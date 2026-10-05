"""FastAPI分层入口：会话、普通对话、统一错误与请求日志。"""
import logging
import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from openai import APITimeoutError

from app import memory
from app.config import Settings
from app.database import Database
from app.llm import ModelNotConfigured, ModelService
from app.locks import SessionLocks
from app.schemas import ApiResponse, ChatRequest, RenameRequest
from app.rate_limit import RateLimiter, RateLimitMiddleware

logger = logging.getLogger("smartchat")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def ok(**data):
    return ApiResponse(data=data)


def service_error(error):
    # 不把上游异常、URL、密钥或堆栈直接返回浏览器。
    logger.error("模型调用失败，异常类型=%s", type(error).__name__)
    if isinstance(error, ModelNotConfigured):
        return HTTPException(503, "模型尚未配置，请在本地 backend/.env 配置 API Key")
    if isinstance(error, (APITimeoutError, TimeoutError)):
        return HTTPException(504, "模型响应超时，请稍后重试")
    return HTTPException(502, "AI 服务暂时不可用，请检查模型配置或稍后重试")


def create_app(settings=None, model_service=None, agent_service=None):
    settings = settings or Settings.load()
    database = Database(settings.db_path)
    models = model_service or ModelService(settings)
    locks = SessionLocks()

    @asynccontextmanager
    async def lifespan(app):
        try:
            database.initialize()
            if app.state.agent is None:
                from app.agent import AgentService
                app.state.agent = AgentService(settings)
            yield
        finally:
            try:
                if app.state.agent is not None:
                    if hasattr(app.state.agent, "aclose"):
                        await app.state.agent.aclose()
                    else:
                        app.state.agent.close()
            finally:
                try:
                    if hasattr(models, "aclose"):
                        await models.aclose()
                finally:
                    database.close()

    app = FastAPI(title="智聊助手 API", version="1.0.0", lifespan=lifespan)
    app.state.database = database
    app.state.settings = settings
    app.state.models = models
    app.state.locks = locks
    app.state.agent = agent_service
    app.state.limiter = RateLimiter(settings.rate_limit)
    app.add_middleware(RateLimitMiddleware, limiter=app.state.limiter)

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                            content={"code": exc.status_code, "message": exc.detail, "data": {}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        errors = [{"loc": e["loc"], "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content=jsonable_encoder({
            "code": 422, "message": "参数校验失败", "data": {"errors": errors}}))

    @app.exception_handler(Exception)
    async def unknown_error(_, exc):
        logger.error("服务异常，类型=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={
            "code": 500, "message": "服务异常，请稍后重试", "data": {}})

    @app.middleware("http")
    async def log_requests(request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        logger.info("%s %s status=%s headers_ms=%.0f", request.method, request.url.path,
                    response.status_code, (time.monotonic() - start) * 1000)
        return response

    @app.get("/api/health", response_model=ApiResponse)
    def health():
        return ok(status="ok", model_configured=bool(settings.api_key), model=settings.model,
                  weather_configured=bool(settings.tavily_api_key), weather_provider="Tavily + Open-Meteo")

    @app.get("/", response_model=ApiResponse)
    def index():
        return ok(service="智聊", docs="/docs")

    @app.get("/api/sessions", response_model=ApiResponse)
    def sessions():
        with database.sessions() as db:
            return ok(sessions=memory.list_sessions(db))

    @app.post("/api/sessions", response_model=ApiResponse)
    def create_session():
        with database.sessions() as db:
            return ok(session=memory.create_session(db))

    @app.patch("/api/sessions/{session_id}", response_model=ApiResponse)
    def rename(session_id: str, req: RenameRequest):
        with locks.hold(session_id), database.sessions() as db:
            session = memory.require_session(db, session_id)
            session.title, session.manual_title = req.title, True
            db.commit()
            return ok(session=memory.session_out(session))

    @app.delete("/api/sessions/{session_id}", response_model=ApiResponse)
    def delete(session_id: str):
        with locks.hold(session_id), database.sessions() as db:
            session = memory.require_session(db, session_id)
            app.state.agent.clear(session_id)
            db.delete(session)
            db.commit()
            return ok(deleted=True)

    @app.get("/api/sessions/{session_id}/messages", response_model=ApiResponse)
    def messages(session_id: str):
        with database.sessions() as db:
            return ok(messages=memory.messages(db, session_id))

    @app.post("/api/chat", response_model=ApiResponse)
    def chat(req: ChatRequest):
        with locks.hold(req.session_id), database.sessions() as db:
            history = memory.bounded_history(memory.messages(db, req.session_id), settings)
            try:
                reply = models.chat(req.message, history)
            except Exception as exc:
                raise service_error(exc) from exc
            saved = memory.append_turn(db, req.session_id, req.message, reply, "chat")
            return ok(reply=reply, **saved)

    def run_agent(req, db, history):
        session = memory.require_session(db, req.session_id)
        try:
            result = app.state.agent.chat(req.message, req.session_id, history, session.history_version)
            saved = memory.append_turn(db, req.session_id, req.message, result["reply"], "agent", result["tools_used"])
            return {**result, **saved}
        except Exception as exc:
            db.rollback()
            app.state.agent.clear(req.session_id)
            raise service_error(exc) from exc

    @app.post("/api/agent/chat", response_model=ApiResponse)
    def agent_chat(req: ChatRequest):
        with locks.hold(req.session_id), database.sessions() as db:
            history = memory.bounded_history(memory.messages(db, req.session_id), settings)
            return ok(**run_agent(req, db, history))

    @app.post("/api/smart/chat", response_model=ApiResponse)
    def smart_chat(req: ChatRequest):
        with locks.hold(req.session_id), database.sessions() as db:
            history = memory.bounded_history(memory.messages(db, req.session_id), settings)
            try:
                route = models.classify(req.message, history)
            except Exception as exc:
                raise service_error(exc) from exc
            if route == "agent":
                return ok(route=route, **run_agent(req, db, history))
            try:
                reply = models.chat(req.message, history)
            except Exception as exc:
                raise service_error(exc) from exc
            saved = memory.append_turn(db, req.session_id, req.message, reply, "chat")
            return ok(route="chat", reply=reply, tools_used=[], **saved)

    @app.post("/api/chat/stream")
    async def stream(req: ChatRequest, request: Request):
        # 先校验会话并取得锁；生成器和数据库连接的释放不依赖请求依赖注入。
        guard = locks.hold(req.session_id)
        guard.__enter__()
        try:
            with database.sessions() as db:
                history = memory.bounded_history(memory.messages(db, req.session_id), settings)
            if not settings.api_key and model_service is None:
                raise service_error(ModelNotConfigured())
        except BaseException:
            guard.__exit__(None, None, None)
            raise

        async def generate():
            chunks, started = [], time.monotonic()
            try:
                async for delta in models.stream(req.message, history):
                    if await request.is_disconnected():
                        return
                    chunks.append(delta)
                    yield "data: " + json.dumps({"delta": delta}, ensure_ascii=False) + "\n\n"
                reply = "".join(chunks)
                if not reply.strip():
                    raise ValueError("流式未返回正文")
                if await request.is_disconnected():
                    return
                with database.sessions() as db:
                    saved = memory.append_turn(db, req.session_id, req.message, reply, "chat")
                yield "data: " + json.dumps(jsonable_encoder({"saved": saved}), ensure_ascii=False) + "\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                error = service_error(exc)
                yield "data: " + json.dumps({"error": error.detail, "code": error.status_code}, ensure_ascii=False) + "\n\n"
            finally:
                guard.__exit__(None, None, None)
                logger.info("stream_complete duration_ms=%.0f", (time.monotonic() - started) * 1000)

        return StreamingResponse(generate(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app


app = create_app()

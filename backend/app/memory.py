from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import ChatMessage, ChatSession, now


def require_session(db, session_id):
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(404, "会话不存在")
    return session


def session_out(session):
    return {key: getattr(session, key) for key in (
        "id", "title", "created_at", "updated_at", "history_version")}


def create_session(db):
    session = ChatSession(id=uuid4().hex)
    db.add(session)
    db.commit()
    return session_out(session)


def list_sessions(db):
    return [session_out(s) for s in db.scalars(select(ChatSession).order_by(
        ChatSession.updated_at.desc(), ChatSession.id))]


def messages(db, session_id):
    require_session(db, session_id)
    return [{"id": m.id, "role": m.role, "content": m.content,
             "created_at": m.created_at, "route": m.route, "tools_used": m.tools_used}
            for m in db.scalars(select(ChatMessage).where(
                ChatMessage.session_id == session_id).order_by(ChatMessage.id))]


def bounded_history(history, settings):
    """按完整问答轮次裁剪；完整记录仍保留在业务数据库中。"""
    result, size = [], 0
    for i in range(len(history) - 2, -1, -2):
        pair = history[i:i + 2]
        cost = sum(len(m["content"]) for m in pair)
        if len(result) >= settings.history_turns * 2 or size + cost > settings.history_char_limit:
            break
        result[0:0] = pair
        size += cost
    return result


def append_turn(db, session_id, user, reply, route, tools=()):
    session = require_session(db, session_id)
    db.add_all([
        ChatMessage(session_id=session_id, role="user", content=user),
        ChatMessage(session_id=session_id, role="assistant", content=reply,
                    route=route, tools_used=list(tools)),
    ])
    if session.history_version == 0 and not session.manual_title:
        session.title = user[:16] + ("…" if len(user) > 16 else "")
    session.updated_at = now()
    session.history_version += 1
    db.commit()  # 用户消息、回答与版本号在同一事务中提交。

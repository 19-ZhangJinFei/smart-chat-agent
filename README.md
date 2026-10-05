# 智聊——基于 LangChain 的智能客服系统

个人课设：复现三课教程，实现FastAPI后端、Vue3界面、五工具、双库记忆、自动路由、SSE、限流、评估和Docker交付。订单、天气、优惠券为教学模拟数据。

## 本机启动

Python3.11、Node20.19+或22.12+、Git。PowerShell在项目根目录执行：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Copy-Item backend\.env.example backend\.env
```

已有.env时不要覆盖。仅本机填写LLM_API_KEY，匹配Key地域与LLM_BASE_URL；默认qwen-plus。环境变量优先，路径相对backend固定解析。无Key仍可管理会话与检查健康。

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
Set-Location frontend
npm ci --registry=https://registry.npmjs.org
npm run dev
```

页面 http://127.0.0.1:5173 ，Swagger http://127.0.0.1:8000/docs 。API由Vite代理，密钥不传给浏览器。

## Docker交付

Docker Desktop使用Linux引擎，backend/.env配置后：

```powershell
docker compose up -d --build --wait
docker compose ps
docker compose logs --tail 50 backend
docker compose down
```

默认 http://127.0.0.1:8080 ，Swagger在同端口/docs。端口占用时根目录.env写SMARTCHAT_PORT=8081，重建前端容器。本机实际8081，避免影响已有Docker应用。双库挂载backend/data，停启/重建保留数据；后端不向宿主机开放8000。单worker内存限流重启重置。

## 测试与真实模型验证

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
Set-Location frontend
npm test
npm run build
```

离线测试不请求模型。根目录以下命令会使用本机Key产生真实调用，请按需单次运行：

```powershell
.venv\Scripts\python.exe backend\verify_models.py
.venv\Scripts\python.exe backend\verify_live.py
.venv\Scripts\python.exe backend\test_eval.py
.venv\Scripts\python.exe backend\experiment_prompt.py
.venv\Scripts\python.exe backend\verify_advanced.py
.venv\Scripts\python.exe backend\verify_docker.py --port 8081
```

Docker验收会停启和重建本项目容器、生成备份。评估每题独立会话，每次唯一ID，结果在artifacts/evidence；保留失败和优化后结果。10题课堂指标与补充指标分开，小样本不能证明所有问题均正确。

## 学习和交付材料

- [课程对应与核心原理](docs/IMPLEMENTATION.md)
- [接口约定](docs/API.md)
- [使用说明](docs/USER_GUIDE.md)
- [测试记录](docs/TESTING.md)
- [部署与备份恢复](docs/DEPLOYMENT.md)
- [答辩演示与问答](docs/DEFENSE.md)
- [真实开发日志](docs/DEVELOPMENT_LOG.md)
- [阶段清单](docs/ROADMAP.md)

CI仅运行离线测试与前端构建，不配置真实Key。个人报告和代码包在本地忽略目录，需本人复核，答辩后经老师确认再提交。公开仓库排除个人身份信息、Key、运行数据库和课程原始附件。MIT许可只涵盖本仓库原创实现。

模型配置参考[百炼OpenAI兼容接口](https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions)，智能体参考[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents)，构建环境参考[Vite](https://vite.dev/guide/)。

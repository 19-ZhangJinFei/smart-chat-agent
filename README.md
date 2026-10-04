# 智聊 SmartChat Agent

基于 FastAPI、Vue 3、LangChain 与 LangGraph 的智能客服学习项目。按后端、智能体与前端、容器化交付三个阶段逐步开发，并保留真实的实现与验证记录。

## 当前状态

项目初始化完成，业务功能尚未实现。当前仓库不能作为可运行系统使用。

## 计划功能

- 多轮对话、SQLite 持久化、会话新建/查询/改名/删除。
- 订单、天气、计算、时间工具与本轮调用记录。
- Vue 聊天界面、历史恢复、加载与错误提示。
- 意图路由、SSE 流式输出、限流与自动化评估。
- Docker Compose 部署、数据卷与重启持久化验证。

初期订单与天气采用明确标注的模拟数据，真实接口作为后续扩展。

## 技术路线

后端：Python / FastAPI / SQLAlchemy / Pydantic。
模型与智能体：LangChain / LangGraph / OpenAI 兼容模型 API。
前端：Vue 3 / Element Plus / Vite。
部署：Docker Compose / Nginx / SQLite 数据卷。

具体依赖版本在实现阶段验证并固定。

## 项目管理

- [阶段任务与验收标准](docs/ROADMAP.md)
- [真实开发日志](docs/DEVELOPMENT_LOG.md)
- [贡献与版本管理约定](CONTRIBUTING.md)
- GitHub Issues 跟踪任务，提交或 PR 关联对应 Issue。

## 配置与安全

模型密钥放在本地 `.env`，后续提供无密钥的 `.env.example`。密钥、数据库、日志、虚拟环境与构建产物不得提交。实际截图与评估结果完成后再添加，不填写未经验证的结果。

## 来源与许可

项目参考课程提供的三份 LangChain / 智能体 / Docker 教学材料。课程原文和原始示例未上传，其许可不由本仓库声明；复用具体代码时应记录来源并确认许可。

本仓库自行编写的内容采用 MIT 许可。功能、测试和部署说明将随开发进度更新。

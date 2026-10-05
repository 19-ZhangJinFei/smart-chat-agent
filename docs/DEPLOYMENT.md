# 部署与恢复

Compose使用Python3.11后端和Nginx前端；Node22仅构建。Nginx转发/api和Swagger，关闭缓冲，读取超时180秒。后端健康后启动前端。一个worker，可信代理网段172.29.90.0/24。

默认127.0.0.1:8080。本机已有docker-nginx-1占用，根目录.env配置SMARTCHAT_PORT=8081。后端Key仅backend/.env。启动 `docker compose up -d --build --wait`；查看 `docker compose ps`、`logs --tail 50 backend`。

双库共同挂载backend/data；down移除本项目容器和网络，保留数据；up --build --force-recreate重建应用但保留目录。不要让开发后端和容器同时写同一个data目录。

## 备份与恢复步骤

1. 等生成结束，`docker compose stop backend`。
2. 根目录运行 `.venv\Scripts\python.exe backend\backup_data.py artifacts/private/backup-new`，目标必须全新。SQLite backup API复制两库并检查完整性，拒绝覆盖。
3. 记录备份日期和版本，保存到安全位置，不上传含对话的数据库。
4. 恢复前停止后端，把原data目录改名保存，建立空data目录，复制备份中的两个数据库原名文件；不要保留旧WAL/SHM。
5. `docker compose up -d --wait`，读取历史并追问原姓名验证恢复。

本次验收将备份复制到独立临时目录，启动独立FastAPI服务恢复历史，并完成真实智能体追问，避免覆盖演示数据。

端口冲突改SMARTCHAT_PORT。502/504检查异常类型、Key地域和Base URL。429等待窗口。子网冲突时同时修改Compose子网与后端可信代理范围并重建，不能只改一处。

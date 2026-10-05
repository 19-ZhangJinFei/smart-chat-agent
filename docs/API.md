# API约定

普通响应为UTF-8 JSON `{code,message,data}`，成功code=0，错误code=HTTP状态。POST聊天请求包含session_id、message；改名包含title。

| 方法与路径 | data |
|---|---|
| GET /api/health | status/model_configured/model/weather_configured/weather_provider |
| GET /api/sessions | sessions数组 |
| POST /api/sessions | session |
| PATCH /api/sessions/{id} | session |
| DELETE /api/sessions/{id} | deleted |
| GET /api/sessions/{id}/messages | messages数组 |
| POST /api/chat | reply/session/messages（本轮两条） |
| POST /api/agent/chat | reply/tools_used/session/messages（本轮两条） |
| POST /api/smart/chat | route/reply/tools_used/session/messages（本轮两条） |
| POST /api/chat/stream | SSE delta/saved/error/[DONE] |

message去除首尾空白后1—2000字符，title为1—80字符。422参数错误，404缺失会话，409生成冲突，429限流含Retry-After，503未配置，502模型失败，504超时。上游错误详情和Key不返回客户端。

会话响应含id/title/history_version/created_at/updated_at，manual_title保存在数据库内部；历史消息响应含id/role/content/created_at/route/tools_used，session_id通过路径指定。时间为北京时间，会话按更新时间倒序，消息按ID递增。

流式事件 `data: {"delta":"你好"}`，空行分隔。生成完成并成功保存后发送 `data: [DONE]`。error或缺失DONE表示未确认完成，网络可能恰在落库后中断，重试前先刷新历史。

2026-10-06修正：成功聊天响应附带数据库提交后的session及本轮两条messages，前端直接更新问答、标题和排序，不再每轮读取整段历史和会话列表。SSE在落库后先发送 `data: {"saved":{"session":...,"messages":[...]}}`，再发送DONE；saved本身不能替代DONE完成确认。429响应data含retry_after，与Retry-After头一致；前端共享冷却窗口，在到期前阻止新的API请求（健康检查除外），问题保留供稍后重试。限流仍为每IP每60秒20次，覆盖所有API及管理接口，健康检查除外。

weather_configured只表示本地Tavily密钥非空，健康检查不进行外部请求，不能当作密钥有效性验证。天气查询仍走原有智能体/自动聊天接口，工具名仍为get_weather；来源和查询时间保存于助手正文，刷新后仍可查看。

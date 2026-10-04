import json
import math
import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self, limit, clock=time.monotonic):
        self.limit, self.clock = limit, clock
        self.records, self.lock = {}, Lock()

    def check(self, ip):
        now = self.clock()
        with self.lock:
            # 定期移除过期IP，避免字典永久增长。
            for key in list(self.records):
                queue = self.records[key]
                while queue and now - queue[0] >= 60:
                    queue.popleft()
                if not queue:
                    del self.records[key]
            queue = self.records.setdefault(ip, deque())
            if len(queue) >= self.limit:
                return max(1, math.ceil(60 - (now - queue[0])))
            queue.append(now)
        return 0


class RateLimitMiddleware:
    def __init__(self, app, limiter):
        self.app, self.limiter = app, limiter

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/api/") and scope["path"] != "/api/health":
            ip = scope.get("client", ("unknown", 0))[0]
            retry = self.limiter.check(ip)
            if retry:
                body = json.dumps({"code": 429, "message": "请求过于频繁，请稍后再试", "data": {}},
                                  ensure_ascii=False).encode()
                await send({"type": "http.response.start", "status": 429, "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"retry-after", str(retry).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)

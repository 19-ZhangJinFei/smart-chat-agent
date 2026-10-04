from contextlib import contextmanager
from threading import Lock

from fastapi import HTTPException


class SessionLocks:
    """单进程会话锁；不等待生成结束，竞争请求返回409。"""
    def __init__(self):
        self.guard = Lock()
        self.active = set()

    @contextmanager
    def hold(self, session_id):
        with self.guard:
            if session_id in self.active:
                raise HTTPException(409, "该会话正在生成，请稍后再试")
            self.active.add(session_id)
        try:
            yield
        finally:
            with self.guard:
                self.active.discard(session_id)

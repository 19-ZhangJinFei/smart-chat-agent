from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models import Base


class Database:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", connect_args={
            "check_same_thread": False, "timeout": 15})

        @event.listens_for(self.engine, "connect")
        def configure(conn, _):
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")

        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self):
        Base.metadata.create_all(self.engine)

    def close(self):
        self.engine.dispose()

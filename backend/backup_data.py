"""备份前停止后端，确保两个数据库来自同一个已完成状态。"""
import argparse
import sqlite3
from pathlib import Path

from app.config import Settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="使用SQLite backup API备份双库；先停止后端")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    settings = Settings.load()
    for source in [settings.db_path, settings.agent_db_path]:
        destination = args.destination / source.name
        if destination.exists():
            raise SystemExit("备份目标已存在，请使用新的目录，避免覆盖")
        with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
                assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        print(f"已备份：{source.name}")

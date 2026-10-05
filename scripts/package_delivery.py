"""从Git提交导出私有交付目录；不复制工作区密钥、数据库或依赖。

使用项目虚拟环境运行，身份资料只读取忽略目录中的JSON。
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def package(profile_path, private_dir, env_path):
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    private_dir = private_dir.resolve()
    destination = private_dir / "交付" / f"智聊-{profile['专业班级']}-{profile['姓名']}"
    code_dir = destination / f"智聊-{profile['姓名']}-代码"
    report = destination / f"{profile['专业班级']}-{profile['姓名']}-个人报告.docx"
    if not report.is_file():
        raise ValueError("先保存排版检查通过的报告初稿")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", "--format=zip", commit], cwd=ROOT)
    config = dotenv_values(env_path)
    secrets = [os.environ.get(name) or config.get(name, '') for name in ('LLM_API_KEY', 'TAVILY_API_KEY')]
    secrets += [profile["姓名"], profile["学号"]]
    hashes = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        for entry in source.infolist():
            path = PurePosixPath(entry.filename)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("源码归档存在不安全路径")
            if entry.is_dir():
                continue
            name = path.name
            if (any(part in {".git", ".venv", "node_modules", "private", "__pycache__"} for part in path.parts)
                    or (name.startswith(".env") and not name.endswith(".example"))
                    or name.endswith((".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3", ".pyc"))):
                raise ValueError("源码归档包含禁止交付的运行文件")
            content = source.read(entry)
            if any(secret and secret.encode() in content for secret in secrets):
                raise ValueError("源码归档检测到真实密钥或个人身份，停止导出")
            hashes[entry.filename] = hashlib.sha256(content).hexdigest()
        # 校验全部通过后才写文件，拒绝覆盖已含额外文件的旧交付目录。
        if code_dir.exists():
            extras = [p for p in code_dir.rglob("*") if p.is_file()
                      and p.relative_to(code_dir).as_posix() not in hashes]
            if extras:
                raise ValueError("旧代码包含额外文件，请使用新的私有交付目录")
        for entry in source.infolist():
            if entry.is_dir():
                continue
            target = code_dir.joinpath(*PurePosixPath(entry.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(entry))
    report_hash = hashlib.sha256(report.read_bytes()).hexdigest()
    qa_path = private_dir / "report-qa.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.is_file() else {}
    template_verified = (qa.get("school_original_template") == "verified"
                         and qa.get("report_sha256") == report_hash)
    manifest = {"commit": commit, "files": hashes,
                "report_sha256": report_hash,
                "school_template_review": "verified" if template_verified else "pending",
                "personal_rehearsal": "pending"}
    (private_dir / "delivery-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"代码包已导出：{len(hashes)}个受版本管理文件，密钥与身份扫描通过，提交{commit[:7]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--env", type=Path, required=True)
    args = parser.parse_args()
    package(args.profile, args.private_dir, args.env)

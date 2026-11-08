"""测试公共夹具：临时库 + 建表 + 少量种子数据。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.uow import Database  # noqa: E402

SCHEMA = (ROOT / "scripts" / "schema.sql").read_text(encoding="utf-8")


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "t.db", busy_timeout_ms=200)
    d.init_schema(SCHEMA)
    return d


@pytest.fixture()
def seeded(db):
    conn = db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at) "
                 "VALUES('alice','x','student','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at) "
                 "VALUES('admin','x','admin','2026-01-01T00:00:00Z')")
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status) "
                 "VALUES(2,'软件工程综合实训','2026秋',48,'enabled')")
    for name, chapter in [("循环结构", "第3章"), ("数组", "第4章"), ("指针", "第5章")]:
        conn.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                     "reference_minutes,status) VALUES(1,?,?,3,60,'enabled')",
                     (name, chapter))
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def cfg():
    from app.core import config as C
    return C.load({"DB_PATH": ":memory:", "SECRET_KEY": "test-secret"})


@pytest.fixture()
def svc(seeded):
    from app.services.content import ContentService
    return ContentService(seeded)


@pytest.fixture()
def auth_svc(seeded, cfg):
    from app.services.auth import AuthService
    return AuthService(seeded, cfg)


@pytest.fixture()
def client(tmp_path):
    """带管理员/学生、一门课程、3 个知识点、1 条先修边的 HTTP 客户端。"""
    from fastapi.testclient import TestClient

    from app.core.security import hash_password
    from app.main import create_app

    app = create_app({"DB_PATH": str(tmp_path / "t.db"), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "s"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-01-01T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-01-01T00:00:00Z')",
                 (hash_password("Passw0rd!"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程','2026秋',48,'enabled')")
    for name, mins in [("循环结构", 120), ("数组", 90), ("指针", 150)]:
        conn.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                     "reference_minutes,status) VALUES(1,?, '第1章',3,?,'enabled')",
                     (name, mins))
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,1,2)")          # 循环 → 数组：闭包含 1、2
    conn.commit()
    conn.close()
    return TestClient(app, raise_server_exceptions=False)

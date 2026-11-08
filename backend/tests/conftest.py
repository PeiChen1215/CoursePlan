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

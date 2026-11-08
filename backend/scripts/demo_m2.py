"""M2 演示脚本：登录 → 建知识点 → 提交先修 → 制造环路 → 越权被拒。

用法（在 backend 目录下）：
    python scripts/demo_m2.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    db_path = Path(__file__).resolve().parents[1] / "data" / "demo_m2.db"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()                  # 每次演示从空库开始
    app = create_app({"DB_PATH": str(db_path), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "demo-secret"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-11-08T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-11-08T00:00:00Z')",
                 (hash_password("Passw0rd!"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程综合实训','2026秋',48,'enabled')")
    conn.commit()
    conn.close()

    c = TestClient(app, raise_server_exceptions=False)

    r = c.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    token = r.json()["data"]["token"]
    print("1) 管理员登录        → 200，令牌 %s…" % token[:18])
    h = {"Authorization": "Bearer " + token}

    ids = []
    for name, chapter, diff, minutes in [("循环结构", "第3章", 3, 120),
                                         ("数组", "第4章", 2, 90),
                                         ("指针", "第5章", 4, 150)]:
        resp = c.post("/api/courses/1/concepts", headers=h,
                      json={"name": name, "chapter": chapter,
                            "difficulty": diff, "reference_minutes": minutes})
        ids.append(resp.json()["data"]["concept_id"])
    print("2) 建 3 个知识点      → id = %s" % ids)

    r = c.post("/api/courses/1/prerequisites/batch", headers=h,
               json={"edges": [[ids[0], ids[1]], [ids[1], ids[2]]]})
    print("3) 提交 循环→数组→指针 → saved=%d" % r.json()["data"]["saved"])

    r = c.post("/api/courses/1/prerequisites/batch", headers=h,
               json={"edges": [[ids[2], ids[0]]]})
    body = r.json()
    print("4) 提交 指针→循环（成环）→ HTTP %d / %s / 环路 %s"
          % (r.status_code, body["code"], "→".join(str(x) for x in body["detail"]["cycle"])))

    st = c.post("/api/auth/login",
                json={"username": "alice", "password": "Passw0rd!"}).json()["data"]["token"]
    r = c.post("/api/courses/1/concepts", headers={"Authorization": "Bearer " + st},
               json={"name": "x", "chapter": "c", "difficulty": 1, "reference_minutes": 10})
    print("5) 学生建知识点      → HTTP %d / %s" % (r.status_code, r.json()["code"]))

    r = c.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    print("6) 口令错误          → HTTP %d / %s" % (r.status_code, r.json()["code"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

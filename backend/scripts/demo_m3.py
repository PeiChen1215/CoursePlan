"""M3 演示：建课 → 建知识点 → 填约束 → 算容量。

用法（backend 目录）：python scripts/demo_m3.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402

BASE = "2026-11-09T09:00:00Z"          # 周一上午 9 点


def main() -> int:
    db_path = Path(__file__).resolve().parents[1] / "data" / "demo_m3.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()

    app = create_app({"DB_PATH": str(db_path), "LOG_LEVEL": "ERROR",
                      "SECRET_KEY": "demo"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-11-01T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-11-01T00:00:00Z')",
                 (hash_password("Passw0rd!"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程综合实训','2026秋',48,'enabled')")
    for name, chapter, mins in [("循环结构", "第3章", 120), ("数组", "第4章", 90),
                                ("指针", "第5章", 150)]:
        conn.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                     "reference_minutes,status) VALUES(1,?,?,3,?,'enabled')",
                     (name, chapter, mins))
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,1,2)")
    conn.commit()
    conn.close()

    c = TestClient(app, raise_server_exceptions=False)
    tok = c.post("/api/auth/login",
                 json={"username": "alice", "password": "Passw0rd!"}).json()["data"]["token"]
    h = {"Authorization": "Bearer " + tok}

    pid = c.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    print("1) 学生建计划        → plan_id=%d" % pid)

    body = {
        "target_concept_id": 2,
        "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": BASE,
    }
    d = c.put("/api/plans/%d/constraint" % pid, headers=h, json=body).json()["data"]
    print("2) 填写约束          → C=%d, B=%d, C'=%d, 时段=%d 段"
          % (d["C"], d["B"], d["C_prime"], d["slots"]))
    print("3) 目标路径时长      → %d 分钟（目标 2 的闭包含 1、2：90+120）"
          % d["path_minutes"])

    zero = dict(body, availability={})
    r = c.post("/api/plans/%d/capacity/preview" % pid, headers=h, json=zero)
    print("4) 可用时间为空      → reject_reason=%s" % r.json()["data"]["reject_reason"])

    excluded = dict(body, excluded_dates=["2026-11-%02d" % day for day in range(9, 21)])
    r = c.post("/api/plans/%d/capacity/preview" % pid, headers=h, json=excluded)
    print("5) 排除整个区间      → reject_reason=%s, C=%d"
          % (r.json()["data"]["reject_reason"], r.json()["data"]["C"]))

    mastered = dict(body, mastered_concept_ids=[2])
    r = c.post("/api/plans/%d/capacity/preview" % pid, headers=h, json=mastered)
    print("6) 目标已自评掌握    → reject_reason=%s" % r.json()["data"]["reject_reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

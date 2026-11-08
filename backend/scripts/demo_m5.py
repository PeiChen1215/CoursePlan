"""M5 演示：生成草案 → 校验 → 确认 → 再生成 → 差异。

用法（backend 目录）：python scripts/demo_m5.py
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402
from app.services.version import VersionService  # noqa: E402

BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)


def main() -> int:
    db_path = Path(__file__).resolve().parents[1] / "data" / "demo_m5.db"
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()

    app = create_app({"DB_PATH": str(db_path), "LOG_LEVEL": "ERROR", "SECRET_KEY": "d"})
    conn = app.state.db.connect()
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-11-01T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-11-01T00:00:00Z')",
                 (hash_password("Passw0rd!"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程综合实训','2026秋',48,'enabled')")
    for name, chapter, order, mins in [("循环结构", "第3章", 1, 120),
                                       ("数组", "第4章", 2, 90),
                                       ("指针", "第5章", 3, 150)]:
        conn.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                     "reference_minutes,sort_order,status) VALUES(1,?,?,3,?,?,'enabled')",
                     (name, chapter, mins, order))
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,1,2)")
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,2,3)")
    conn.commit()
    conn.close()

    c = TestClient(app, raise_server_exceptions=False)
    info = c.post("/api/auth/login",
                  json={"username": "alice", "password": "Passw0rd!"}).json()["data"]
    h = {"Authorization": "Bearer " + info["token"]}
    uid = info["user_id"]
    pid = c.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    c.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 3, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]],
                         "sat": [["09:00", "11:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    planner = PlannerService(app.state.db, app.state.config)
    d1 = planner.generate(pid, uid, BASE)
    print("1) 生成草案 v1      → revision=%d，%d 任务 / %d 片"
          % (d1.revision, len(d1.tasks), len(d1.slices)))

    vs = VersionService(app.state.db, app.state.config)
    r1 = vs.confirm(pid, d1.revision, "click-1", uid, BASE)
    print("2) 确认             → v%d 生效，replayed=%s" % (r1.version_no, r1.replayed))

    r1b = vs.confirm(pid, d1.revision, "click-1", uid, BASE)
    print("3) 同键重复确认     → replayed=%s，版本数仍为 1" % r1b.replayed)

    later = datetime(2026, 11, 10, 9, tzinfo=timezone.utc)
    d2 = planner.generate(pid, uid, later)
    r2 = vs.confirm(pid, d2.revision, "click-2", uid, BASE)
    print("4) 再生成并确认     → v%d，差异 %s"
          % (r2.version_no, {k: len(v) for k, v in r2.diff.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

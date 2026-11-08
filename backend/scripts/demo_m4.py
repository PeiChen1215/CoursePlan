"""M4 演示：从约束一路生成草案（拆分 → 排序 → 装箱 → 指标）。

用法（backend 目录）：python scripts/demo_m4.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.core import config as C  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402

BASE = "2026-11-09T09:00:00Z"


def main() -> int:
    db_path = Path(__file__).resolve().parents[1] / "data" / "demo_m4.db"
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
    login = c.post("/api/auth/login",
                   json={"username": "alice", "password": "Passw0rd!"}).json()["data"]
    tok, uid = login["token"], login["user_id"]
    h = {"Authorization": "Bearer " + tok}
    pid = c.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    c.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 3,
        "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]],
                         "sat": [["09:00", "11:00"]]},
        "base_time": BASE,
    })
    print("1) 计划与约束就绪    → plan_id=%d，目标=指针（闭包含 循环/数组/指针）" % pid)

    draft = PlannerService(app.state.db, app.state.config).generate(
        pid, uid, datetime(2026, 11, 9, 9, tzinfo=timezone.utc))
    print("2) 生成草案          → revision=%d，hash=%s…" % (draft.revision, draft.hash[:12]))
    print("3) 拓扑序            → %s" % draft.order)
    print("4) 任务拆分（7:3）   → %s" % [(t.task_no, t.minutes) for t in draft.tasks])
    print("5) 装箱结果          → %d 片，首片 %s ~ %s"
          % (len(draft.slices), draft.slices[0].start.strftime("%m-%d %H:%M"),
             draft.slices[0].end.strftime("%H:%M")))
    print("6) 未排入            → %s" % ([(u.task_no, u.reason) for u in draft.unscheduled] or "无"))
    m = draft.metrics
    print("7) 指标 T=%d C=%d B=%d C'=%d D=%d U=%.2f"
          % (m.total_minutes, m.raw_minutes, m.buffer_minutes, m.usable_minutes,
             m.deficit_minutes, m.utilization))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

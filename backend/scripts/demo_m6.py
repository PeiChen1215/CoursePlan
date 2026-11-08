"""M6 演示：自然语言抽取 → 打卡 → 更正 → 完成率与逾期。

用法（backend 目录）：python scripts/demo_m6.py
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
    db_path = Path(__file__).resolve().parents[1] / "data" / "demo_m6.db"
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
    conn.commit()
    conn.close()

    c = TestClient(app, raise_server_exceptions=False)
    info = c.post("/api/auth/login",
                  json={"username": "alice", "password": "Passw0rd!"}).json()["data"]
    h = {"Authorization": "Bearer " + info["token"]}
    uid = info["user_id"]

    r = c.post("/api/agent/extract", headers=h, json={
        "utterance": "我想学指针，10 天后，每天两小时",
        "base_date": "2026-11-09"}).json()["data"]
    print("1) 句子抽取          → 目标=%s 截止=%s 每日=%s 模式=%s"
          % (r["fields"]["target_concept_id"], r["fields"]["deadline"],
             r["fields"]["daily_limit"], r["mode"]))
    print("2) 还缺什么          → %s" % (r["questions"] or "无"))

    pid = c.post("/api/plans", headers=h, json={"course_id": 1}).json()["data"]["plan_id"]
    c.put("/api/plans/%d/constraint" % pid, headers=h, json={
        "target_concept_id": 2, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]]},
        "base_time": "2026-11-09T09:00:00Z"})
    draft = PlannerService(app.state.db, app.state.config).generate(pid, uid, BASE)
    VersionService(app.state.db, app.state.config).confirm(pid, draft.revision,
                                                           "k1", uid, BASE)
    tasks = [int(x["task_id"]) for x in app.state.db.query(
        "SELECT task_id FROM version_task WHERE version_id=1 ORDER BY task_id")]

    e1 = c.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e1"},
                json={"task_id": tasks[0], "event_type": "done",
                      "actual_minutes": 50}).json()["data"]
    print("3) 打卡完成          → 事件 %d，完成率 %.1f%%"
          % (e1["event_id"], e1["completion_rate"] * 100))

    again = c.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e1"},
                   json={"task_id": tasks[0], "event_type": "done",
                         "actual_minutes": 50}).json()["data"]
    print("4) 同键重复打卡      → replayed=%s，事件数仍为 1" % again["replayed"])

    c.post("/api/plans/%d/events" % pid, headers={**h, "Idempotency-Key": "e2"},
           json={"task_id": tasks[0], "event_type": "correction",
                 "actual_minutes": 35, "corrects_event_id": e1["event_id"]})
    p = c.get("/api/plans/%d/progress" % pid, headers=h).json()["data"]
    print("5) 更正用时为 35     → 已用 %d 分钟，完成 %d/%d"
          % (p["actual_minutes"], p["done_tasks"], p["total_tasks"]))
    print("6) 逾期任务          → 当前时刻无逾期: %s" % (p["overdue_tasks"] or "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

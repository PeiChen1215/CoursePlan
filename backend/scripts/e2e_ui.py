"""端到端联调：真实起服务后，经 Vite 代理走完整流程。

前置：后端 8000（DSH_DB_PATH=data/dev_ui.db）、前端 5173 均已启动。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.uow import Database  # noqa: E402

BASE = "http://127.0.0.1:5173"          # 走前端代理，顺带验证 vite proxy
DB = Path(__file__).resolve().parents[2] / "data" / "dev_ui.db"
SCHEMA = Path(__file__).resolve().parents[2] / "scripts" / "schema.sql"


def seed() -> None:
    db = Database(DB)
    db.init_schema(SCHEMA.read_text(encoding="utf-8"))
    conn = db.connect()
    conn.execute("DELETE FROM learning_event")
    conn.execute("DELETE FROM task_slice")
    conn.execute("DELETE FROM version_task")
    conn.execute("DELETE FROM plan_validation")
    conn.execute("DELETE FROM plan_version")
    conn.execute("DELETE FROM plan_task")
    conn.execute("DELETE FROM plan_draft")
    conn.execute("DELETE FROM plan_constraint")
    conn.execute("DELETE FROM study_plan")
    conn.execute("DELETE FROM prerequisite")
    conn.execute("DELETE FROM concept")
    conn.execute("DELETE FROM course")
    conn.execute("DELETE FROM app_user")
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('admin',?,'admin','2026-11-01T00:00:00Z')",
                 (hash_password("Admin123!"),))
    conn.execute("INSERT INTO app_user(username,password_hash,role,created_at)"
                 " VALUES('alice',?,'student','2026-11-01T00:00:00Z')",
                 (hash_password("Passw0rd!"),))
    conn.execute("INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
                 " VALUES(1,'软件工程综合实训','2026秋',48,'enabled')")
    for name, chapter, order, minutes in [("循环结构", "第3章", 1, 120),
                                          ("数组", "第4章", 2, 90),
                                          ("指针", "第5章", 3, 150)]:
        conn.execute("INSERT INTO concept(course_id,name,chapter,difficulty,"
                     "reference_minutes,sort_order,status)"
                     " VALUES(1,?,?,3,?,?,'enabled')", (name, chapter, minutes, order))
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,1,2)")
    conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                 " VALUES(1,2,3)")
    conn.commit()
    conn.close()


def main() -> int:
    client = httpx.Client(base_url=BASE, timeout=20.0)

    page = client.get("/")
    print("1) 前端首页          → HTTP %d，含 #root=%s"
          % (page.status_code, 'id="root"' in page.text))
    main_tsx = client.get("/src/main.tsx")
    print("2) TSX 编译          → HTTP %d，%d 字节"
          % (main_tsx.status_code, len(main_tsx.text)))

    seed()
    print("3) 种子数据          → 2 用户 / 1 课程 / 3 知识点 / 2 条先修")

    login = client.post("/api/auth/login", json={"username": "alice",
                                                 "password": "Passw0rd!"}).json()
    token = login["data"]["token"]
    headers = {"Authorization": "Bearer " + token}
    print("4) 登录（经代理）    → 用户 %d，角色 %s"
          % (login["data"]["user_id"], login["data"]["role"]))

    extract = client.post("/api/agent/extract", headers=headers, json={
        "utterance": "我想学指针，10 天后，每天两小时", "base_date": "2026-11-09"}).json()["data"]
    print("5) 一句话抽取        → 目标 %s，截止 %s，模式 %s"
          % (extract["fields"]["target_concept_id"], extract["fields"]["deadline"],
             extract["mode"]))

    plan = client.post("/api/plans", headers=headers, json={"course_id": 1}).json()["data"]
    pid = plan["plan_id"]
    print("6) 建计划            → plan_id=%d" % pid)

    cap = client.put("/api/plans/%d/constraint" % pid, headers=headers, json={
        "target_concept_id": 3, "deadline": "2026-11-20",
        "availability": {"mon": [["19:00", "21:00"]], "wed": [["19:00", "21:00"]],
                         "sat": [["09:00", "11:00"]]},
        "base_time": "2026-11-09T09:00:00Z"}).json()["data"]
    print("7) 存约束            → C=%d B=%d C'=%d 时段=%d 路径=%d 分钟"
          % (cap["C"], cap["B"], cap["C_prime"], cap["slots"], cap["path_minutes"]))

    draft = client.post("/api/plans/%d/drafts" % pid, headers=headers).json()["data"]
    print("8) 生成草案          → revision=%d，任务 %d，片 %d，校验通过=%s"
          % (draft["revision"], len(draft["tasks"]), len(draft["slices"]),
             draft["report"]["passed"]))

    confirm = client.post("/api/plans/%d/drafts/%d/confirm" % (pid, draft["revision"]),
                          headers={**headers, "Idempotency-Key": "e2e-1"},
                          json={"revision": draft["revision"]}).json()["data"]
    print("9) 确认              → v%d 生效，replayed=%s"
          % (confirm["version_no"], confirm["replayed"]))

    board = client.get("/api/plans/%d/board" % pid, headers=headers).json()["data"]
    print("10) 看板             → 版本 v%s，任务 %d，未排入 %d，只读=%s"
          % (board["version_no"], len(board["tasks"]), len(board["unscheduled"]),
             board["readonly"]))

    first = board["tasks"][0]
    done = client.post("/api/plans/%d/events" % pid,
                       headers={**headers, "Idempotency-Key": "e2e-done-1"},
                       json={"task_id": first["task_id"], "event_type": "done",
                             "actual_minutes": 45}).json()["data"]
    print("11) 打卡             → 事件 %d，完成率 %.1f%%"
          % (done["event_id"], done["completion_rate"] * 100))

    replay = client.post("/api/plans/%d/events" % pid,
                         headers={**headers, "Idempotency-Key": "e2e-done-1"},
                         json={"task_id": first["task_id"], "event_type": "done",
                               "actual_minutes": 45}).json()["data"]
    print("12) 同键重放         → replayed=%s" % replay["replayed"])

    versions = client.get("/api/plans/%d/versions" % pid, headers=headers).json()["data"]
    print("13) 版本列表         → %d 个版本，首个 v%d 含 %d 任务"
          % (len(versions["items"]), versions["items"][0]["version_no"],
             versions["items"][0]["tasks"]))

    progress = client.get("/api/plans/%d/progress" % pid, headers=headers).json()["data"]
    print("14) 进度             → %d/%d，实际用时 %d 分钟"
          % (progress["done_tasks"], progress["total_tasks"], progress["actual_minutes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

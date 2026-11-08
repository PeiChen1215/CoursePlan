"""种子数据验收：确认看板/版本/进度能读到种子计划，且管理员能维护内容。

前置：后端 8000 已用种子库启动，前端 5173 已启动。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

BASE = "http://127.0.0.1:5173"


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=20.0)

    alice = c.post("/api/auth/login",
                   json={"username": "alice", "password": "Passw0rd!"}).json()["data"]
    h = {"Authorization": "Bearer " + alice["token"]}

    plans = c.get("/api/plans", headers=h).json()["data"]["items"]
    print("1) alice 的计划      → %d 个，%s，当前 v%s"
          % (len(plans), plans[0]["course_name"], plans[0]["current_version"]))
    pid = plans[0]["plan_id"]

    board = c.get("/api/plans/%d/board" % pid, headers=h).json()["data"]
    print("2) 看板              → 任务 %d，未排入 %d，完成率 %.0f%%，提示 %d 项"
          % (len(board["tasks"]), len(board["unscheduled"]),
             board["progress"]["completion_rate"] * 100, len(board["issues"])))
    first = board["tasks"][0]
    print("   首个任务           → %s（%s，%d 分钟，%s）"
          % (first["concept_name"], first["kind"], first["minutes"], first["start"]))

    versions = c.get("/api/plans/%d/versions" % pid, headers=h).json()["data"]["items"]
    print("3) 版本              → v%d，%d 任务 / %d 片"
          % (versions[0]["version_no"], versions[0]["tasks"], versions[0]["slices"]))

    done = c.post("/api/plans/%d/events" % pid,
                  headers={**h, "Idempotency-Key": "seed-check-1"},
                  json={"task_id": first["task_id"], "event_type": "done",
                        "actual_minutes": 40}).json()["data"]
    progress = c.get("/api/plans/%d/progress" % pid, headers=h).json()["data"]
    print("4) 打卡后进度        → %d/%d，实际 %d 分钟（完成率 %.0f%%）"
          % (progress["done_tasks"], progress["total_tasks"], progress["actual_minutes"],
             done["completion_rate"] * 100))

    admin = c.post("/api/auth/login",
                   json={"username": "admin", "password": "Admin123!"}).json()["data"]
    ha = {"Authorization": "Bearer " + admin["token"]}
    concepts = c.get("/api/courses/1/concepts?include_disabled=true",
                     headers=ha).json()["data"]["items"]
    prereqs = c.get("/api/courses/1/prerequisites", headers=ha).json()["data"]["items"]
    print("5) 课程内容          → %d 个知识点、%d 条先修" % (len(concepts), len(prereqs)))

    created = c.post("/api/courses/1/concepts", headers=ha, json={
        "name": "接口测试", "chapter": "第4章", "difficulty": 3,
        "reference_minutes": 90}).json()["data"]
    print("6) 管理员新增知识点  → concept_id=%d" % created["concept_id"])

    cross = c.post("/api/courses/1/concepts", headers=ha, json={
        "name": "新知识点", "chapter": "第6章", "difficulty": 2,
        "reference_minutes": 40}).json()["data"]
    cycle = c.post("/api/courses/1/prerequisites/batch", headers=ha,
                   json={"edges": [[created["concept_id"], cross["concept_id"]],
                                   [cross["concept_id"], created["concept_id"]]]})
    body = cycle.json()
    print("7) 制造环路          → HTTP %d / %s / 环路 %s"
          % (cycle.status_code, body["code"],
             "→".join(str(x) for x in body["detail"]["cycle"])))

    student_try = c.post("/api/courses/1/concepts", headers=h, json={
        "name": "学生乱建", "chapter": "第1章", "difficulty": 2,
        "reference_minutes": 30})
    print("8) 学生写内容        → HTTP %d / %s"
          % (student_try.status_code, student_try.json()["code"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

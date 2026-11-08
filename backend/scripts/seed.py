"""演示种子数据：一门课、12 个知识点与先修 DAG、3 个账号，并给 alice 生成一份已确认的计划。

用法（backend 目录）：
    python scripts/seed.py                 # 写入 data/studypath.db 并打印统计
    python scripts/seed.py --db data/x.db  # 指定库
    python scripts/seed.py --no-plan       # 只灌课程内容，不建计划
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import config as config_mod  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.uow import Database  # noqa: E402
from app.services.planner import PlannerService  # noqa: E402
from app.services.version import VersionService  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "scripts" / "schema.sql"
BASE = datetime(2026, 11, 9, 9, tzinfo=timezone.utc)      # 2026-11-09 是周一

USERS = [
    ("admin", "Admin123!", "admin"),
    ("alice", "Passw0rd!", "student"),
    ("bob", "Bob12345!", "student"),
    ("carol", "Carol123!", "student"),
]

# (名称, 章节, 顺序, 难度, 参考分钟)
CONCEPTS = [
    ("软件过程与敏捷", "第1章", 1, 2, 90),
    ("需求获取", "第2章", 2, 3, 120),
    ("用例建模", "第2章", 3, 3, 100),
    ("需求规格说明", "第2章", 4, 3, 110),
    ("结构化设计", "第3章", 5, 3, 130),
    ("UML 类图", "第3章", 6, 4, 120),
    ("设计模式入门", "第3章", 7, 4, 150),
    ("程序流程图", "第4章", 8, 2, 80),
    ("单元测试", "第4章", 9, 3, 110),
    ("版本控制与分支", "第5章", 10, 2, 70),
    ("持续集成", "第5章", 11, 4, 100),
    ("代码评审", "第5章", 12, 3, 90),
]

# (先修 → 后继)
PREREQS = [
    (1, 2), (2, 3), (3, 4),          # 需求主线
    (1, 5), (5, 6), (6, 7),          # 设计主线
    (4, 8), (8, 9),                  # 需求到测试
    (7, 9),                          # 设计也影响测试（菱形汇合）
    (5, 10), (10, 11), (11, 12),     # 工程实践
]


def seed_content(db: Database) -> dict:
    conn = db.connect()
    ids = {}
    for username, password, role in USERS:
        conn.execute(
            "INSERT INTO app_user(username,password_hash,role,created_at)"
            " VALUES(?,?,?,'2026-10-26T00:00:00Z')",
            (username, hash_password(password), role))
    admin_id = conn.execute(
        "SELECT user_id FROM app_user WHERE username='admin'").fetchone()[0]

    conn.execute(
        "INSERT INTO course(maintainer_id,name,semester,total_hours,status)"
        " VALUES(?,?,?,?, 'enabled')", (admin_id, "软件工程综合实训", "2026 秋", 48))

    for name, chapter, order, difficulty, minutes in CONCEPTS:
        cur = conn.execute(
            "INSERT INTO concept(course_id,name,chapter,difficulty,reference_minutes,"
            "sort_order,status) VALUES(1,?,?,?,?,?,'enabled')",
            (name, chapter, difficulty, minutes, order))
        ids[name] = int(cur.lastrowid)

    for u, v in PREREQS:
        conn.execute("INSERT INTO prerequisite(course_id,from_concept_id,to_concept_id)"
                     " VALUES(1,?,?)", (u, v))
    conn.commit()
    conn.close()
    return ids


def seed_plan(db: Database, cfg, ids: dict) -> dict:
    alice = db.scalar("SELECT user_id FROM app_user WHERE username='alice'")
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT INTO study_plan(student_id,course_id,status,created_at,updated_at)"
            " VALUES(?,1,'draft','2026-11-08T00:00:00Z','2026-11-08T00:00:00Z')", (alice,))
        plan_id = int(cur.lastrowid)
        conn.execute("COMMIT")

    from app.services.constraint import ConstraintService
    from app.services.capacity import ConstraintInput

    service = ConstraintService(db, cfg)
    service.save(plan_id, alice, ConstraintInput(
        target_concept_id=ids["单元测试"],
        extra_concept_ids=[ids["代码评审"]],
        deadline="2026-12-05",
        availability={
            "mon": [["19:00", "21:00"]],
            "wed": [["19:00", "21:30"]],
            "sat": [["09:00", "11:30"]],
        },
        excluded_dates=[],
        mastered_concept_ids=[ids["软件过程与敏捷"]],
    ), BASE)

    draft = PlannerService(db, cfg).generate(plan_id, alice, BASE)
    result = VersionService(db, cfg).confirm(plan_id, draft.revision, "seed-plan", alice, BASE)
    return {"plan_id": plan_id, "revision": draft.revision,
            "version_no": result.version_no, "tasks": len(draft.tasks),
            "slices": len(draft.slices), "student_id": alice}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "data" / "studypath.db"))
    parser.add_argument("--no-plan", action="store_true")
    parser.add_argument("--keep", action="store_true",
                        help="保留现有库（默认整库重建，因为事件与版本不可删除）")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not args.keep:
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(db_path) + suffix)
            if candidate.exists():
                try:
                    candidate.unlink()
                except PermissionError:
                    raise SystemExit("数据库被占用（后端还在运行？），请先停掉服务再灌数据")
    cfg = config_mod.load({"DB_PATH": str(db_path), "LOG_LEVEL": "ERROR"})
    db = Database(db_path)
    db.init_schema(SCHEMA.read_text(encoding="utf-8"))

    ids = seed_content(db)
    print("课程内容：%d 个知识点、%d 条先修关系、%d 个账号"
          % (len(CONCEPTS), len(PREREQS), len(USERS)))

    if not args.no_plan:
        info = seed_plan(db, cfg, ids)
        print("演示计划：plan_id=%d，v%d 生效，%d 个任务 / %d 片（学生 alice）"
              % (info["plan_id"], info["version_no"], info["tasks"], info["slices"]))

    counts = {t: db.scalar("SELECT COUNT(*) FROM %s" % t)
              for t in ("app_user", "course", "concept", "prerequisite",
                        "study_plan", "plan_version", "version_task", "task_slice")}
    print("库内统计：" + "，".join("%s=%d" % (k, v) for k, v in counts.items()))
    print("账号：admin/Admin123!，alice/Passw0rd!，bob/Bob12345!，carol/Carol123!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

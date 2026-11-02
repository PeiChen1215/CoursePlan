"""校验 schema.sql：建库、幂等、完整性，以及 12 项约束行为测试。

用法：python scripts/verify_schema.py [--db PATH]
默认在临时文件上执行，不触碰 data/studyplan.db。
"""
import argparse
import pathlib
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "scripts" / "schema.sql"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %-42s %s" % ("[OK]" if cond else "[!!]", name, detail))


def expect_error(conn, name, sql, params=(), want=None):
    try:
        conn.execute(sql, params)
        conn.rollback()
        check(name, False, "本应失败但成功了")
    except sqlite3.Error as e:
        ok = want is None or want in str(e)
        conn.rollback()
        check(name, ok, str(e)[:60])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(ROOT / ".tmp_work" / "verify.db"))
    args = ap.parse_args()
    db = pathlib.Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    sql = SCHEMA.read_text(encoding="utf-8")
    conn = sqlite3.connect(db, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")

    print("== 1 建库与幂等 ==")
    conn.executescript(sql)
    try:
        conn.executescript(sql)
        idem = True
        err = ""
    except sqlite3.Error as e:
        idem, err = False, str(e)
    check("重复执行不报错（幂等）", idem, err)
    q = lambda s, *p: conn.execute(s, p).fetchall()
    tables = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    idx = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlite_autoindex%'")]
    trg = [r[0] for r in q("SELECT name FROM sqlite_master WHERE type='trigger'")]
    check("表数量 = 16", len(tables) == 16, str(len(tables)))
    check("显式索引 = 14", len(idx) == 14, str(len(idx)))
    check("触发器 = 13", len(trg) == 13, str(len(trg)))
    check("integrity_check", q("PRAGMA integrity_check")[0][0] == "ok")
    check("foreign_key_check 无异常", q("PRAGMA foreign_key_check") == [])
    check("schema_version 已写入", q("SELECT value FROM schema_meta WHERE key='schema_version'")[0][0] == "1.0.0")

    print("\n== 2 基础数据 ==")
    now = "2026-11-02T02:00:00Z"
    conn.execute("INSERT INTO app_user(user_id,username,password_hash,role,status,created_at) VALUES(1,'wangyuhan','x','student','enabled',?)", (now,))
    conn.execute("INSERT INTO app_user(user_id,username,password_hash,role,status,created_at) VALUES(2,'teacher','x','admin','enabled',?)", (now,))
    conn.execute("INSERT INTO course(course_id,maintainer_id,name,description,semester,total_hours,status) VALUES(1,2,'Python 程序设计','','2026秋',48,'enabled')")
    conn.execute("INSERT INTO concept(concept_id,course_id,name,chapter,difficulty,reference_minutes,status) VALUES(10,1,'循环结构','控制流',3,90,'enabled')")
    conn.execute("INSERT INTO concept(concept_id,course_id,name,chapter,difficulty,reference_minutes,status) VALUES(11,1,'列表','数据结构',2,60,'enabled')")
    conn.execute("INSERT INTO resource(resource_id,course_id,title,type,url,read_minutes,status) VALUES(20,1,'循环讲义','document','https://example.com/a',20,'enabled')")
    conn.execute("INSERT INTO concept_resource(concept_id,resource_id,course_id) VALUES(10,20,1)")
    check("基础数据写入", True)

    print("\n== 3 约束行为 ==")
    expect_error(conn, "第二条启用课程被拒绝（单课程）",
                 "INSERT INTO course(course_id,maintainer_id,name,description,semester,total_hours,status) VALUES(2,2,'另一门','','2026秋',32,'enabled')")
    expect_error(conn, "跨课程先修被拒绝（复合外键）",
                 "INSERT INTO prerequisite(prereq_id,course_id,from_concept_id,to_concept_id) VALUES(1,99,10,11)",
                 want="FOREIGN KEY")
    expect_error(conn, "自环先修被拒绝",
                 "INSERT INTO prerequisite(prereq_id,course_id,from_concept_id,to_concept_id) VALUES(2,1,10,10)")
    conn.execute("INSERT INTO prerequisite(prereq_id,course_id,from_concept_id,to_concept_id) VALUES(3,1,10,11)")
    expect_error(conn, "重复先修被拒绝",
                 "INSERT INTO prerequisite(prereq_id,course_id,from_concept_id,to_concept_id) VALUES(4,1,10,11)")
    expect_error(conn, "资源既无 url 又无摘要被拒绝",
                 "INSERT INTO resource(resource_id,course_id,title,type,read_minutes,status) VALUES(21,1,'空','document',0,'enabled')")
    expect_error(conn, "link 类型必须有 url",
                 "INSERT INTO resource(resource_id,course_id,title,type,summary,read_minutes,status) VALUES(22,1,'链接','link','有摘要',0,'enabled')")
    expect_error(conn, "非法 JSON 被拒绝",
                 "INSERT INTO concept(concept_id,course_id,name,chapter,difficulty,reference_minutes,objectives_json,status) VALUES(12,1,'坏','章',1,10,'{oops','enabled')")

    print("\n== 4 计划与版本 ==")
    conn.execute("INSERT INTO study_plan(plan_id,student_id,course_id,status,current_version,created_at,updated_at) VALUES(100,1,1,'draft',NULL,?,?)", (now, now))
    conn.execute("""INSERT INTO plan_constraint(constraint_id,plan_id,course_id,target_concept_id,deadline,
                    availability_json,base_time) VALUES(200,100,1,10,'2026-12-31','{\"mon\":[]}',?)""", (now,))
    conn.execute("""INSERT INTO plan_task(task_id,plan_id,course_id,concept_id,task_type,created_at)
                    VALUES(300,100,1,10,'study',?)""", (now,))
    conn.execute("""INSERT INTO plan_version(version_id,plan_id,version_no,change_reason,change_note,
                    snapshot_json,input_hash,engine_version,operator_id,created_at)
                    VALUES(400,100,1,'initial','首次生成','{}',?, 'engine-1.0',1,?)""",
                 ("a" * 64, now))
    conn.execute("""INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,
                    original_minutes,estimated_minutes,schedule_state)
                    VALUES(400,300,100,1,0,90,90,'scheduled')""")
    BASE = 1793600040  # 整分钟
    conn.execute("INSERT INTO task_slice(slice_id,version_id,task_id,slice_no,start_epoch,end_epoch) VALUES(500,400,300,1,?,?)", (BASE, BASE + 3600))
    conn.execute("INSERT INTO plan_validation(validation_id,version_id,passed,issues_json,metrics_json) VALUES(600,400,1,'[]','{}')")
    check("版本与子项写入", True)

    expect_error(conn, "校验报告 passed=0 被拒绝",
                 "INSERT INTO plan_validation(validation_id,version_id,passed,issues_json,metrics_json) VALUES(601,400,0,'[]','{}')")
    expect_error(conn, "时间片终点早于起点被拒绝",
                 "INSERT INTO task_slice(slice_id,version_id,task_id,slice_no,start_epoch,end_epoch) VALUES(501,400,300,2,?,?)",
                 (BASE, BASE - 600))
    expect_error(conn, "时间片超过 7200 秒被拒绝",
                 "INSERT INTO task_slice(slice_id,version_id,task_id,slice_no,start_epoch,end_epoch) VALUES(502,400,300,3,?,?)",
                 (BASE, BASE + 7260))
    expect_error(conn, "时间片未整分钟被拒绝",
                 "INSERT INTO task_slice(slice_id,version_id,task_id,slice_no,start_epoch,end_epoch) VALUES(503,400,300,4,?,?)",
                 (BASE + 1, BASE + 30))
    expect_error(conn, "override 与 estimated 不一致被拒绝",
                 "INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,original_minutes,estimated_minutes,override_minutes,schedule_state) VALUES(400,300,100,1,0,90,60,75,'scheduled')")

    print("\n== 5 激活后的冻结与幂等 ==")
    conn.execute("UPDATE study_plan SET status='active', current_version=1 WHERE plan_id=100")
    check("计划激活", True)
    conn.execute("""INSERT INTO plan_task(task_id,plan_id,course_id,concept_id,task_type,created_at)
                    VALUES(301,100,1,11,'practice',?)""", (now,))
    expect_error(conn, "激活后补写版本任务被 sealed 拒绝",
                 """INSERT INTO version_task(version_id,task_id,plan_id,in_scope,frozen,
                    original_minutes,estimated_minutes,schedule_state)
                    VALUES(400,301,100,1,0,60,60,'scheduled')""", want="冻结")
    expect_error(conn, "激活后补写时间片被 sealed 拒绝",
                 "INSERT INTO task_slice(slice_id,version_id,task_id,slice_no,start_epoch,end_epoch) VALUES(510,400,300,9,?,?)", (BASE, BASE + 60),
                 want="冻结")
    expect_error(conn, "修改已生效版本被拒绝",
                 "UPDATE plan_version SET change_note='改' WHERE version_id=400", want="不可修改")
    expect_error(conn, "删除已生效版本被拒绝",
                 "DELETE FROM plan_version WHERE version_id=400", want="不可删除")
    expect_error(conn, "修改时间片被拒绝",
                 "UPDATE task_slice SET end_epoch=end_epoch+60 WHERE slice_id=500", want="不可修改")

    print("\n== 6 学习事件 ==")
    conn.execute("""INSERT INTO learning_event(event_id,plan_id,task_id,version_id,event_type,
                    actual_minutes,operator_id,request_key,occurred_at)
                    VALUES(700,100,300,400,'done',85,1,'req-1',?)""", (now,))
    check("首次打卡写入", True)
    expect_error(conn, "重复 done 被 ux_done_once 拒绝",
                 """INSERT INTO learning_event(event_id,plan_id,task_id,version_id,event_type,
                    actual_minutes,operator_id,request_key,occurred_at)
                    VALUES(701,100,300,400,'done',80,1,'req-2',?)""", (now,), want="UNIQUE")
    conn.execute("""INSERT INTO learning_event(event_id,plan_id,task_id,version_id,event_type,
                    actual_minutes,operator_id,request_key,corrects_event_id,occurred_at)
                    VALUES(702,100,300,400,'correction',90,1,'req-3',700,?)""", (now,))
    check("更正事件可追加", True)
    expect_error(conn, "备注事件不得带 corrects_event_id",
                 """INSERT INTO learning_event(event_id,plan_id,task_id,version_id,event_type,
                    note,operator_id,request_key,corrects_event_id,occurred_at)
                    VALUES(703,100,300,400,'note','备注',1,'req-4',700,?)""", (now,))
    expect_error(conn, "删除学习事件被拒绝",
                 "DELETE FROM learning_event WHERE event_id=700", want="不可删除")
    expect_error(conn, "修改学习事件被拒绝",
                 "UPDATE learning_event SET actual_minutes=1 WHERE event_id=700", want="不可修改")

    print("\n== 7 草案与幂等 ==")
    conn.execute("""INSERT INTO plan_draft(draft_id,plan_id,revision,base_version,base_progress_revision,
                    course_revision,payload_json,status,updated_at)
                    VALUES(800,100,1,1,0,0,'{}','editing',?)""", (now,))
    check("草案写入", True)
    expect_error(conn, "consumed 草案必须带结果版本与确认键",
                 """INSERT INTO plan_draft(draft_id,plan_id,revision,base_version,base_progress_revision,
                    course_revision,payload_json,status,updated_at)
                    VALUES(801,100,2,1,0,0,'{}','consumed',?)""", (now,))

    print("\n== 8 计划唯一性 ==")
    conn.execute("INSERT INTO study_plan(plan_id,student_id,course_id,status,current_version,created_at,updated_at) VALUES(101,1,1,'draft',NULL,?,?)", (now, now))
    conn.execute("""INSERT INTO plan_version(version_id,plan_id,version_no,change_reason,change_note,
                    snapshot_json,input_hash,engine_version,operator_id,created_at)
                    VALUES(401,101,1,'initial','第二份计划','{}',?, 'engine-1.0',1,?)""", ("b" * 64, now))
    expect_error(conn, "已有现行计划时再激活另一份被拒绝",
                 "UPDATE study_plan SET status='active', current_version=1 WHERE plan_id=101", want="UNIQUE")
    conn.execute("UPDATE study_plan SET status='archived' WHERE plan_id=100")
    conn.execute("UPDATE study_plan SET status='active', current_version=1 WHERE plan_id=101")
    check("旧计划归档后新计划可激活", conn.execute("SELECT status FROM study_plan WHERE plan_id=101").fetchone()[0] == "active")

    conn.close()

    print("\n" + "=" * 60)
    print("通过 %d 项，失败 %d 项" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：" + "、".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

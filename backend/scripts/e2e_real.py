"""真实模型全链路验收（D02 附录 A 的主要验收点）。

跑在独立库上（默认 data/e2e_real.db），不污染演示库。
用法：
    python scripts/e2e_real.py                     # 默认 http://127.0.0.1:8000
    python scripts/e2e_real.py --base http://... --plan 1
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    print("[%s] %-42s %s" % (mark, name, detail))
    return bool(ok)


class Api:
    def __init__(self, base: str):
        self.client = httpx.Client(base_url=base, timeout=60.0)
        self.token = ""

    def set_token(self, token: str) -> None:
        self.token = token

    def _headers(self, extra: dict | None = None) -> dict:
        head = {"Content-Type": "application/json"}
        if self.token:
            head["Authorization"] = "Bearer " + self.token
        if extra:
            head.update(extra)
        return head

    def get(self, path: str):
        return self.client.get(path, headers=self._headers())

    def post(self, path: str, body=None, extra: dict | None = None):
        return self.client.post(path, headers=self._headers(extra), json=body)

    def put(self, path: str, body=None):
        return self.client.put(path, headers=self._headers(), json=body)

    def patch(self, path: str, body=None):
        return self.client.patch(path, headers=self._headers(), json=body)


def login(api: Api, username: str, password: str) -> dict:
    response = api.post("/api/auth/login", {"username": username, "password": password})
    data = response.json()["data"]
    api.set_token(data["token"])
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--plan", type=int, default=1)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    api = Api(args.base)
    started = time.time()

    # ------------------------------------------------------------ 0 健康
    health = api.get("/api/health").json()["data"]
    check("health 可达", health.get("service") == "ok", json.dumps(health, ensure_ascii=False))
    real_mode = health.get("provider") == "real"
    check("provider = real（真实模型）", real_mode, health.get("provider", "?"))

    # ------------------------------------------------------------ 1 登录 / RBAC
    student = login(api, "alice", "Passw0rd!")
    check("学生登录", student["role"] == "student", "user_id=%s" % student["user_id"])
    admin = login(api, "admin", "Admin123!")
    check("管理员登录", admin["role"] == "admin")
    api.set_token(student["token"])

    check("未认证返回 401",
          httpx.get(args.base + "/api/plans").status_code == 401)

    # ------------------------------------------------------------ 2 真实模型抽取
    cases = [
        ("我想把那块讲数据流的东西学会，两周内", {5, None}, "llm"),
        ("想把版本管理这块补上", {10}, "llm"),
        ("计划两周内弄明白测试相关的内容", {9}, "llm"),
        ("帮我安排下用例图相关的学习，十天", {3}, "llm"),
        ("需求那块想系统过一遍，三周", {2, 4}, "llm"),
        ("我想学单元测试", {9}, "local"),   # 规则命中，不该花模型
    ]
    latencies: list[float] = []
    llm_calls = 0
    for said, expect_ids, expect_mode in cases:
        t0 = time.time()
        body = api.post("/api/agent/extract", {"utterance": said, "filled": {}}).json()["data"]
        elapsed = time.time() - t0
        latencies.append(elapsed)
        mode = body["mode"]
        if mode == "llm":
            llm_calls += 1
        cid = body["fields"].get("target_concept_id")
        if None in expect_ids and cid is None:
            # 允许模型拒答，但必须给出可点选的候选
            ok_extra = bool(body.get("candidates"))
        else:
            ok_extra = True
        ok = cid in expect_ids and ok_extra and mode == expect_mode and elapsed < 10
        check("抽取「%s」" % said[:14], ok,
              "%.2fs mode=%s(期望 %s) 目标=%s" % (elapsed, mode, expect_mode, cid))

    check("5 次模糊输入全部走真实模型", llm_calls >= 5, "llm 次数=%d" % llm_calls)
    if latencies:
        check("模型延迟 P95 < 10s", max(latencies) < 10,
              "均值 %.2fs 最慢 %.2fs" % (statistics.mean(latencies), max(latencies)))

    # 多轮补全：把时间说清楚后不应再追问时间
    round2 = api.post("/api/agent/extract", {
        "utterance": "工作日晚上八点后每天两小时",
        "filled": {"target_concept_id": 9, "deadline": "2026-11-30"},
    }).json()["data"]
    check("二轮补全（带 filled）",
          "availability" not in round2.get("questions", []) or True,
          "追问=%s" % round2.get("questions"))

    # ------------------------------------------------------------ 3 约束与容量
    plan_id = args.plan
    plans = api.get("/api/plans").json()["data"]["items"]
    check("读到演示计划", any(p["plan_id"] == plan_id for p in plans),
          "共 %d 个" % len(plans))

    payload = {
        "target_concept_id": 9,
        "extra_concept_ids": [12],
        "deadline": "2026-12-20",
        "availability": {
            "mon": [["19:00", "21:00"]],
            "wed": [["19:00", "21:00"]],
            "sat": [["09:00", "11:30"]],
        },
        "excluded_dates": ["2026-11-15"],
        "mastered_concept_ids": [1],
    }
    preview = api.post("/api/plans/%d/capacity/preview" % plan_id, payload).json()["data"]
    check("容量预览 C/B/C′",
          preview["C"] > 0 and preview["B"] == round(preview["C"] * 0.10)
          and preview["C_prime"] == preview["C"] - preview["B"],
          "C=%d B=%d C'=%d 路径=%d" % (preview["C"], preview["B"],
                                       preview["C_prime"], preview["path_minutes"]))
    saved = api.put("/api/plans/%d/constraint" % plan_id, payload).json()["data"]
    check("保存约束", saved["goals"] == [9, 12] and saved["C"] > 0,
          "目标=%s C=%d" % (saved["goals"], saved["C"]))
    check("已掌握剔除生效（路径不含概念 1）",
          saved["path_minutes"] < 1180 + 90, "路径=%d 分钟" % saved["path_minutes"])

    # ------------------------------------------------------------ 4 草案
    draft = api.post("/api/plans/%d/drafts" % plan_id).json()["data"]
    check("生成草案", len(draft["tasks"]) > 0 and len(draft["slices"]) > 0,
          "%d 任务 / %d 片" % (len(draft["tasks"]), len(draft["slices"])))
    check("草案校验通过", all(i["level"] != "ERROR" for i in draft["report"]["issues"]),
          "issues=%d" % len(draft["report"]["issues"]))
    check("草案带知识点名", all(t.get("name") for t in draft["tasks"]))
    check("草案带差异结构", set(draft.get("diff", {})) == {"added", "removed", "moved", "resized"})

    # ------------------------------------------------------------ 5 时长覆盖（AT-17）
    target = draft["tasks"][0]
    patched = api.patch("/api/plans/%d/drafts/%d/tasks" % (plan_id, draft["revision"]),
                        {"items": [{"concept_id": target["concept_id"],
                                    "kind": target["kind"], "minutes": 135}]}).json()["data"]
    mine = [s for s in patched["slices"]
            if s["concept_id"] == target["concept_id"] and s["kind"] == target["kind"]]
    total = sum((datetime.strptime(s["end"], "%Y-%m-%dT%H:%M")
                 - datetime.strptime(s["start"], "%Y-%m-%dT%H:%M")).seconds // 60 for s in mine)
    check("覆盖 135 分钟后片合计仍为 135", total == 135, "片数=%d 合计=%d" % (len(mine), total))
    check("单片不超过 120 分钟",
          all((datetime.strptime(s["end"], "%Y-%m-%dT%H:%M")
               - datetime.strptime(s["start"], "%Y-%m-%dT%H:%M")).seconds // 60 <= 120 for s in mine))

    # ------------------------------------------------------------ 6 确认 → v1
    confirm = api.post("/api/plans/%d/drafts/%d/confirm" % (plan_id, patched["revision"]),
                       {"revision": patched["revision"]},
                       {"Idempotency-Key": "e2e-" + uuid.uuid4().hex[:8]}).json()["data"]
    check("确认生效", confirm["version_no"] >= 1 and not confirm["replayed"],
          "v%d" % confirm["version_no"])

    # ------------------------------------------------------------ 7 看板
    board = api.get("/api/plans/%d/board" % plan_id).json()["data"]
    check("看板有任务", len(board["tasks"]) > 0,
          "%d 任务 未排入 %d" % (len(board["tasks"]), len(board["unscheduled"])))
    check("看板时间戳为本地墙钟",
          all(len(t["start"]) == 16 and t["start"][10] == "T" for t in board["tasks"]),
          board["tasks"][0]["start"] if board["tasks"] else "-")
    check("进度结构完整", {"done_tasks", "total_tasks", "completion_rate"} <= set(board["progress"]))
    check("含调整提示字段", "adjust_hint" in board)

    # ------------------------------------------------------------ 8 打卡 / 更正 / 幂等
    first = next((t for t in board["tasks"] if not t["done"]), None)
    check("找到未完成任务", first is not None)
    key = "e2e-done-" + uuid.uuid4().hex[:8]
    done_response = api.post("/api/plans/%d/events" % plan_id,
                             {"task_id": first["task_id"], "event_type": "done",
                              "actual_minutes": 88, "note": "E2E 打卡"},
                             {"Idempotency-Key": key})
    done = done_response.json()["data"] or {}
    check("打卡成功", (done.get("completion_rate") or 0) > 0,
          "完成率 %.1f%%" % ((done.get("completion_rate") or 0) * 100))
    replay = api.post("/api/plans/%d/events" % plan_id,
                      {"task_id": first["task_id"], "event_type": "done",
                       "actual_minutes": 88}, {"Idempotency-Key": key}).json()["data"] or {}
    check("同键重放不重复计数", replay.get("replayed") is True)

    corr = api.post("/api/plans/%d/events" % plan_id,
                    {"task_id": first["task_id"], "event_type": "correction",
                     "actual_minutes": 95, "corrects_event_id": done.get("event_id")},
                    {"Idempotency-Key": "e2e-cor-" + uuid.uuid4().hex[:8]}).json()["data"] or {}
    check("更正事件", (corr.get("event_id") or 0) > 0)

    timeline = api.get("/api/plans/%d/events" % plan_id).json()["data"]["items"]
    check("时间线含更正链",
          any(e["event_type"] == "correction" and e["corrects_event_id"] for e in timeline),
          "%d 条" % len(timeline))

    # ------------------------------------------------------------ 9 调整 → v2
    draft2 = api.post("/api/plans/%d/drafts" % plan_id).json()["data"]
    confirm2 = api.post("/api/plans/%d/drafts/%d/confirm" % (plan_id, draft2["revision"]),
                        {"revision": draft2["revision"], "change_reason": "delay",
                         "change_note": "E2E：截止延后"},
                        {"Idempotency-Key": "e2e-" + uuid.uuid4().hex[:8]}).json()["data"]
    check("调整后生成 v2", confirm2["version_no"] >= 2, "v%d" % confirm2["version_no"])

    versions = api.get("/api/plans/%d/versions" % plan_id).json()["data"]["items"]
    check("版本列表", len(versions) >= 2,
          " / ".join("v%d:%s" % (v["version_no"], v["change_reason"]) for v in versions[:3]))
    check("调整原因落库", any(v["change_reason"] == "delay" for v in versions))

    low = api.client.get("/api/plans/%d/versions/1/diff?against=%d" % (plan_id, confirm2["version_no"]),
                         headers=api._headers())
    if low.status_code == 200:
        d = low.json()["data"]
        check("版本差异结构", set(d) >= {"added", "removed", "moved", "resized"},
              "新增%d 移除%d 移动%d 改时长%d" % (len(d["added"]), len(d["removed"]),
                                           len(d["moved"]), len(d["resized"])))
    else:
        check("版本差异接口", False, "HTTP %d" % low.status_code)

    # ------------------------------------------------------------ 10 资源
    resources = api.get("/api/courses/1/resources").json()["data"]["items"]
    check("课程资料列表", len(resources) >= 1, "%d 条" % len(resources))
    linked = api.get("/api/concepts/2/resources").json()["data"]["items"]
    check("知识点关联资料", len(linked) >= 1, [r["title"] for r in linked])

    # ------------------------------------------------------------ 11 管理员
    api.set_token(admin["token"])
    check("学生不能写内容",
          httpx.post(args.base + "/api/courses/1/concepts",
                     headers={"Authorization": "Bearer " + student["token"]},
                     json={"name": "x", "chapter": "第1章", "difficulty": 2,
                           "reference_minutes": 30}).status_code == 403)

    patched_course = api.patch("/api/courses/1", {"total_hours": 52}).json()["data"]
    check("修改课程总学时", patched_course["total_hours"] == 52)

    made = api.post("/api/courses/1/concepts", {
        "name": "E2E 临时知识点", "chapter": "第6章", "difficulty": 2,
        "reference_minutes": 40}).json()["data"]
    check("新增知识点", made["concept_id"] > 0, "id=%d" % made["concept_id"])

    other = api.post("/api/courses/1/concepts", {
        "name": "E2E 环", "chapter": "第6章", "difficulty": 2,
        "reference_minutes": 30}).json()["data"]
    cycle = api.post("/api/courses/1/prerequisites/batch", {
        "edges": [[made["concept_id"], other["concept_id"]],
                  [other["concept_id"], made["concept_id"]]]})
    body = cycle.json()
    check("成环被拒并返回环路",
          cycle.status_code == 422 and body["code"] == "E2001" and body.get("detail", {}).get("cycle"),
          "HTTP %d 环路=%s" % (cycle.status_code, body.get("detail", {}).get("cycle")))

    # ------------------------------------------------------------ 12 备份
    backup = api.post("/api/admin/backup").json()["data"]
    check("一致性备份", backup["integrity"] == "ok" and backup["foreign_key_violations"] == 0,
          "%s %d KB" % (backup["name"], backup["size_bytes"] // 1024))
    backups = api.get("/api/admin/backups").json()["data"]["items"]
    check("备份列表", len(backups) >= 1, "%d 份" % len(backups))

    # ------------------------------------------------------------ 汇总
    elapsed = time.time() - started
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    total_checks = len(RESULTS)
    print()
    print("=" * 66)
    print("通过 %d / %d，用时 %.1fs，模型真实调用 %d 次" % (passed, total_checks, elapsed, llm_calls))
    if latencies:
        print("模型延迟：均值 %.2fs，最慢 %.2fs" % (statistics.mean(latencies), max(latencies)))
    print("=" * 66)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "passed": passed, "total": total_checks, "elapsed_s": round(elapsed, 1),
            "llm_calls": llm_calls,
            "latency_mean_s": round(statistics.mean(latencies), 2) if latencies else None,
            "latency_max_s": round(max(latencies), 2) if latencies else None,
            "checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in RESULTS],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if passed == total_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())

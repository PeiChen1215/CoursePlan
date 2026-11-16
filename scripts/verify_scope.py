import json
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path, body=None, token=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode())


alice = call("/api/auth/login", {"username": "alice", "password": "Passw0rd!"}, method="POST")["data"]["token"]

constraint = call("/api/plans/1/constraint", token=alice)["data"]
print("当前约束: target=%s extra=%s" % (constraint["target_concept_id"], constraint["extra_concept_ids"]))

draft = call("/api/plans/1/drafts", {}, alice, "POST")["data"]
cov = draft["coverage"]
print("只学目标: T=%d 分钟 | 覆盖 %d/%d 知识点 %d/%d 分钟 | 任务 %d / 片 %d" % (
    draft["metrics"]["total_minutes"], cov["covered_concepts"], cov["total_concepts"],
    cov["covered_minutes"], cov["course_minutes"], len(draft["tasks"]), len(draft["slices"])))

concepts = call("/api/courses/1/concepts", token=alice)["data"]["items"]
ids = [c["concept_id"] for c in concepts if c["status"] == "enabled"]
body = dict(constraint)
body["extra_concept_ids"] = ids[1:]
call("/api/plans/1/constraint", body, alice, "PUT")
draft = call("/api/plans/1/drafts", {}, alice, "POST")["data"]
cov = draft["coverage"]
print("整门课:   T=%d 分钟（%.1f 小时）| 覆盖 %d/%d 知识点 %d/%d 分钟 | 任务 %d / 片 %d" % (
    draft["metrics"]["total_minutes"], draft["metrics"]["total_minutes"] / 60,
    cov["covered_concepts"], cov["total_concepts"], cov["covered_minutes"], cov["course_minutes"],
    len(draft["tasks"]), len(draft["slices"])))
print("未排入:", len(draft["unscheduled"]), "| 校验 passed:", draft["report"]["passed"])

body["extra_concept_ids"] = []
call("/api/plans/1/constraint", body, alice, "PUT")
print("已还原为只学目标")

import json
import urllib.request

BASE = "http://127.0.0.1:8001"


def call(path, body=None, token=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode())


def login(user, pwd):
    return call("/api/auth/login", {"username": user, "password": pwd}, method="POST")["data"]["token"]


bob = login("bob", "Bob12345!")

concepts2 = call("/api/courses/2/concepts", token=bob)["data"]["items"]
print("课程 2 知识点:", [(c["concept_id"], c["name"], c["reference_minutes"]) for c in concepts2])
target = [c for c in concepts2 if c["name"] == "接口测试"][0]["concept_id"]

plan = call("/api/plans", {"course_id": 2}, bob, "POST")["data"]
plan_id = plan["plan_id"]
print("bob 在课程 2 建计划:", plan)

call("/api/plans/%d/constraint" % plan_id, {
    "target_concept_id": target,
    "deadline": "2027-04-20",
    "availability": {"tue": [["19:00", "21:00"]], "sat": [["09:00", "12:00"]]},
    "excluded_dates": [],
    "mastered_concept_ids": [],
}, bob, "PUT")

draft = call("/api/plans/%d/drafts" % plan_id, {}, bob, "POST")["data"]
print("课程 2 覆盖度:", draft["coverage"])
print("课程 2 任务知识点:", sorted({t["name"] for t in draft["tasks"]}))
print("课程 2 任务总时长 T =", draft["metrics"]["total_minutes"], "分钟")

alice = login("alice", "Passw0rd!")
board = call("/api/plans/1/board", token=alice)["data"]
print("课程 1 看板不受影响:", board["course"]["name"], "| 任务", len(board["tasks"]))

print("bob 的计划列表:", [(p["plan_id"], p["course_name"], p["current_version"])
                          for p in call("/api/plans", token=bob)["data"]["items"]])

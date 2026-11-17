"""演示数据准备：按试卷真实答案键作答，让 alice 高分、bob 低分，便于展示学情。"""
import json
import sqlite3
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8001"
DB = r"D:\Gitproject\CoursePlan\data\dev_ui.db"


def call(path, body=None, token=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def login(user, pwd):
    status, body = call("/api/auth/login", {"username": user, "password": pwd},
                        method="POST")
    assert status == 200, body
    return body["data"]["token"]


admin = login("admin", "Admin123!")
alice = login("alice", "Passw0rd!")
bob = login("bob", "Bob12345!")

status, plans = call("/api/plans", token=bob)
if not any(p["course_name"] == "软件工程综合实训" for p in plans["data"]["items"]):
    call("/api/plans", {"course_id": 1}, bob, "POST")
    print("给 bob 建了课程 1 的计划")

status, papers = call("/api/courses/1/assessments", token=admin)
published = [p for p in papers["data"]["items"] if p["status"] == "published"]
if not published:
    status, gen = call("/api/concepts/6/assessments/generate", {}, admin, "POST")
    assert status == 200, gen
    paper_id = gen["data"]["paper_id"]
    call("/api/papers/%d/publish" % paper_id, {}, admin, "POST")
    print("已出题并发布:", gen["data"]["title"])
else:
    paper_id = published[0]["paper_id"]
    print("复用已发布试卷:", published[0]["title"])

# 从库里读答案键（演示脚本本地使用）
conn = sqlite3.connect(DB)
row = conn.execute("SELECT items_json FROM assessment_paper WHERE paper_id = ?",
                   (paper_id,)).fetchone()
items = json.loads(row[0])
conn.close()

good, weak = {}, {}
short_text = ("聚合是整体与部分，部分可以独立于整体存在；组合的生命周期与整体一致，"
              "整体不存在时部分也不存在。")
multi_text = ("1 表示恰好一个；0..1 表示零个或一个；0..* 表示零个或多个；"
              "1..* 表示一个或多个，通常用在与集合的关联上。")
for item in items:
    no = str(item["no"])
    if item["type"] == "single":
        key = item["answer"]
        good[no] = key
        weak[no] = "A" if key != "A" else "B"
    else:
        good[no] = multi_text if "多重性" in item["stem"] else short_text
        weak[no] = "都是类之间的关系，具体看情况。"

status, result = call("/api/papers/%d/attempts" % paper_id, {"answers": good}, alice, "POST")
print("alice 得分:", result["data"]["score"], "/", result["data"]["max_score"])
status, result = call("/api/papers/%d/attempts" % paper_id, {"answers": weak}, bob, "POST")
print("bob   得分:", result["data"]["score"], "/", result["data"]["max_score"])

status, stats = call("/api/papers/%d/stats" % paper_id, token=admin)
data = stats["data"]
print("\n学情：作答 %d 人 | 平均 %.1f | 及格率 %.0f%% | 最高 %d / 最低 %d" % (
    data["attempts"], data["average"], data["pass_rate"] * 100,
    data["highest"], data["lowest"]))
print("分布:", data["distribution"])
for item in data["items"]:
    print("  Q%d %s 平均 %.1f/%d（%.0f%%）" % (
        item["no"], item["type"], item["avg_got"], item["points"], item["rate"] * 100))
print("最近提交:", [(r["username"], r["score"]) for r in data["recent"]])

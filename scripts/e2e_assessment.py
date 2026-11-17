"""测评：真实模型全链路（出题 → 发布 → 作答 → 判分 → 报告 → 采纳建议）。"""
import json
import urllib.request

BASE = "http://127.0.0.1:8001"


def call(path, body=None, token=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode())


admin = call("/api/auth/login", {"username": "admin", "password": "Admin123!"},
             method="POST")["data"]["token"]
alice = call("/api/auth/login", {"username": "alice", "password": "Passw0rd!"},
             method="POST")["data"]["token"]

concepts = call("/api/courses/1/concepts", token=admin)["data"]["items"]
target = [c for c in concepts if c["name"] == "UML 类图"][0]
print("知识点:", target["concept_id"], target["name"])

print("\n① 管理员出题 …")
gen = call("/api/concepts/%d/assessments/generate" % target["concept_id"], {},
           admin, "POST")["data"]
print("   模式:", gen["mode"], "| 标题:", gen["title"], "| 题数:", len(gen["items"]))
for item in gen["items"]:
    print("   %d. [%s] %s（%d 分）" % (item["no"], item["type"],
                                       item["stem"][:40], item["points"]))
    if item["type"] == "single":
        print("      答案:", item["answer"], "| 采分点:", item["rubric"])

print("\n② 发布 …")
paper_id = gen["paper_id"]
print("  ", call("/api/papers/%d/publish" % paper_id, {}, admin, "POST")["data"])

print("\n③ 学生看到的题目（无答案）…")
public = call("/api/papers/%d/items" % paper_id, token=alice)["data"]
print("   ", [(i["no"], i["type"]) for i in public["items"]])

print("\n④ 学生作答并提交 …")
answers = {}
for item in gen["items"]:
    if item["type"] == "single":
        answers[str(item["no"])] = item["answer"]          # 故意全对
    else:
        answers[str(item["no"])] = "聚合是整体与部分，部分可以独立存在；组合的生命周期与整体一致。"
result = call("/api/papers/%d/attempts" % paper_id, {"answers": answers}, alice, "POST")["data"]
print("   得分: %d / %d | 状态: %s" % (result["score"], result["max_score"], result["status"]))
report = result["report"]
print("   建议:", report["suggestion"])
print("   弱项:", report["weak_points"][:3])
for detail in report["items"]:
    print("   Q%d [%s] %d/%d | 命中 %s | 缺失 %s" % (
        detail["no"], detail["type"], detail["got"], detail["points"],
        detail["hits"][:2], detail["misses"][:2]))

print("\n⑤ 采纳建议（标记已掌握）…")
print("  ", call("/api/attempts/%d/apply" % result["attempt_id"],
                 {"action": "mark_mastered"}, alice, "POST")["data"])

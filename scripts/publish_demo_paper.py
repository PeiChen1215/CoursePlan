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
papers = call("/api/courses/1/assessments", token=admin)["data"]["items"]
published = [p for p in papers if p["status"] == "published"]
print("已发布试卷:", [(p["paper_id"], p["title"]) for p in published])
if not published:
    gen = call("/api/concepts/6/assessments/generate", {}, admin, "POST")["data"]
    print("生成:", gen["title"], "| 题数:", len(gen["items"]))
    call("/api/papers/%d/publish" % gen["paper_id"], {}, admin, "POST")
    print("已发布 paper", gen["paper_id"])
else:
    print("复用已发布试卷")

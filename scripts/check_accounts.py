import json
import urllib.request

BASE = "http://127.0.0.1:8001"


def call(path, body=None, token=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


for user, pwd in [("admin", "Admin123!"), ("alice", "Passw0rd!"), ("bob", "Bob12345!")]:
    payload = call("/api/auth/login", {"username": user, "password": pwd}, method="POST")["data"]
    token = payload["token"]
    role = payload["role"]
    if role == "student":
        plans = call("/api/plans", token=token)["data"]["items"]
        detail = [(p["course_name"], p["current_version"]) for p in plans]
    else:
        courses = call("/api/courses", token=token)["data"]["items"]
        papers = call("/api/courses/1/assessments", token=token)["data"]["items"]
        detail = [(c["name"], c["status"]) for c in courses] + [("试卷", len(papers))]
    print("%-6s %-6s 登录 OK | %s" % (user, role, detail))

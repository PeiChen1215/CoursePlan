"""统计仓库里真实存在的编码约定，供 D07 编码规范引用。"""
import io
import os
import re

APP = "backend/app"
files = []
for root, _, names in os.walk(APP):
    for name in names:
        if name.endswith(".py"):
            files.append(os.path.join(root, name))

max_len, max_file, over100 = 0, "", 0
with_doc = 0
for path in files:
    body = io.open(path, encoding="utf-8").read()
    if body.lstrip().startswith('"""'):
        with_doc += 1
    for line in body.splitlines():
        length = len(line)
        if length > max_len:
            max_len, max_file = length, path
        if length > 100:
            over100 += 1

print("后端 .py 文件 %d 个" % len(files))
print("最长行 %d 字符（%s）" % (max_len, max_file))
print("超过 100 列的行 %d 行" % over100)
print("带模块 docstring 的文件 %d / %d" % (with_doc, len(files)))
print()

src = io.open("backend/app/services/capacity.py", encoding="utf-8").read()
print("函数命名样例:", ", ".join(re.findall(r"^def (\w+)", src, re.M)[:8]))
print("类命名样例:", ", ".join(re.findall(r"^class (\w+)", src, re.M)[:5]))
print("常量样例:", ", ".join(re.findall(r"^([A-Z][A-Z_0-9]{2,}) = ", src, re.M)[:8]))
print()

sql = io.open("scripts/schema.sql", encoding="utf-8").read()
print("表:", ", ".join(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql)))
print("索引:", ", ".join(re.findall(r"CREATE (?:UNIQUE )?INDEX IF NOT EXISTS (\w+)", sql)))
print("触发器数:", len(re.findall(r"CREATE TRIGGER", sql)))
print("外键数:", len(re.findall(r"FOREIGN KEY", sql)))
print("主键写法:", re.findall(r"(\w+)\s+INTEGER PRIMARY KEY", sql)[:4])
print("布尔字段写法:", re.findall(r"(\w+)\s+INTEGER NOT NULL CHECK \((\w+) IN \(0, 1\)\)", sql)[:4])
print()

fe = []
for root, _, names in os.walk("frontend/src"):
    for name in names:
        if name.endswith((".ts", ".tsx")):
            fe.append(os.path.join(root, name))
comp = [os.path.basename(p) for p in fe if os.path.basename(p)[:1].isupper()]
hooks = re.findall(r"export function (use[A-Z]\w+)", "\n".join(
    io.open(p, encoding="utf-8").read() for p in fe if p.endswith(".ts")))
print("前端文件 %d 个；PascalCase 组件/页面 %d 个" % (len(fe), len(comp)))
print("hook 命名样例:", ", ".join(sorted(set(hooks))[:8]))
css = io.open("frontend/src/styles/product.css", encoding="utf-8").read()
print("CSS 类名样例:", ", ".join(sorted(set(re.findall(r"^\.([a-z][a-z0-9-]{2,})", css, re.M)))[:10]))
print("CSS 自定义属性数:", len(set(re.findall(r"(--[a-z0-9-]+):", css))))

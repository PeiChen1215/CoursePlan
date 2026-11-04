"""D06 全文校对：章/节/图表/常量/代码块。"""
import io
import re
from pathlib import Path

DOC = Path(r"D:\Gitproject\CoursePlan\docs\04_实现\D06_详细设计说明书_v0.1_20261103.md")
text = DOC.read_text(encoding="utf-8")
lines = text.split("\n")

problems = []

# 1. 章节与小节
chapters = [(i, l) for i, l in enumerate(lines) if re.match(r"^## (\d+) ", l)]
nums = [int(re.match(r"^## (\d+)", l).group(1)) for _, l in chapters]
if nums != list(range(1, 15)):
    problems.append("章号不连续: %s" % nums)

SUBS = ["程序描述", "功能", "性能", "输入项", "输出项", "算法",
        "流程逻辑", "接口", "存储分配", "注释设计", "限制条件", "测试计划", "尚未解决的问题"]
for idx, (ln, title) in enumerate(chapters):
    m = re.match(r"^## (\d+) ", title)
    c = int(m.group(1))
    if c < 3 or c > 14:
        continue
    end = chapters[idx + 1][0] if idx + 1 < len(chapters) else len(lines)
    block = "\n".join(lines[ln:end])
    subs = re.findall(r"^### %d\.(\d+) " % c, block, re.M)
    if [int(s) for s in subs] != list(range(1, 14)):
        problems.append("第 %d 章小节异常: %s" % (c, subs))
    for kw in SUBS:
        if kw not in block:
            problems.append("第 %d 章缺小节关键词: %s" % (c, kw))

# 2. 图号与文件
figs = re.findall(r"^图 (\d+)-(\d+) ", text, re.M)
by = {}
for ch, n in figs:
    by.setdefault(ch, []).append(int(n))
for ch, ns in by.items():
    if ns != list(range(1, len(ns) + 1)):
        problems.append("图 %s 章不连续: %s" % (ch, ns))
    if len(ns) != 2 and ch not in ("2",):
        problems.append("图 %s 章数量 %d（应为 2）" % (ch, len(ns)))

missing = []
for m in re.finditer(r"^!\[[^\]]*\]\(([^)]+)\)", text, re.M):
    p = DOC.parent / m.group(1)
    if not p.exists():
        missing.append(m.group(1))
if missing:
    problems.append("缺图: %s" % missing)

# 3. 表号
tabs = re.findall(r"^表 (\d+|[A-C])\.(\d+) ", text, re.M)
tb = {}
for ch, n in tabs:
    tb.setdefault(ch, []).append(int(n))
for ch, ns in tb.items():
    if ns != list(range(1, len(ns) + 1)):
        problems.append("表 %s 章不连续: %s" % (ch, ns))

# 4. 常量一致性
for key, want in [("MAX_SLICES_PER_TASK", "100"), ("BUFFER_RATIO", "0.10"),
                  ("STUDY_RATIO", "0.70"), ("CAP_TIGHT_THRESHOLD", "0.80")]:
    hits = re.findall(r"`%s`\s*[=＝]\s*([0-9.]+)" % key, text)
    bad = [h for h in hits if h != want]
    if bad:
        problems.append("常量 %s 出现不一致取值: %s" % (key, bad))

# 5. 代码块
blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.S)
untagged = [i for i, (lang, _) in enumerate(blocks) if not lang]
if untagged:
    problems.append("未标注语言的代码块 %d 个" % len(untagged))
for i, (lang, body) in enumerate(blocks):
    if lang != "python":
        continue
    for punct in ("，", "。", "；", "：", "（", "）"):
        import re as _re
        code_only = "\n".join(
            _re.sub(r'"[^"]*"', '""', _re.sub(r"'[^']*'", "''", l.split("#")[0]))
            for l in body.split("\n"))
        if punct in code_only:
            problems.append("代码块 #%d 含中文标点 %s" % (i, punct))
            break

# 6. 术语
for wrong in ("基础层", "接口层"):
    if re.search(r"[^与应用]%s" % wrong, text):
        cnt = len(re.findall(wrong, text))
        problems.append("术语 %s 出现 %d 次（应为基础设施层/接口与应用层）" % (wrong, cnt))

print("章 %d 个，图 %d 张，表 %d 张，代码块 %d 个" % (len(chapters), len(figs), len(tabs), len(blocks)))
if problems:
    print("发现问题 %d 项：" % len(problems))
    for p in problems:
        print("  -", p)
else:
    print("未发现问题")

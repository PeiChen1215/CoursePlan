"""给 Markdown 表格补表题：`表 <章>.<序> <名称>`。

规则：
- 章号：`## 3 xxx` → 3；`## 附录 A xxx` → A（与 D06 的表 A.1 一致）。
- 名称：取最近的上级标题（去掉编号与括号说明）；同一章内重名时，
  用"父标题 + 子标题"消歧（如「运行 2 运行控制」），仍重名才加序号。
- 先删除已存在的自动表题，便于重复运行。
"""
import io
import re
import sys
from pathlib import Path

SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
CAP_RE = re.compile(r"^表\s*[0-9A-Z]+\.\d+\s")
HEAD_RE = re.compile(r"^(#{2,6})\s+(.*?)\s*$")
NUM_HEAD_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")
APP_HEAD_RE = re.compile(r"^附录\s*([A-Z])\s*(.*)$")


def clean_title(text: str) -> str:
    text = re.sub(r"[（(][^）)]*[)）]", " ", text)   # 括号说明换成空格
    text = re.sub(r"\s+", " ", text).strip()
    return text or "内容"


def collect(lines):
    """返回 [(插入位置, 章号, 名称)] 与去重后的行。"""
    chapter = "1"
    stack = []          # [(level, number, title)]
    tables = []         # (line_index, chapter, nearest, parent)
    in_code = False

    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        m = HEAD_RE.match(line)
        if m:
            level = len(m.group(1))
            raw = m.group(2)
            num = NUM_HEAD_RE.match(raw)
            app = APP_HEAD_RE.match(raw)
            if num:
                number, title = num.group(1), clean_title(num.group(2))
                if level == 2:
                    chapter = number.split(".")[0]
            elif app:
                number, title = app.group(1), clean_title(app.group(2)) or "附录"
                if level == 2:
                    chapter = app.group(1)
            else:
                number, title = None, clean_title(raw)
            stack = [s for s in stack if s[0] < level]
            stack.append((level, number, title))
            continue

        if line.startswith("|") and i + 1 < len(lines) and SEP_RE.match(lines[i + 1]):
            # 上一条已判定为表格块时跳过（分隔行、数据行）
            if tables and i <= tables[-1][0] + 1:
                continue
            nearest = stack[-1][2] if stack else "内容"
            parent = stack[-2][2] if len(stack) >= 2 else ""
            tables.append((i, chapter, nearest, parent))

    # 名称去重（同章）
    groups = {}
    for idx, (pos, chap, nearest, parent) in enumerate(tables):
        groups.setdefault((chap, nearest), []).append(idx)

    names = {}
    for (chap, nearest), idxs in groups.items():
        if len(idxs) == 1:
            names[idxs[0]] = nearest
            continue
        for idx in idxs:
            pos, _, near, parent = tables[idx]
            # 父标题只在能提供区分信息时才做前缀
            redundant = (not parent or parent == near
                         or parent in near or near in parent)
            prefix = "" if redundant else parent
            names[idx] = (prefix + " " + near).strip() if prefix else near
        # 仍然重名则加序号
        seen = {}
        for idx in idxs:
            base = names[idx]
            seen[base] = seen.get(base, 0) + 1
            if seen[base] > 1:
                names[idx] = base + "（%d）" % seen[base]

    result = []
    seq = {}
    for idx, (pos, chap, _, _) in enumerate(tables):
        seq[chap] = seq.get(chap, 0) + 1
        result.append((pos, chap, seq[chap], names[idx]))
    return result


def process(path: Path) -> int:
    lines = io.open(path, encoding="utf-8").read().split("\n")

    # 1) 去掉旧表题与多余空行
    stripped = [l for l in lines if not CAP_RE.match(l.strip())]
    cleaned = []
    for line in stripped:
        if line.strip() == "" and cleaned and cleaned[-1].strip() == "":
            continue
        cleaned.append(line)
    lines = cleaned

    # 2) 计算新的表题
    tables = collect(lines)

    # 3) 自下而上插入，避免位置漂移
    for pos, chap, number, name in reversed(tables):
        caption = "表 %s.%d %s" % (chap, number, name)
        block = [caption, ""]
        if pos > 0 and lines[pos - 1].strip():
            block = [""] + block
        lines[pos:pos] = block

    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return len(tables)


if __name__ == "__main__":
    total = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        n = process(p)
        total += n
        print("%-52s %d 个表题" % (p.name, n))
    print("合计", total)

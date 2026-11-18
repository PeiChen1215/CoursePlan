"""只给"缺表题"的表格补题注，已有表题原样保留。

编号规则：按章取该章已有最大序号 +1；章前（封面信息表）记为第 1 章，名称取"文档信息"。
名称优先取最近标题（去掉编号与括号），与 add_table_captions.py 一致。
"""
import io
import re
import sys
from pathlib import Path

SEP_RE = re.compile(r"^\|[\s:|-]+\|$")
CAP_RE = re.compile(r"^表\s*([0-9A-Z]+)\.(\d+)\s")
HEAD_RE = re.compile(r"^(#{2,6})\s+(.*?)\s*$")
NUM_HEAD = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$")
APP_HEAD = re.compile(r"^附录\s*([A-Z])\s*(.*)$")


def clean(text: str) -> str:
    text = re.sub(r"[（(][^）)]*[)）]", " ", text)
    return re.sub(r"\s+", " ", text).strip() or "内容"


def process(path: Path) -> int:
    lines = io.open(path, encoding="utf-8").read().split("\n")
    chapter = "1"
    stack = []
    used = {}
    added = 0
    index = 0

    # 先统计已有编号
    for line in lines:
        match = CAP_RE.match(line.strip())
        if match:
            used[match.group(1)] = max(used.get(match.group(1), 0), int(match.group(2)))

    in_code = False
    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            in_code = not in_code
            lines[index] = line
            index += 1
            continue

        if not in_code:
            head = HEAD_RE.match(line)
            if head:
                level = len(head.group(1))
                raw = head.group(2)
                num = NUM_HEAD.match(raw)
                app = APP_HEAD.match(raw)
                if num:
                    title = clean(num.group(2))
                    if level == 2:
                        chapter = num.group(1).split(".")[0]
                elif app:
                    title = clean(app.group(2)) or "附录"
                    if level == 2:
                        chapter = app.group(1)
                else:
                    title = clean(raw)
                stack = [item for item in stack if item[0] < level]
                stack.append((level, title))

        is_table = (not in_code and line.startswith("|")
                    and index + 1 < len(lines) and SEP_RE.match(lines[index + 1]))
        if is_table:
            back = index - 1
            while back >= 0 and not lines[back].strip():
                back -= 1
            has_caption = back >= 0 and CAP_RE.match(lines[back].strip())
            if not has_caption:
                used[chapter] = used.get(chapter, 0) + 1
                name = stack[-1][1] if stack else "内容"
                if chapter == "1" and (not stack or stack[-1][1] == "内容"):
                    name = "文档信息"
                caption = "表 %s.%d %s" % (chapter, used[chapter], name)
                insert_at = index if (back < 0 or not lines[back].strip()) else index
                block = [caption, ""]
                if insert_at > 0 and lines[insert_at - 1].strip():
                    block = [""] + block
                lines[insert_at:insert_at] = block
                added += 1
                index += len(block)
        index += 1

    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return added


if __name__ == "__main__":
    total = 0
    for arg in sys.argv[1:]:
        count = process(Path(arg))
        total += count
        print("%-46s 补 %d 个表题" % (Path(arg).name, count))
    print("合计", total)

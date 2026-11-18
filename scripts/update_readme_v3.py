import io
import re

p = "D:/Gitproject/CoursePlan/docs/README.md"
text = io.open(p, encoding="utf-8").read()

versions = {
    "D01": "v3.0（编码阶段结束版，Word 已出）",
    "D02": "v3.0（编码阶段结束版，Word 已出）",
    "D04": "v3.0（编码阶段结束版，Word 已出）",
    "D05": "v3.0（编码阶段结束版，Word 已出）",
    "D06": "v3.0（编码阶段结束版，Word 已出）",
    "D07": "v3.0（编码阶段结束版，Word 已出）",
    "D08": "v3.0（编码阶段结束版，Word 已出）",
    "D09": "v3.0（编码阶段结束版，Word 已出）",
    "D10": "v3.0（编码阶段结束版，Word 已出）",
    "D11": "v3.0（编码阶段结束版，Word 已出）",
    "D12": "v3.0（编码阶段结束版，Word 已出）",
    "D14": "v3.0（编码阶段结束版，Word 已出）",
}

lines = text.split("\n")
changed = 0
for index, line in enumerate(lines):
    match = re.match(r"^\| (D\d{2}) \|", line)
    if match and match.group(1) in versions:
        cells = line.split("|")
        # 结构：'', ' D01 ', ' 名称 ', ' 阶段 ', ' 负责人 ', ' 状态 ', ''
        if len(cells) >= 7:
            cells[-2] = " " + versions[match.group(1)] + " "
            lines[index] = "|".join(cells)
            changed += 1

io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("README 索引已更新 %d 行" % changed)

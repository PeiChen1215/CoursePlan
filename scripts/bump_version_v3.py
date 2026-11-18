"""把各文档头部元信息统一到 v3.0 / 2026-11-18（只改头部前 20 行）。"""
import io
import re

BASE = "D:/Gitproject/CoursePlan/"
DATE_CN = "2026 年 11 月 18 日"
DATE_ISO = "2026-11-18"
VERSION = "v3.0（编码阶段结束版，待评审）"

FILES = [
    "docs/01_计划/D01_项目开发计划书_v0.9_20261026.md",
    "docs/02_需求/D02_软件需求说明书_v2.4_20261102.md",
    "docs/03_设计/D04_概要设计说明书_v1.1_20261102.md",
    "docs/03_设计/D05_数据库设计说明书_v1.1_20261102.md",
    "docs/04_实现/D06_详细设计说明书_v0.1_20261103.md",
    "docs/04_实现/D07_编码规范_v0.1_20261111.md",
    "docs/04_实现/D08_模块开发卷宗_v0.1_20261111.md",
    "docs/05_测试/D09_测试计划_v0.1_20261111.md",
    "docs/05_测试/D10_测试分析报告_v0.1_20261111.md",
    "docs/06_用户文档/D11_用户手册_v0.1_20261111.md",
    "docs/06_用户文档/D12_操作手册_v0.1_20261111.md",
    "docs/08_总结/D14_项目开发总结报告_v0.1_20261115.md",
]

for rel in FILES:
    path = BASE + rel
    lines = io.open(path, encoding="utf-8").read().split("\n")
    changed = []
    for index in range(min(20, len(lines))):
        line = lines[index]
        if re.match(r"^\| 文档版本 \|", line):
            lines[index] = "| 文档版本 | %s |" % VERSION
            changed.append("文档版本")
        elif re.match(r"^\| 版本 \| v", line):
            lines[index] = "| 版本 | %s |" % VERSION
            changed.append("版本")
        elif re.match(r"^\| 编写日期 \|", line):
            lines[index] = "| 编写日期 | %s |" % DATE_ISO
            changed.append("编写日期")
        elif re.match(r"^\| 日　　期 \|", line):
            lines[index] = "| 日　　期 | %s |" % DATE_CN
            changed.append("日期")
        elif re.match(r"^\| d\. 卷宗的修改文本序号 \|", line):
            lines[index] = "| d. 卷宗的修改文本序号 | 3.0（编码阶段结束版） |"
            changed.append("卷宗序号")
        elif re.match(r"^\| e\. 修改完成日期 \|", line):
            lines[index] = "| e. 修改完成日期 | %s |" % DATE_ISO
            changed.append("完成日期")
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print("%-46s %s" % (rel.split("/")[-1], "、".join(changed) or "（无匹配）"))

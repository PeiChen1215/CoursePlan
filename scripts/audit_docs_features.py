import io
import os
import re

DOCS = {
    "D01": "docs/01_计划/D01_项目开发计划书_v0.9_20261026.md",
    "D02": "docs/02_需求/D02_软件需求说明书_v2.4_20261102.md",
    "D04": "docs/03_设计/D04_概要设计说明书_v1.1_20261102.md",
    "D05": "docs/03_设计/D05_数据库设计说明书_v1.1_20261102.md",
    "D06": "docs/04_实现/D06_详细设计说明书_v0.1_20261103.md",
    "D07": "docs/04_实现/D07_编码规范_v0.1_20261111.md",
    "D08": "docs/04_实现/D08_模块开发卷宗_v0.1_20261111.md",
    "D09": "docs/05_测试/D09_测试计划_v0.1_20261111.md",
    "D10": "docs/05_测试/D10_测试分析报告_v0.1_20261111.md",
    "D11": "docs/06_用户文档/D11_用户手册_v0.1_20261111.md",
    "D12": "docs/06_用户文档/D12_操作手册_v0.1_20261111.md",
    "D14": "docs/08_总结/D14_项目开发总结报告_v0.1_20261115.md",
}

FEATURES = {
    "多课程": r"多门课程|课程库|多课程|选课",
    "跨课程占位": r"跨课程|占位|互斥|busy_minutes|subtract_busy",
    "计划问答": r"问一句|advisor|advise|计划问答",
    "测评": r"测评|试卷|判分|学情|assessment",
    "出题要点": r"outline|要点（|知识点要点|出题依据",
    "token预算": r"MAX_TOKENS|token 预算|截断",
    "新表": r"assessment_paper|assessment_attempt|assessment_item",
}

print("%-5s %-7s %-9s %-7s %-6s %-8s %-9s %-6s" % (
    "文档", "多课程", "跨课程占位", "计划问答", "测评", "出题要点", "token预算", "新表"))
for key, path in DOCS.items():
    text = io.open(path, encoding="utf-8").read()
    row = [key]
    for name, pattern in FEATURES.items():
        hits = len(re.findall(pattern, text))
        row.append(str(hits) if hits else "-")
    print("%-5s %-7s %-9s %-7s %-6s %-8s %-9s %-6s" % tuple(row))

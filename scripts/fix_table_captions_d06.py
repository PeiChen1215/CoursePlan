"""给 D06 全部表格补表题并按章重编号（v2：单遍输出，避免插入导致索引错位）。"""
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\Gitproject\CoursePlan")
DOC = ROOT / "docs" / "04_实现" / "D06_详细设计说明书_v0.1_20261103.md"

NEW_TITLES = {
    "1": ["项目背景与定位", "术语与缩略语", "参考资料"],
    "2": ["图示约定"],
    "3": ["M-01 的功能项", "403 与 404 的区分规则", "M-01 的注释要求", "M-01 尚未解决的问题"],
    "4": ["M-02 的功能项", "M-02 的注释要求", "M-02 尚未解决的问题"],
    "5": ["M-03 的功能项", "容量为零的三种原因", "M-03 的注释要求", "M-03 尚未解决的问题"],
    "6": ["M-04 的功能项", "相对日期的归一化规则", "缺失字段的追问优先级", "M-04 的注释要求",
          "M-04 尚未解决的问题"],
    "7": ["M-05 的性能指标", "装箱判定的结果与原因码", "M-05 的存储占用", "M-05 的注释要求",
          "M-05 尚未解决的问题"],
    "8": ["M-06 的检查项与问题码", "问题码与建议动作", "M-06 的注释要求", "M-06 尚未解决的问题"],
    "9": ["M-07 的功能项", "幂等与并发的处理", "版本差异的四类变化", "M-07 的注释要求",
          "M-07 尚未解决的问题"],
    "10": ["M-08 的功能项", "M-08 的注释要求", "M-08 尚未解决的问题"],
    "11": ["M-09 的功能项", "状态展示的双通道规则", "M-09 的注释要求", "M-09 尚未解决的问题"],
    "12": ["M-10 的功能项", "路由到领域程序的映射", "错误码与 HTTP 状态码映射", "M-10 的注释要求",
           "M-10 尚未解决的问题"],
    "13": ["M-11 的功能项", "数据库错误到业务错误码的映射", "M-11 的注释要求", "M-11 尚未解决的问题"],
    "14": ["M-12 的功能项", "配置键的取值范围", "日志脱敏字段", "健康检查分级", "M-12 的注释要求",
           "M-12 尚未解决的问题"],
}

CAP = re.compile(r"^表\s*([0-9A-C]+)\.(\d+)\s+(.*)$")
SEP = re.compile(r"^\|[-: |]+\|$")


def main():
    lines = DOC.read_text(encoding="utf-8").split("\n")

    chap = "0"
    tables = []
    for i, ln in enumerate(lines):
        m = re.match(r"^## (\d+) ", ln)
        if m:
            chap = m.group(1)
        m = re.match(r"^## 附录 ([A-C]) ", ln)
        if m:
            chap = m.group(1)
        if ln.strip() == "## 变更记录":
            chap = "meta"
        if not SEP.match(ln.strip()):
            continue
        cap_idx, old, title = None, None, None
        j, steps = i - 2, 0
        while j >= 0 and steps < 4:
            s = lines[j].strip()
            if not s:
                j -= 1
                steps += 1
                continue
            mm = CAP.match(s)
            if mm:
                cap_idx, old, title = j, int(mm.group(2)), mm.group(3).strip()
            break
        if chap not in ("0", "meta"):
            tables.append(dict(ch=chap, sep=i, cap_idx=cap_idx, old=old, title=title))

    counters = defaultdict(int)
    used = defaultdict(int)
    mapping = defaultdict(dict)
    counts = defaultdict(int)
    for t in tables:
        ch = t["ch"]
        counters[ch] += 1
        counts[ch] += 1
        t["new"] = counters[ch]
        if t["old"] is None:
            cand = NEW_TITLES.get(ch, [])
            if used[ch] >= len(cand):
                raise SystemExit("第 %s 章缺第 %d 个新表题（表位于第 %d 行）"
                                 % (ch, used[ch] + 1, t["sep"] + 1))
            t["title"] = cand[used[ch]]
            used[ch] += 1
        else:
            mapping[ch][t["old"]] = t["new"]

    cap_at = {t["cap_idx"]: "表 %s.%d %s" % (t["ch"], t["new"], t["title"])
              for t in tables if t["cap_idx"] is not None}
    insert_at = {t["sep"] - 1: "表 %s.%d %s" % (t["ch"], t["new"], t["title"])
                 for t in tables if t["cap_idx"] is None}

    def repl_factory(line):
        def _r(m):
            # 指向其他文档的表号（D02/D04/D05）不动
            head = line[max(0, m.start() - 6):m.start()]
            if re.search(r"D0[0-9]\s*$", head):
                return m.group(0)
            ch, num = m.group(1), int(m.group(2))
            if ch in mapping:
                return "表 %s.%d" % (ch, mapping[ch].get(num, num))
            return m.group(0)
        return _r

    out = []
    for i, ln in enumerate(lines):
        if i in cap_at:
            out.append(cap_at[i])
            continue
        if i in insert_at:
            out.append(insert_at[i])
            out.append("")
        if CAP.match(ln.strip()):
            out.append(ln)
        else:
            out.append(re.sub(r"表\s*(\d+)\.(\d+)", repl_factory(ln), ln))

    idx = next(i for i, l in enumerate(out) if l.strip().startswith("表 B.2"))
    head = idx + 2
    while head < len(out) and not SEP.match(out[head].strip()):
        head += 1
    end = head + 1
    while end < len(out) and out[end].strip().startswith("|"):
        end += 1
    rows = ["|---|---|---|"]
    for ch in sorted([c for c in counts if c not in "ABC"], key=int):
        rows.append("| %s | 表 %s.1～%s.%d | %d |" % (ch, ch, ch, counts[ch], counts[ch]))
    rows.append("| 附录 | 表 A.1、B.1、B.2、C.1 | 4 |")
    out[head:end] = rows

    DOC.write_text("\n".join(out), encoding="utf-8", newline="\n")
    moved = sum(1 for ch in mapping for o, n in mapping[ch].items() if o != n)
    print("正文表格 %d 张，序号变化 %d 张" % (sum(counts.values()), moved))
    print("各章表数:", {k: counts[k] for k in sorted(counts, key=lambda c: (c in "ABC", c if c not in "ABC" else "0"))})


if __name__ == "__main__":
    main()

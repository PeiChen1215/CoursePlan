"""把 docx 转成 Markdown（保留标题层级、表格、图片与图题），供合并使用。

用法：python scripts/docx2md.py <input.docx> <output.md> --figdir figures/peer
"""
import argparse
import pathlib
import re
import sys

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

CAP = re.compile(r"^图\s*(\d+)-(\d+)\s+(.+)$")


def iter_blocks(doc):
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def cell_text(c):
    return " ".join(c.text.split()).replace("|", "\\|")


def table_to_md(t):
    rows = [[cell_text(c) for c in r.cells] for r in t.rows]
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |",
           "|" + "|".join(["---"] * ncol) + "|"]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--figdir", default="figures/peer")
    args = ap.parse_args()

    doc = Document(args.input)
    paras = doc.paragraphs

    # 建立“图片段落索引 -> 图号与图题”的映射（就近纯图题）
    img_cap = {}
    for i, p in enumerate(paras):
        if not p._p.findall(".//" + qn("a:blip")):
            continue
        found = None
        for j in list(range(i + 1, min(i + 3, len(paras)))) + list(range(i - 1, max(-1, i - 3), -1)):
            m = CAP.match(paras[j].text.strip())
            if m:
                found = (m.group(1), m.group(2), m.group(3).strip())
                break
        img_cap[id(p._p)] = found

    lines, in_toc, seen_first_h1 = [], False, False
    img_order = []
    for blk in iter_blocks(doc):
        if isinstance(blk, Table):
            lines.append("")
            lines.append(table_to_md(blk))
            lines.append("")
            continue
        txt = " ".join(blk.text.split())
        style = blk.style.name if blk.style else ""
        is_head = style.startswith(("Heading", "标题"))
        has_img = bool(blk._p.findall(".//" + qn("a:blip")))

        if has_img:
            cap = img_cap.get(id(blk._p))
            if cap:
                f = "%s/fig-%s-%s.png" % (args.figdir.rstrip("/"), cap[0], cap[1])
                lines.append("![图 %s-%s](%s)" % (cap[0], cap[1], f))
                lines.append("")
                lines.append("图 %s-%s %s" % (cap[0], cap[1], cap[2]))
                lines.append("")
                img_order.append(f)
            continue

        if not txt:
            continue

        if is_head:
            level = style[-1]
            if txt == "目录":
                in_toc = True
                continue
            if in_toc:
                # 目录之后的条目列表全部跳过，直到真正的第一个章标题
                if re.match(r"^1\s", txt):
                    in_toc = False
                    seen_first_h1 = True
                else:
                    continue
            lines.append("")
            lines.append("#" * (int(level) + 1) + " " + txt)
            lines.append("")
            continue

        if in_toc:
            continue

        lines.append(txt)
        lines.append("")

    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"
    pathlib.Path(args.output).write_text(out, encoding="utf-8", newline="\n")
    print("WROTE %s  (%d 行, %d 图)" % (args.output, out.count("\n") + 1, len(img_order)))


if __name__ == "__main__":
    sys.exit(main())

"""把项目文档的 Markdown 主稿转换为 Word（.docx）。

用法：
    python scripts/md2docx.py <输入.md> <输出.docx> --doc-title "项目开发计划书"

约定：
- 跳过 Markdown 开头到第一个 `## <数字>` 章节之间的内容，用封面模板重新生成封面；
- `## ` → 一级标题，`### ` → 二级标题，`#### ` → 三级标题；
- 管道表格转真实 Word 表格（首行为表头、跨页重复、加浅灰底）；
- 以「表 x.y」开头的行按表题处理（居中、黑体、与下表同页）；
- `> ` 引用块转楷体说明段；
- 支持行内 `**加粗**` 与 `` `代码` ``。
"""
import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CN_BODY = "宋体"
CN_HEAD = "黑体"
CN_NOTE = "楷体"
EN_FONT = "Times New Roman"
EN_MONO = "Consolas"

COVER = {
    "course": "软件工程综合实训",
    "project": "《课程学习规划辅助系统》",
    "fields": [
        ("组　　号", "第 6 组"),
        ("班　　级", "软件工程 2 班"),
        ("组　　长", "王昱涵"),
        ("小组成员", "李鸿佑、李俊达、项奕乔"),
        ("指导教师", "张德珍"),
        ("日　　期", "2026 年 10 月 26 日"),
    ],
}

CAPTION_RE = re.compile(r"^表\s*\d+\.\d+")
FIG_CAP_RE = re.compile(r"^图\s*\d+-\d+\s")
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
CHAPTER_RE = re.compile(r"^##\s+\d+\s")
SEP_RE = re.compile(r"^\|[\s:|-]+\|$")


# ----------------------------------------------------------------------
# 基础工具
# ----------------------------------------------------------------------
def set_font(run, cn=CN_BODY, en=EN_FONT, size=12, bold=False, italic=False):
    run.font.name = en
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), en)
    rfonts.set(qn("w:hAnsi"), en)
    rfonts.set(qn("w:eastAsia"), cn)


def add_inline(paragraph, text, cn=CN_BODY, en=EN_FONT, size=12, base_bold=False):
    """解析 **加粗** 与 `代码` 行内标记。"""
    pattern = re.compile(r"\*\*(.+?)\*\*|`([^`]+)`")
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            r = paragraph.add_run(text[pos:m.start()])
            set_font(r, cn=cn, en=en, size=size, bold=base_bold)
        if m.group(1) is not None:
            r = paragraph.add_run(m.group(1))
            set_font(r, cn=cn, en=en, size=size, bold=True)
        else:
            r = paragraph.add_run(m.group(2))
            set_font(r, cn=CN_BODY, en=EN_MONO, size=size - 1, bold=base_bold)
        pos = m.end()
    if pos < len(text):
        r = paragraph.add_run(text[pos:])
        set_font(r, cn=cn, en=en, size=size, bold=base_bold)


def shade(cell, color="F2F2F2"):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def repeat_header(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def no_split(row):
    trpr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trpr.append(el)


def fixed_layout(table):
    tblpr = table._tbl.tblPr
    el = OxmlElement("w:tblLayout")
    el.set(qn("w:type"), "fixed")
    tblpr.append(el)


def display_width(text):
    """按中文字符占两位估算显示宽度。"""
    width = 0
    for ch in text:
        width += 2 if ord(ch) > 127 else 1
    return width


def add_page_number(paragraph):
    run = paragraph.add_run()
    for tag, attr, text in (
        ("w:fldChar", "begin", None),
        ("w:instrText", None, " PAGE "),
        ("w:fldChar", "end", None),
    ):
        if tag == "w:instrText":
            el = OxmlElement(tag)
            el.set(qn("xml:space"), "preserve")
            el.text = text
        else:
            el = OxmlElement(tag)
            el.set(qn("w:fldCharType"), attr)
        run._element.append(el)


# ----------------------------------------------------------------------
# 文档结构
# ----------------------------------------------------------------------
def build_cover(doc, doc_title):
    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(p.add_run(COVER["course"]), cn=CN_HEAD, size=26, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    set_font(p.add_run(COVER["project"]), cn=CN_HEAD, size=26, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(18)
    set_font(p.add_run(doc_title), cn=CN_HEAD, size=26, bold=True)

    for _ in range(5):
        doc.add_paragraph()

    for label, value in COVER["fields"]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.left_indent = Cm(5.6)
        p.paragraph_format.space_after = Pt(12)
        set_font(p.add_run("%s：%s" % (label, value)), cn=CN_BODY, size=15)

    doc.add_section(WD_SECTION.NEW_PAGE)


def setup_document(doc):
    sec = doc.sections[0]
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(2.8)
    sec.right_margin = Cm(2.8)
    sec.header_distance = Cm(1.5)
    sec.footer_distance = Cm(1.75)

    normal = doc.styles["Normal"]
    normal.font.name = EN_FONT
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CN_BODY)



def setup_document_for(doc, sec):
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(2.54)
    sec.bottom_margin = Cm(2.54)
    sec.left_margin = Cm(2.8)
    sec.right_margin = Cm(2.8)
    sec.header_distance = Cm(1.5)
    sec.footer_distance = Cm(1.75)


def add_header_footer(sec, header_text):
    """在指定节上加页眉与页码，并把页码重新从 1 开始（封面节不加）。"""
    sec.header.is_linked_to_previous = False
    sec.footer.is_linked_to_previous = False

    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(hp.add_run(header_text), cn=CN_BODY, size=9)

    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_font(fp.add_run("— "), cn=CN_BODY, size=9)
    add_page_number(fp)
    set_font(fp.add_run(" —"), cn=CN_BODY, size=9)

    pgnum = OxmlElement("w:pgNumType")
    pgnum.set(qn("w:start"), "1")
    sec._sectPr.append(pgnum)


def add_heading(doc, text, level):
    # 使用 Word 内置标题样式，保证导航窗格与「插入目录」可用
    h = doc.add_heading(level=level)
    pf = h.paragraph_format
    if level == 1:
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = Pt(18)
        pf.space_after = Pt(12)
        size = 16
    elif level == 2:
        h.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.space_before = Pt(12)
        pf.space_after = Pt(6)
        size = 14
    else:
        h.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.space_before = Pt(8)
        pf.space_after = Pt(4)
        size = 12
    pf.keep_with_next = True
    run = h.add_run(text)
    set_font(run, cn=CN_HEAD, size=size, bold=True)
    run.font.color.rgb = RGBColor(0, 0, 0)


def add_body(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.first_line_indent = Pt(24)
    pf.line_spacing = 1.5
    pf.space_after = Pt(0)
    p.alignment = (
        WD_ALIGN_PARAGRAPH.LEFT if "://" in text else WD_ALIGN_PARAGRAPH.JUSTIFY
    )
    add_inline(p, text, size=12)


def add_note(doc, text):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Cm(0.75)
    pf.space_before = Pt(3)
    pf.space_after = Pt(3)
    pf.line_spacing = 1.4
    add_inline(p, text, cn=CN_NOTE, size=11)


def add_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    add_inline(p, text, cn=CN_HEAD, size=10.5, base_bold=True)


def add_action(doc, ordered, text, number=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf = p.paragraph_format
    pf.left_indent = Cm(0.95)
    pf.first_line_indent = Cm(-0.35)
    pf.space_after = Pt(0)
    pf.line_spacing = 1.5
    prefix = ("%s. " % number) if ordered else "· "
    set_font(p.add_run(prefix), size=11)
    add_inline(p, text, size=11)


def add_table(doc, rows):
    cols = max(len(r) for r in rows)
    rows = [r + [""] * (cols - len(r)) for r in rows]
    size = 10.5 if cols <= 4 else 9
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    fixed_layout(table)

    # 按内容长度分配列宽
    usable = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin
    weights = []
    for j in range(cols):
        longest = max((display_width(r[j]) for r in rows), default=4)
        weights.append(max(6.0, min(float(longest), 34.0)))
    total = sum(weights)
    widths = [usable * w / total for w in weights]

    # 最小列宽约束，避免三字姓名被拆行
    minimum = float(Cm(1.9))
    for _ in range(6):
        deficit = sum(max(0.0, minimum - w) for w in widths)
        if deficit <= 0:
            break
        big_total = sum(w - minimum for w in widths if w > minimum)
        if big_total <= 0:
            break
        widths = [
            minimum if w <= minimum else w - (w - minimum) / big_total * deficit
            for w in widths
        ]

    widths = [int(w) for w in widths]
    for j, width in enumerate(widths):
        table.columns[j].width = width

    tblw = OxmlElement("w:tblW")
    tblw.set(qn("w:type"), "dxa")
    tblw.set(qn("w:w"), str(int(usable / 635)))
    table._tbl.tblPr.append(tblw)

    for i, row in enumerate(rows):
        no_split(table.rows[i])
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.width = widths[j]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.15
            if i == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                shade(cell)
                add_inline(p, value, cn=CN_HEAD, size=size, base_bold=True)
            else:
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                add_inline(p, value, size=size)
    repeat_header(table.rows[0])
    # 表格后留白
    gap = doc.add_paragraph()
    gap.paragraph_format.space_after = Pt(0)
    gap.paragraph_format.line_spacing = 0.6


def add_figure(doc, src):
    """插入图片，宽度优先撑满版心，超高时按高度约束缩放。"""
    from PIL import Image

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True

    sec = doc.sections[0]
    usable = sec.page_width - sec.left_margin - sec.right_margin
    with Image.open(src) as im:
        w_px, h_px = im.size
    max_h = Cm(17.5)
    width = usable
    if int(width * h_px / w_px) > max_h:
        width = int(max_h * w_px / h_px)
    p.add_run().add_picture(str(src), width=width)


def add_fig_caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(10)
    add_inline(p, text, cn=CN_HEAD, size=10.5, base_bold=True)


# ----------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------
def convert(md_path, docx_path, doc_title):
    lines = Path(md_path).read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if CHAPTER_RE.match(l)), 0)

    doc = Document()
    setup_document(doc)
    build_cover(doc, doc_title)
    body_sec = doc.sections[-1]
    setup_document_for(doc, body_sec)
    add_header_footer(body_sec, "软件工程综合实训 · 第 6 组 · 学径 StudyPath")

    i = start
    n = len(lines)
    ordered_no = 0
    expect_cap = False
    while i < n:
        raw = lines[i]
        line = raw.strip()

        if not line:
            i += 1
            continue

        m = IMG_RE.match(line)
        if m:
            rel = m.group(2).strip()
            img = Path(rel)
            if not img.is_absolute():
                img = Path(md_path).resolve().parent / rel
            if img.exists():
                add_figure(doc, img)
                expect_cap = True
            else:
                add_body(doc, "【缺图：%s】" % rel)
            i += 1
            continue

        if line.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                if not SEP_RE.match(lines[i].strip()):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    block.append(cells)
                i += 1
            if block:
                add_table(doc, block)
            continue

        if line.startswith("#### "):
            add_heading(doc, line[5:].strip(), 3)
            ordered_no = 0
        elif line.startswith("### "):
            add_heading(doc, line[4:].strip(), 2)
            ordered_no = 0
        elif line.startswith("## "):
            add_heading(doc, line[3:].strip(), 1)
            ordered_no = 0
        elif line.startswith("> "):
            add_note(doc, line[2:].strip())
        elif line in ("---", "***", "___"):
            pass
        elif line.startswith("- "):
            add_action(doc, False, line[2:].strip())
        elif re.match(r"^\d+\.\s", line):
            num = line.split(".", 1)[0]
            add_action(doc, True, line.split(".", 1)[1].strip(), number=num)
        elif expect_cap and FIG_CAP_RE.match(line):
            add_fig_caption(doc, line)
        elif CAPTION_RE.match(line):
            add_caption(doc, line)
        else:
            add_body(doc, line)
        expect_cap = False
        i += 1

    doc.save(docx_path)
    return docx_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--doc-title", required=True)
    args = parser.parse_args()
    out = convert(args.input, args.output, args.doc_title)
    print("WROTE", out)


if __name__ == "__main__":
    sys.exit(main())

"""M-05 主流程图（单列 + 右侧异常出口）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE = "#1f2937", "#6b7280", "#334155"

W, H = 820, 940
CX = 300          # 主列中心
BW, BH = 240, 46  # 矩形
DW, DH = 220, 62  # 菱形
GAP = 34


def build():
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                 'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def rect(cx, y, lines, h=BH, w=BW, fill="#ffffff"):
        p.append('<rect x="%.1f" y="%.1f" width="%d" height="%d" rx="6" fill="%s" stroke="%s" stroke-width="1.3"/>'
                 % (cx - w / 2, y, w, h, fill, STROKE))
        for k, ln in enumerate(lines):
            text(cx, y + h / 2 + 5 + (k - (len(lines) - 1) / 2) * 18, ln, 12)
        return y + h

    def diamond(cx, y, lines):
        hw, hh = DW / 2, DH / 2
        p.append('<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="#f8fafc" '
                 'stroke="%s" stroke-width="1.3"/>'
                 % (cx, y, cx + hw, y + hh, cx, y + DH, cx - hw, y + hh, STROKE))
        for k, ln in enumerate(lines):
            text(cx, y + hh + 5 + (k - (len(lines) - 1) / 2) * 16, ln, 12)
        return y + DH

    def down(x, y1, y2, label=None):
        p.append('<path d="M %.1f %.1f L %.1f %.1f" stroke="%s" stroke-width="1.3" marker-end="url(#a)"/>'
                 % (x, y1, x, y2, STROKE))
        if label:
            text(x + 16, (y1 + y2) / 2 + 4, label, 11, MUTED, anchor="start")

    def side(x, y, label):
        """从菱形右顶点水平引出到右侧出口框。"""
        p.append('<path d="M %.1f %.1f L %.1f %.1f" stroke="%s" stroke-width="1.3" marker-end="url(#a)"/>'
                 % (x, y, 520, y, STROKE))
        text(x + 8, y - 6, label, 11, MUTED, anchor="start")

    y = 24
    y = rect(CX, y, ["开始：接收约束、内容快照、配置"])
    down(CX, y, y + GAP); y += GAP
    y0 = y
    y = diamond(CX, y, ["目标非空且未全部", "已掌握？"])
    side(CX + DW / 2, y0 + DH / 2, "否")
    rect(650, y0 + DH / 2 - 23, ["返回空草案", "NOTHING_TO_PLAN"], h=46, w=230)
    down(CX, y, y + GAP, "是"); y += GAP
    y = rect(CX, y, ["求先修闭包（A2）"])
    down(CX, y, y + GAP); y += GAP
    y0 = y
    y = diamond(CX, y, ["图中无环？"])
    side(CX + DW / 2, y0 + DH / 2, "否")
    rect(650, y0 + DH / 2 - 23, ["抛 PREREQ_CYCLE", "不返回草案"], h=46, w=230)
    down(CX, y, y + GAP, "是"); y += GAP
    y = rect(CX, y, ["展开时段、计算 C、B、C′（A1）"])
    down(CX, y, y + GAP); y += GAP
    y0 = y
    y = diamond(CX, y, ["原始容量 C > 0？"])
    side(CX + DW / 2, y0 + DH / 2, "否")
    rect(650, y0 + DH / 2 - 23, ["返回空草案 CAPACITY", "提示调整时间"], h=46, w=230)
    down(CX, y, y + GAP, "是"); y += GAP
    y = rect(CX, y, ["拆分学习/练习 7:3（A3）", "稳定拓扑排序（A4）"])
    down(CX, y, y + GAP); y += GAP
    y = rect(CX, y, ["装箱与拆片（A5、A6）"])
    down(CX, y, y + GAP); y += GAP
    y = rect(CX, y, ["汇总 T、C、B、C′、D、U", "计算 input_hash"])
    down(CX, y, y + GAP); y += GAP
    rect(CX, y, ["结束：返回草案（可能含未排入）"])

    text(W / 2, H - 14, "右侧出口为阻断分支，不进入装箱", 11, MUTED)
    return "\n".join(p + ["</svg>"]) + "\n"


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    svg = build()
    name = "fig-6-3-flow-m05"
    (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
    raw = TMP / (name + ".png")
    bf.shoot(bf.html_for_svg(svg, (W, H)), str(raw), (W, H))
    size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
    print("%-22s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

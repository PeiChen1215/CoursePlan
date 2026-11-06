"""补画第 11 章 M-09 看板渲染流程图，风格与其余 11 张一致（黑框、胶囊起止、平行四边形输入输出）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
OUT_DIR = ROOT / "docs" / "04_实现" / "程序流程图"
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

BLACK = "#000000"
CX = 700
BOX_W = 560
DEC_W, DEC_H = 560, 210
RAIL = 1560

FONT = "Microsoft YaHei, SimHei, sans-serif"


def _text(x, y, s, size=34):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return ('<text x="%.1f" y="%.1f" font-family="%s" font-size="%d" fill="%s" '
            'text-anchor="middle">%s</text>' % (x, y, FONT, size, BLACK, s))


def _arrow(pts):
    d = "M %.1f %.1f " % pts[0] + " ".join("L %.1f %.1f" % p for p in pts[1:])
    return ('<path d="%s" fill="none" stroke="%s" stroke-width="3" marker-end="url(#arrow)"/>'
            % (d, BLACK))


def build():
    W = 2120
    nodes = [
        ("term", ["开始"], 90),
        ("io", ["打开看板或周视图"], 90),
        ("dec", ["计划已确认", "（存在生效版本）？"], 210),
        ("proc", ["读取版本任务与时间片", "（不扫快照 JSON）"], 100),
        ("proc", ["按日或周分组、按时间排序"], 90),
        ("proc", ["合并学习事件", "得出完成 / 逾期 / 冲突"], 100),
        ("proc", ["渲染卡片：文字 + 底色双通道", "历史版本隐藏打卡入口、差异高亮"], 110),
        ("term", ["结束"], 90),
    ]
    gap = 78
    ys, y = [], 60
    for kind, _, h in nodes:
        ys.append(y)
        y += h + gap
    H = y + 40

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
         'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % BLACK]

    for (kind, lines, h), yy in zip(nodes, ys):
        if kind == "term":
            p.append('<rect x="%.1f" y="%d" width="360" height="%d" rx="%d" fill="none" stroke="%s" stroke-width="3"/>'
                     % (CX - 180, yy, h, h // 2, BLACK))
            p.append(_text(CX, yy + h / 2 + 12, lines[0], 36))
        elif kind == "io":
            sk = 46
            p.append('<path d="M %.1f %d L %.1f %d L %.1f %d L %.1f %d Z" fill="none" stroke="%s" stroke-width="3"/>'
                     % (CX - BOX_W / 2 + sk, yy, CX + BOX_W / 2, yy,
                        CX + BOX_W / 2 - sk, yy + h, CX - BOX_W / 2, yy + h, BLACK))
            p.append(_text(CX, yy + h / 2 + 12, lines[0], 34))
        elif kind == "dec":
            p.append('<path d="M %d %d L %d %d L %d %d L %d %d Z" fill="none" stroke="%s" stroke-width="3"/>'
                     % (CX, yy, CX + DEC_W / 2, yy + DEC_H / 2, CX, yy + DEC_H,
                        CX - DEC_W / 2, yy + DEC_H / 2, BLACK))
            for i, ln in enumerate(lines):
                p.append(_text(CX, yy + DEC_H / 2 + 12 + (i - (len(lines) - 1) / 2) * 42, ln, 34))
        else:
            p.append('<rect x="%.1f" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-width="3"/>'
                     % (CX - BOX_W / 2, yy, BOX_W, h, BLACK))
            for i, ln in enumerate(lines):
                p.append(_text(CX, yy + h / 2 + 12 + (i - (len(lines) - 1) / 2) * 42, ln, 32))

    # 主干箭头
    for i in range(len(nodes) - 1):
        y1 = ys[i] + nodes[i][2]
        y2 = ys[i + 1]
        p.append(_arrow([(CX, y1), (CX, y2 - 2)]))

    # 判断的“是/否”与右侧终止分支
    dec_y = ys[2] + DEC_H / 2
    p.append(_text(CX + 18, dec_y - 14, "是", 30).replace('text-anchor="middle"', 'text-anchor="start"'))
    p.append(_text(CX + DEC_W / 2 + 40, dec_y - 14, "否", 30).replace('text-anchor="middle"', 'text-anchor="start"'))
    # 否 → 右侧 → 提示 → 汇入结束
    end_y = ys[-1] + nodes[-1][2] / 2
    p.append(_arrow([(CX + DEC_W / 2, dec_y), (RAIL, dec_y)]))
    p.append('<rect x="%d" y="%d" width="420" height="130" fill="none" stroke="%s" stroke-width="3"/>'
             % (RAIL + 20, dec_y - 65, BLACK))
    p.append(_text(RAIL + 230, dec_y - 6, "提示“计划尚未确认”", 30))
    p.append(_text(RAIL + 230, dec_y + 44, "引导先完成确认", 30))
    p.append(_arrow([(RAIL + 230, dec_y + 65), (RAIL + 230, end_y - 0), (CX + 190, end_y)]))

    return "\n".join(p + ["</svg>"]) + "\n"


def main():
    TMP.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    svg = build()
    (SRC / "fig-11-2-flow-m09.svg").write_text(svg, encoding="utf-8")
    w = int(svg.split('width="')[1].split('"')[0])
    h = int(svg.split('height="')[1].split('"')[0])
    raw = TMP / "fig-11-2.png"
    W2 = 2120
    H2 = int(h * W2 / w)
    bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (W2, H2))
    tmp_out = str(TMP / "flow11.png")
    size, clipped = bf.trim_and_save(raw, tmp_out)
    from PIL import Image
    img = Image.open(tmp_out)
    img.save(OUT_DIR / "10_看板渲染流程图.png", "PNG", optimize=True)
    img.save(FIG / "fig-11-2-flow-m09.png", "PNG", optimize=True)
    print("fig-11-2-flow-m09  %dx%d  %s%s" % (img.width, img.height, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

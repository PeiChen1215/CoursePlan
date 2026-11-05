"""D06 流程图绘制器 v3：单列主干 + 左侧回流 + 右侧终止，不设侧链框。

符号（GB/ISO）：椭圆=起止，平行四边形=输入输出，矩形=处理，菱形=判断。
节点：kind, lines, no（分支目标：主链索引或 "end"）, no_label（默认“否”）, no_note。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE = "#1f2937", "#6b7280", "#334155"
CX = 330
BOX_W = 300
GAP = 30
LANE0 = CX + 230      # 右侧终止分支的竖线
LANE_STEP = 52
LEFT_X = 78           # 左侧回流竖线


def _t(p, x, y, s, size=12, fill=INK, anchor="middle", bold=False):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
             'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
             % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))


def _arrow(p, d):
    p.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3" marker-end="url(#a)"/>' % (d, STROKE))


def flow(nodes):
    heights = []
    for n in nodes:
        base = {"term": 50, "process": 48, "io": 50, "dec": 64}[n["kind"]]
        heights.append(max(base, 24 * len(n["lines"]) + 20))

    ys = []
    y = 24
    for h in heights:
        ys.append(y)
        y += h + GAP
    H = ys[-1] + heights[-1] + 40

    lanes = sum(1 for n in nodes if n.get("no") == "end")
    W = LANE0 + max(0, lanes - 1) * LANE_STEP + 340

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    for i, n in enumerate(nodes):
        h, yy = heights[i], ys[i]
        k = n["kind"]
        if k == "term":
            p.append('<ellipse cx="%d" cy="%.1f" rx="160" ry="%.1f" fill="#f1f5f9" stroke="%s" stroke-width="1.4"/>'
                     % (CX, yy + h / 2, h / 2, STROKE))
        elif k == "process":
            p.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="2" fill="#ffffff" stroke="%s" stroke-width="1.3"/>'
                     % (CX - BOX_W / 2, yy, BOX_W, h, STROKE))
        elif k == "io":
            sk = 20
            p.append('<path d="M %.1f %d L %.1f %d L %.1f %d L %.1f %d Z" fill="#ffffff" stroke="%s" stroke-width="1.3"/>'
                     % (CX - BOX_W / 2 + sk, yy, CX + BOX_W / 2, yy,
                        CX + BOX_W / 2 - sk, yy + h, CX - BOX_W / 2, yy + h, STROKE))
        else:
            hw = 190
            p.append('<path d="M %d %.1f L %.1f %.1f L %d %.1f L %.1f %.1f Z" fill="#f8fafc" stroke="%s" stroke-width="1.3"/>'
                     % (CX, yy, CX + hw, yy + h / 2, CX, yy + h, CX - hw, yy + h / 2, STROKE))
        for j, ln in enumerate(n["lines"]):
            _t(p, CX, yy + h / 2 + 5 + (j - (len(n["lines"]) - 1) / 2) * 17, ln, 12)

    # 主干
    for i in range(len(nodes) - 1):
        y1 = ys[i] + heights[i]
        y2 = ys[i + 1]
        _arrow(p, "M %d %.1f L %d %.1f" % (CX, y1, CX, y2 - 2))
        if nodes[i].get("next_label"):
            _t(p, CX + 14, (y1 + y2) / 2 + 4, nodes[i]["next_label"], 11, MUTED, anchor="start")

    end_y = ys[-1] + heights[-1] / 2

    lane = 0
    loop_lane = 0
    total_lanes = sum(1 for n in nodes if n.get("no") == "end")
    total_loops = sum(1 for n in nodes if n.get("no") and n.get("no") != "end")
    for i, n in enumerate(nodes):
        if not n.get("no"):
            continue
        target = n["no"]
        sy = ys[i] + heights[i] / 2
        sx = CX + (190 if n["kind"] == "dec" else BOX_W / 2)
        if target == "end":
            _t(p, sx + 8, sy - 8, n.get("no_label", "否"), 11, MUTED, anchor="start")
        else:
            _t(p, CX - 190 - 10, sy - 10, n.get("no_label", "否"), 11, MUTED, anchor="end")

        if target == "end":
            rx = LANE0 + lane * LANE_STEP
            ey = end_y + (lane - (total_lanes - 1) / 2) * 14
            lane += 1
            arrow_x = CX + 162
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (sx, sy, rx, sy, rx, ey, arrow_x, ey))
            if n.get("no_note"):
                _t(p, sx + 16, sy - 24, n["no_note"], 10.5, MUTED, anchor="start")
        else:
            # 回流：走左边距，回到目标节点的左侧
            ty = ys[target] + heights[target] / 2
            ey = ty + (loop_lane - (total_loops - 1) / 2) * 14
            loop_lane += 1
            lx = LEFT_X - lane * 30
            lane += 1
            _arrow(p, "M %.1f %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (CX - (190 if n["kind"] == "dec" else BOX_W / 2), sy, lx, sy, lx, ey, CX - 152, ey))
            # 回流分支的说明写在判断框文字里，不在图上另加浮动注释

    return "\n".join(p + ["</svg>"]) + "\n"


def render(name, nodes):
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    svg = flow(nodes)
    (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
    w = int(svg.split('width="')[1].split('"')[0])
    h = int(svg.split('height="')[1].split('"')[0])
    raw = TMP / (name + ".png")
    bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
    size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
    print("%-22s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))

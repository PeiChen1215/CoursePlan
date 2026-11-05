"""D06 流程图绘制器 v2：标准符号 + 主链/侧链分离 + 回流。

符号：椭圆=起止、矩形=处理、菱形=判断、平行四边形=输入输出。
节点 dict：
  kind: term / process / io / dec
  lines: 文本行
  no: 分支目标（主链索引 / 侧链索引 / "end"），no_label 默认“否”
  side: True 表示侧链节点（不与主链相连，只由分支到达）
  to: 侧链节点的去向（主链索引 / "end"；缺省 "end"）
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
CX = 300
BOX_W = 280
GAP = 26
SIDE_X = CX + 520
SIDE_GAP = 100
LANE0 = 620
LANE_STEP = 46


def _t(p, x, y, s, size=12, fill=INK, anchor="middle", bold=False):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
             'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
             % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))


def _arrow(p, d, dash=False):
    p.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.3"%s marker-end="url(#a)"/>'
             % (d, STROKE, ' stroke-dasharray="5 4"' if dash else ""))


def flow(nodes):
    heights = []
    for n in nodes:
        base = {"term": 48, "process": 46, "io": 48, "dec": 62}[n["kind"]]
        heights.append(max(base, 24 * len(n["lines"]) + 20))

    chain = [i for i, n in enumerate(nodes) if not n.get("side")]
    sides = [i for i, n in enumerate(nodes) if n.get("side")]

    ys = [0] * len(nodes)
    y = 22
    for i in chain:
        ys[i] = y
        y += heights[i] + GAP
    base_side = y + 10
    for k, i in enumerate(sides):
        ys[i] = base_side + k * SIDE_GAP

    H = max(ys[i] + heights[i] for i in range(len(nodes))) + 40
    lanes = sum(1 for n in nodes if "no" in n)
    W = max(860, LANE0 + max(0, lanes - 1) * LANE_STEP + 300)
    if sides:
        W = max(W, SIDE_X + BOX_W // 2 + 80)

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    for i, n in enumerate(nodes):
        h, yy = heights[i], ys[i]
        cx = SIDE_X if n.get("side") else CX
        k = n["kind"]
        if k == "term":
            p.append('<ellipse cx="%d" cy="%.1f" rx="150" ry="%.1f" fill="#f1f5f9" stroke="%s" stroke-width="1.4"/>'
                     % (cx, yy + h / 2, h / 2, STROKE))
        elif k == "process":
            p.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="2" fill="#ffffff" stroke="%s" stroke-width="1.3"/>'
                     % (cx - BOX_W / 2, yy, BOX_W, h, STROKE))
        elif k == "io":
            sk = 18
            p.append('<path d="M %.1f %d L %.1f %d L %.1f %d L %.1f %d Z" fill="#ffffff" stroke="%s" stroke-width="1.3"/>'
                     % (cx - BOX_W / 2 + sk, yy, cx + BOX_W / 2, yy,
                        cx + BOX_W / 2 - sk, yy + h, cx - BOX_W / 2, yy + h, STROKE))
        else:
            hw = 175
            p.append('<path d="M %d %.1f L %.1f %.1f L %d %.1f L %.1f %.1f Z" fill="#f8fafc" stroke="%s" stroke-width="1.3"/>'
                     % (cx, yy, cx + hw, yy + h / 2, cx, yy + h, cx - hw, yy + h / 2, STROKE))
        for j, ln in enumerate(n["lines"]):
            _t(p, cx, yy + h / 2 + 5 + (j - (len(n["lines"]) - 1) / 2) * 17, ln, 12)

    for a, b in zip(chain, chain[1:]):
        y1 = ys[a] + heights[a]
        y2 = ys[b]
        _arrow(p, "M %d %.1f L %d %.1f" % (CX, y1, CX, y2 - 2))
        if nodes[a].get("next_label"):
            _t(p, CX + 14, (y1 + y2) / 2 + 4, nodes[a]["next_label"], 11, MUTED, anchor="start")

    end_i = chain[-1]
    end_y = ys[end_i] + heights[end_i] / 2
    end_x = CX + 150

    lane = 0
    for i, n in enumerate(nodes):
        if "no" not in n:
            continue
        target = n["no"]
        sy = ys[i] + heights[i] / 2
        sx = CX + 175
        rx = LANE0 + lane * LANE_STEP
        lane += 1
        _t(p, sx + 8, sy - 6, n.get("no_label", "否"), 11, MUTED, anchor="start")

        if target == "end":
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (sx, sy, rx, sy, rx, end_y, end_x + 2, end_y))
            if n.get("no_note"):
                _t(p, rx + 8, (sy + end_y) / 2, n["no_note"], 10.5, MUTED, anchor="start")
        elif nodes[target].get("side"):
            ty = ys[target] + heights[target] / 2
            tx = SIDE_X - BOX_W / 2 - 2
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (sx, sy, rx, sy, rx, ty, tx, ty))
            if n.get("no_note"):
                _t(p, rx + 8, (sy + ty) / 2, n["no_note"], 10.5, MUTED, anchor="start")
        else:
            ty = ys[target] + heights[target] / 2
            tx = CX + (175 if nodes[target]["kind"] == "dec" else BOX_W / 2)
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (sx, sy, rx, sy, rx, ty, tx + 2, ty))
            if n.get("no_note"):
                _t(p, rx + 8, (sy + ty) / 2, n["no_note"], 10.5, MUTED, anchor="start")

    for i in sides:
        tgt = nodes[i].get("to", "end")
        x0 = SIDE_X - BOX_W / 2 + 40
        y0 = ys[i] + heights[i]
        if tgt == "end":
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (x0, y0, x0, end_y + 30, end_x + 90, end_y + 30, end_x + 30, end_y + 26))
        else:
            ty = ys[tgt] + heights[tgt] / 2
            _arrow(p, "M %d %.1f L %d %.1f L %d %.1f L %.1f %.1f"
                   % (x0, y0, x0, ty, CX + BOX_W / 2 + 60, ty, CX + BOX_W / 2 + 2, ty))

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

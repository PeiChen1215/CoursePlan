"""重画图 2-1：程序系统层次结构图（组织图式，按层分列，模块竖排）。

层级与归属严格按 D04 表 2.3：表现层 M-09；接口与应用层 M-01/02/03/07/08/10；
领域层 M-04/05/06；基础设施层 M-11/12。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LINE = "#1f2937", "#6b7280", "#334155", "#94a3b8"
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT

COL_W = 250          # 每列宽
GAP_X = 24
MARGIN = 24
ROOT_H, LAYER_H, MOD_H = 56, 46, 52
GAP_ROOT_LAYER = 46
GAP_LAYER_MOD = 34
GAP_MOD = 16

LAYERS = [
    ("表现层", [("M-09", "看板与前端组件")]),
    ("接口与应用层", [("M-01", "认证与权限"), ("M-02", "课程内容管理"), ("M-03", "约束与容量"),
                  ("M-07", "确认与版本"), ("M-08", "进度与事件"), ("M-10", "接口与序列化")]),
    ("领域层", [("M-04", "追问与抽取"), ("M-05", "分解与排程"), ("M-06", "计划校验")]),
    ("基础设施层", [("M-11", "存储访问"), ("M-12", "配置与日志")]),
]


def build():
    n = len(LAYERS)
    W = MARGIN * 2 + n * COL_W + (n - 1) * GAP_X
    max_mods = max(len(m) for _, m in LAYERS)
    root_y = 20
    layer_y = root_y + ROOT_H + GAP_ROOT_LAYER
    mod_y0 = layer_y + LAYER_H + GAP_LAYER_MOD
    H = mod_y0 + max_mods * (MOD_H + GAP_MOD) + 60

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         'markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>'
         % STROKE]

    def t(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                 'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def line(x1, y1, x2, y2, arrow=False):
        p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.2"%s/>'
                 % (x1, y1, x2, y2, LINE, ' marker-end="url(#a)"' if arrow else ""))

    # 根
    root_w = 300
    root_x = (W - root_w) / 2
    p.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="8" fill="%s" stroke="%s" stroke-width="1.4"/>'
             % (root_x, root_y, root_w, ROOT_H, TEAL_SOFT, TEAL))
    t(W / 2, root_y + ROOT_H / 2 + 6, "课程学习规划辅助系统", 16, INK, bold=True)

    # 层列
    centers = []
    for i, (layer, mods) in enumerate(LAYERS):
        cx = MARGIN + i * (COL_W + GAP_X) + COL_W / 2
        centers.append(cx)
        p.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="6" fill="%s" stroke="%s" stroke-width="1.3"/>'
                 % (cx - COL_W / 2 + 6, layer_y, COL_W - 12, LAYER_H, "#f1f5f9", STROKE))
        t(cx, layer_y + LAYER_H / 2 + 6, layer, 14, INK, bold=True)

    # 根到各层：先竖直，再横向母线，再竖直下到层框
    bus_y = root_y + ROOT_H + GAP_ROOT_LAYER / 2
    line(W / 2, root_y + ROOT_H, W / 2, bus_y)
    line(centers[0], bus_y, centers[-1], bus_y)
    for cx in centers:
        line(cx, bus_y, cx, layer_y, arrow=True)

    # 层到模块：用左侧“归属括号”，模块之间不画箭头（它们是兄弟，不是链）
    for i, (layer, mods) in enumerate(LAYERS):
        cx = centers[i]
        box_x = cx - COL_W / 2 + 20
        bracket_x = box_x - 14
        stubs = []
        for k, (mid, name) in enumerate(mods):
            yy = mod_y0 + k * (MOD_H + GAP_MOD)
            p.append('<rect x="%.1f" y="%d" width="%d" height="%d" rx="5" fill="#ffffff" stroke="%s" stroke-width="1.2"/>'
                     % (cx - COL_W / 2 + 20, yy, COL_W - 40, MOD_H, STROKE))
            t(cx, yy + 20, mid, 12, MUTED)
            t(cx, yy + 38, name, 12, INK)
            stubs.append(yy + MOD_H / 2)
        if not mods:
            continue
        # 括号：层框底部 → 下滑到最末模块中心
        line(cx, layer_y + LAYER_H, cx, layer_y + LAYER_H + 14)
        line(bracket_x, layer_y + LAYER_H + 14, cx, layer_y + LAYER_H + 14)
        line(bracket_x, layer_y + LAYER_H + 14, bracket_x, stubs[-1])
        for sy in stubs:
            line(bracket_x, sy, box_x - 2, sy, arrow=True)

    t(W / 2, H - 26, "连线表示“归属”关系，不代表运行调用顺序；调用关系见 §3.3 表 3.3", 11, MUTED)
    return "\n".join(p + ["</svg>"]) + "\n"


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    svg = build()
    name = "fig-2-1-structure"
    (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
    w = int(svg.split('width="')[1].split('"')[0])
    h = int(svg.split('height="')[1].split('"')[0])
    raw = TMP / (name + ".png")
    bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
    size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
    print("%-22s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

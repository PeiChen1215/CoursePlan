"""生成 D06 详细设计的图：程序层次结构图、IPO 图（三角形三栏）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE = "#1f2937", "#6b7280", "#334155"
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT


def structure():
    """程序系统层次结构：4 层 12 个程序，★ 为详写。"""
    W, H = 940, 560
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
             '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
             '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
             'markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                     'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                     % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def box(x, y, w, h, lines, detail=False, size=12):
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" fill="%s" stroke="%s" stroke-width="1.2"/>'
                     % (x, y, w, h, "#f8fafc" if detail else "#ffffff", STROKE))
        for k, ln in enumerate(lines):
            text(x + w / 2, y + h / 2 + 5 + (k - (len(lines) - 1) / 2) * 17, ln, size)

    def seg(x1, y1, x2, y2, arrow=False):
        parts.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.1"%s/>'
                     % (x1, y1, x2, y2, "9ca3af", ' marker-end="url(#a)"' if arrow else ""))

    parts.append('<rect x="330" y="14" width="280" height="46" rx="7" fill="%s" stroke="%s" stroke-width="1.3"/>'
                 % (TEAL_SOFT, TEAL))
    text(470, 43, "课程学习规划辅助系统", 15, INK, bold=True)

    layers = [
        ("表现层", 96, [("M-09", "看板与前端组件", False)]),
        ("接口与应用层", 196, [("M-01", "认证与权限", False), ("M-02", "课程内容管理", True),
                             ("M-03", "约束与容量", True), ("M-10", "接口与序列化", False)]),
        ("领域层", 330, [("M-04", "追问与抽取", False), ("M-05", "分解与排程", True),
                       ("M-06", "计划校验", True), ("M-07", "确认与版本", True),
                       ("M-08", "进度与事件", True)]),
        ("基础设施层", 470, [("M-11", "存储访问", False), ("M-12", "配置与日志", False)]),
    ]
    LEFT, RIGHT = 96, 920
    avail = RIGHT - LEFT
    prev_bottom = 60
    for name, y, mods in layers:
        n = len(mods)
        gap = 10
        w = min(196, (avail - (n - 1) * gap) / n)
        total = n * w + (n - 1) * gap
        x0 = LEFT + (avail - total) / 2
        centers = [x0 + w / 2 + i * (w + gap) for i in range(n)]
        bus = y - 14
        seg(470, prev_bottom, 470, bus)
        seg(min(centers), bus, max(centers), bus)
        for c in centers:
            seg(c, bus, c, y - 2, arrow=True)
        text(LEFT - 8, y + 30, name, 11, MUTED, anchor="end")
        for i, (mid, label, detail) in enumerate(mods):
            box(x0 + i * (w + gap), y, w, 56, ["%s%s" % ("★ " if detail else "", mid), label], detail)
        prev_bottom = y + 56

    text(470, 548, "★ 为本说明书详写的程序；其余在 §2 表格给出标识符与职责，正文简述其与相邻程序的差异", 11, MUTED)
    return "\n".join(parts + ["</svg>"]) + "\n"


def wrap(s, n=19):
    """按显示宽度折行：中文按 1 计，ASCII 按 0.55 计。"""
    out, cur, w = [], "", 0.0
    for ch in s:
        cw = 1.0 if ord(ch) > 127 else 0.55
        if w + cw > n and cur:
            out.append(cur)
            cur, w = "  ", 0.0
        cur += ch
        w += cw
    if cur.strip():
        out.append(cur)
    return out


def ipo(in_items, proc_items, out_items, _title=""):
    """IPO 图：左输入、中处理、右输出，三栏 + 箭头（文字自动折行，不烤图题）。"""
    cols = [("输入", in_items), ("处理", proc_items), ("输出", out_items)]
    wrapped = []
    for head, items in cols:
        lines = []
        for it in items:
            lines.extend(wrap("· " + it))
        wrapped.append((head, lines))
    maxlines = max(len(l) for _, l in wrapped)
    colw, gap, margin = 300, 22, 22
    W = margin * 2 + colw * 3 + gap * 2
    top, headh = 20, 34
    body_h = maxlines * 24 + 24
    H = top + headh + body_h + 20
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
             '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
             '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
             'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                     'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                     % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    xs = [margin + i * (colw + gap) for i in range(3)]
    for i, (head, lines) in enumerate(wrapped):
        x = xs[i]
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="%s" stroke="%s" stroke-width="1.3"/>'
                     % (x, top, colw, headh + body_h, "#f8fafc" if i == 1 else "#ffffff", STROKE))
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#f1f5f9" stroke="%s" stroke-width="1.1"/>'
                     % (x, top, colw, headh, STROKE))
        text(x + colw / 2, top + 23, head, 14, INK, bold=True)
        for k, ln in enumerate(lines):
            text(x + 12, top + headh + 24 + k * 24, ln, 12, INK, anchor="start")
    mid_y = top + headh + body_h / 2
    for i in range(2):
        x1 = xs[i] + colw
        parts.append('<path d="M %d %.1f L %d %.1f" stroke="%s" stroke-width="1.6" marker-end="url(#a)"/>'
                     % (x1, mid_y, x1 + gap - 2, mid_y, STROKE))
    return "\n".join(parts + ["</svg>"]) + "\n"


FIGS = {
    "fig-6-1-structure": structure,
    "fig-6-2-ipo-m05": lambda: ipo(
        ["约束对象：主目标、附加目标、截止、周模板、排除日期、已掌握",
         "课程内容快照：知识点、参考时长、先修边、资源",
         "配置：学习练习比 7:3、缓冲比例 10%、片长上限、片数上限",
         "基准时刻 base_time（UTC）"],
        ["求先修闭包并剔除已掌握",
         "按参考时长拆学习/练习任务",
         "拓扑排序（先修 + 学习先于练习）",
         "按可用时段逐段装箱，留缓冲",
         "超长任务拆片，片数和片长受限",
         "汇总 T / C / B / C′ 与缺口"],
        ["任务列表（稳定身份 + 预计时长）",
         "时间片列表（起止、所属版本）",
         "未排入清单与原因",
         "指标：T、C、B、C′、缺口、利用率",
         "草案对象（含输入快照引用）"],
        "图 6-2 M-05 分解与排程 的 IPO 图",
    ),
}


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, builder in FIGS.items():
        svg = builder()
        (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
        w = int(svg.split('width="')[1].split('"')[0])
        h = int(svg.split('height="')[1].split('"')[0])
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-20s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

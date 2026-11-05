"""D04 图 2-4：系统模块结构图（控制关系）。

结构图记法：矩形=模块，自上而下箭头=调用/控制，模块框内第三行标注主要数据进出。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "03_设计" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LINE = "#1f2937", "#6b7280", "#334155", "#64748b"
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT

W = 1290
T0_Y, T1_Y, T2_Y, T3_Y = 28, 200, 430, 590
H_BOX, H_MAIN = 86, 92

T0 = ("M-10", "接口与序列化", "HTTP 请求 → 响应")
T1 = [
    ("M-01", "认证与权限", "令牌 → 角色"),
    ("M-03", "约束与容量", "约束字段 → C / B / C′"),
    ("M-04", "追问与抽取", "自然语言 → 字段"),
    ("M-05", "分解与排程", "约束 → 草案"),
    ("M-06", "计划校验", "草案 → 校验报告"),
    ("M-07", "确认与版本", "确认请求 → 版本"),
    ("M-08", "进度与事件", "事件 → 完成率"),
    ("M-09", "看板与前端", "计划 → 视图数据"),
]
T2 = [("M-02", "课程内容管理", "内容快照 →")]
T3 = [("M-11", "存储访问", "SQL / 事务"), ("M-12", "配置与日志", "配置 / 日志")]


def build():
    n = len(T1)
    bw = 140
    gap = (W - 60 - n * bw) / (n - 1)
    xs = [30 + i * (bw + gap) for i in range(n)]
    H = T3_Y + H_BOX + 60

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         'markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>'
         % LINE]

    def t(x, y, s, size=12, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                 'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def module(x, y, w, h, mid, name, data, fill="#ffffff", stroke=STROKE):
        p.append('<rect x="%.1f" y="%d" width="%.0f" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="1.3"/>'
                 % (x, y, w, h, fill, stroke))
        t(x + w / 2, y + 20, mid, 11, MUTED)
        t(x + w / 2, y + 38, name, 12.5, INK, bold=True)
        t(x + w / 2, y + 56, data, 10, MUTED)

    def arrow(x1, y1, x2, y2, dash=False):
        p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.2"%s marker-end="url(#a)"/>'
                 % (x1, y1, x2, y2, LINE, ' stroke-dasharray="5 4"' if dash else ""))

    # 顶层
    w0 = 300
    x0 = (W - w0) / 2
    module(x0, T0_Y, w0, H_MAIN - 6, T0[0], T0[1], T0[2], fill=TEAL_SOFT, stroke=TEAL)

    # 顶层 → 第二层母线
    bus = T0_Y + H_MAIN + 34
    arrow(W / 2, T0_Y + H_MAIN - 6, W / 2, bus)
    p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.2"/>'
             % (xs[0] + bw / 2, bus, xs[-1] + bw / 2, bus, LINE))
    for x in xs:
        arrow(x + bw / 2, bus, x + bw / 2, T1_Y)

    for (mid, name, data), x in zip(T1, xs):
        module(x, T1_Y, bw, H_BOX, mid, name, data)

    # M-02：被 M-03、M-05 读取
    x2 = xs[1] + bw / 2 - 90
    module(x2, T2_Y, 180, H_BOX, T2[0][0], T2[0][1], "被 M-03 / M-05 读取")
    arrow(xs[1] + bw / 2, T1_Y + H_BOX, x2 + 70, T2_Y, dash=True)
    arrow(xs[3] + bw / 2, T1_Y + H_BOX, x2 + 150, T2_Y, dash=True)
    t((xs[1] + bw / 2 + x2 + 70) / 2 - 6, (T1_Y + H_BOX + T2_Y) / 2, "内容快照", 9.5, MUTED)
    t((xs[3] + bw / 2 + x2 + 150) / 2 + 6, (T1_Y + H_BOX + T2_Y) / 2 - 10, "内容快照", 9.5, MUTED)

    # M-11 / M-12：共用基础（不画连线，避免穿过 M-02；逐条调用见表 3.3）
    y3 = T3_Y
    bw3 = 240
    x3 = 30
    for (mid, name, data) in T3:
        module(x3, y3, bw3, H_BOX - 10, mid, name, data, fill="#f8fafc")
        x3 += bw3 + 30
    t(x3 + 16, y3 + 26, "共用基础：被上述全部程序调用", 12, INK, anchor="start", bold=True)
    t(x3 + 16, y3 + 48, "（每个程序的具体调用点见 §3.3 表 3.3）", 10, MUTED, anchor="start")
    t(W / 2, H - 22, "箭头表示调用（上层调用下层）；框内第三行为主要数据进出；虚线为读取 / 共用关系", 11, MUTED)
    return "\n".join(p + ["</svg>"]) + "\n"


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    svg = build()
    name = "fig-2-4-structure"
    (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
    h = int(svg.split('height="')[1].split('"')[0])
    raw = TMP / (name + ".png")
    bf.shoot(bf.html_for_svg(svg, (W, h)), str(raw), (W, h))
    size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
    print("%-24s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

"""图 2-1：程序调用结构图（结构图）——按“谁调用谁”组织，不是按分层归属。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LINE = "#1f2937", "#6b7280", "#334155", "#64748b"
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT

W = 1080
T1_Y, T2_Y, T3_Y, T4_Y = 28, 172, 330, 470
T1_H, T2_H, T3_H = 54, 78, 58

TOP = ("M-10", "接口与序列化", "HTTP 入口，唯一的对外通道")
T2 = [("M-01", "认证与权限"), ("M-03", "约束与容量"), ("M-04", "追问与抽取"),
      ("M-05", "分解与排程"), ("M-06", "计划校验"), ("M-07", "确认与版本"),
      ("M-08", "进度与事件"), ("M-09", "看板与前端组件")]
T3 = [("M-02", "课程内容管理", "被 M-03、M-05 读取快照")]
SHARED = [("M-11", "存储访问"), ("M-12", "配置与日志")]


def build():
    n2 = len(T2)
    bw = 122
    gap = (W - 40 - n2 * bw) / (n2 - 1)
    xs2 = [20 + i * (bw + gap) for i in range(n2)]
    H = T4_Y + T3_H + 96

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

    def box(x, y, w, h, lines, fill="#ffffff", stroke=STROKE, size=12, sub=None, sub_size=10.5):
        p.append('<rect x="%.1f" y="%d" width="%.0f" height="%d" rx="5" fill="%s" stroke="%s" stroke-width="1.2"/>'
                 % (x, y, w, h, fill, stroke))
        t(x + w / 2, y + (h / 2 - 4 if sub else h / 2 + 4), lines, size, INK, bold=True)
        if sub:
            t(x + w / 2, y + h / 2 + 14, sub, sub_size, MUTED)

    def line(x1, y1, x2, y2, dash=False, arrow=True):
        p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.2"%s%s/>'
                 % (x1, y1, x2, y2, LINE, ' stroke-dasharray="5 4"' if dash else "",
                    ' marker-end="url(#a)"' if arrow else ""))

    # 顶层
    w1 = 300
    x1 = (W - w1) / 2
    box(x1, T1_Y, w1, T1_H, "%s　%s" % (TOP[0], TOP[1]), fill=TEAL_SOFT, stroke=TEAL, size=14, sub=TOP[2])

    # 顶层到第二层母线
    bus = T1_Y + T1_H + 40
    line(W / 2, T1_Y + T1_H, W / 2, bus, arrow=False)
    line(xs2[0] + bw / 2, bus, xs2[-1] + bw / 2, bus, arrow=False)
    for x in xs2:
        line(x + bw / 2, bus, x + bw / 2, T2_Y, arrow=True)

    # 第二层
    for (mid, name), x in zip(T2, xs2):
        box(x, T2_Y, bw, T2_H, mid, sub=name, size=13)

    # 第三层：M-02（被 M-03、M-05 调用）
    x2c = xs2[1] + bw / 2 - 70
    box(x2c, T3_Y, 140, T3_H, "M-02", sub="课程内容管理", size=12)
    src_idx = [1, 3]              # M-03、M-05 的下标
    for i in src_idx:
        line(xs2[i] + bw / 2, T2_Y + T2_H, x2c + 70, T3_Y, arrow=True)

    # 第四层：共用基础（M-11、M-12）
    sx = 20
    sw = W - 40
    p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="6" fill="#f8fafc" stroke="%s" stroke-width="1.2"/>'
             % (sx, T4_Y, sw, T3_H, STROKE))
    t(sx + sw / 2, T4_Y + 24, "共用基础（被上述全部程序调用）", 12, INK, bold=True)
    t(sx + sw / 2, T4_Y + 45, "M-11 存储访问　·　M-12 配置与日志　·　M-04 经 M-12 调用模型适配器", 11, MUTED)
    # 共用基础：一条虚线母线横跨第二层所有程序，再向下汇入共用框（不逐条连线）
    bus_y = T2_Y + T2_H + 26
    line(xs2[0] + bw / 2, bus_y, xs2[-1] + bw / 2, bus_y, dash=True, arrow=False)
    for x in xs2:
        line(x + bw / 2, T2_Y + T2_H + 2, x + bw / 2, bus_y, dash=True, arrow=False)
    line(W / 2, bus_y, W / 2, T4_Y - 6, dash=True, arrow=True)
    t(W / 2 + 10, (bus_y + T4_Y) / 2, "共用基础（完整调用见表 3.3）", 10.5, MUTED, anchor="start")

    t(W / 2, H - 24, "箭头表示“调用 / 依赖”；本图按调用层次组织，分层归属见 D04 图 2-4", 11, MUTED)
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

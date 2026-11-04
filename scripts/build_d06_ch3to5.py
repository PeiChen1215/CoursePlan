"""D06 第 1 批图：结构图（去★）+ 第 3～5 章各 2 张（IPO / 流程图）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402
from build_d06_figures import ipo, wrap  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE = "#1f2937", "#6b7280", "#334155"
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT


# ---------------------------------------------------------------- 结构图
def structure():
    W, H = 940, 520
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
         'markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    def text(x, y, s, size=13, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                 'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def seg(x1, y1, x2, y2, arrow=False):
        p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.1"%s/>'
                 % (x1, y1, x2, y2, "9ca3af", ' marker-end="url(#a)"' if arrow else ""))

    p.append('<rect x="330" y="14" width="280" height="46" rx="7" fill="%s" stroke="%s" stroke-width="1.3"/>'
             % (TEAL_SOFT, TEAL))
    text(470, 43, "课程学习规划辅助系统", 15, INK, bold=True)

    layers = [
        ("表现层", 92, [("M-09", "看板与前端组件")]),
        ("接口与应用层", 182, [("M-01", "认证与权限"), ("M-02", "课程内容管理"),
                             ("M-03", "约束与容量"), ("M-07", "确认与版本"),
                             ("M-08", "进度与事件"), ("M-10", "接口与序列化")]),
        ("领域层", 306, [("M-04", "追问与抽取"), ("M-05", "分解与排程"), ("M-06", "计划校验")]),
        ("基础设施层", 400, [("M-11", "存储访问"), ("M-12", "配置与日志")]),
    ]
    LEFT, RIGHT = 96, 920
    avail = RIGHT - LEFT
    prev_bottom = 60
    for name, y, mods in layers:
        n = len(mods)
        gap = 8
        w = min(140, (avail - (n - 1) * gap) / n)
        total = n * w + (n - 1) * gap
        x0 = LEFT + (avail - total) / 2
        centers = [x0 + w / 2 + i * (w + gap) for i in range(n)]
        bus = y - 14
        seg(470, prev_bottom, 470, bus)
        seg(min(centers), bus, max(centers), bus)
        for c in centers:
            seg(c, bus, c, y - 2, arrow=True)
        text(LEFT - 8, y + 30, name, 11, MUTED, anchor="end")
        for i, (mid, label) in enumerate(mods):
            bx = x0 + i * (w + gap)
            p.append('<rect x="%.1f" y="%d" width="%.0f" height="52" rx="5" fill="#ffffff" '
                     'stroke="%s" stroke-width="1.2"/>' % (bx, y, w, STROKE))
            text(bx + w / 2, y + 22, mid, 11)
            text(bx + w / 2, y + 40, label, 9)
        prev_bottom = y + 52

    text(470, H - 16, "本图只表示模块的层次归属；模块间的调用顺序见 §3.3 表 3.3", 11, MUTED)
    return "\n".join(p + ["</svg>"]) + "\n"


# ---------------------------------------------------------------- 通用流程图
def flow(nodes, W=760):
    """nodes: list of dict(kind: 'rect'|'diamond'|'end', lines, right: (label, lines) 可选)"""
    GAP = 30
    heights = []
    for nd in nodes:
        h = 46 if nd["kind"] != "diamond" else 60
        h = max(h, 24 * len(nd["lines"]) + 20)
        heights.append(h)
    H = 26 + sum(heights) + GAP * (len(nodes) - 1) + 40
    CX = 300 if any("right" in n for n in nodes) else W // 2
    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
         '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
         '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
         'markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE]

    def text(x, y, s, size=12, fill=INK, anchor="middle", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                 'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    y = 24
    for idx, nd in enumerate(nodes):
        h = heights[idx]
        lines = nd["lines"]
        if nd["kind"] == "diamond":
            hw, hh = 120, h / 2
            p.append('<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f Z" fill="#f8fafc" '
                     'stroke="%s" stroke-width="1.3"/>' % (CX, y, CX + hw, y + hh, CX, y + h, CX - hw, y + hh, STROKE))
        else:
            fill = "#f1f5f9" if nd["kind"] == "end" else "#ffffff"
            p.append('<rect x="%.1f" y="%d" width="240" height="%d" rx="6" fill="%s" stroke="%s" '
                     'stroke-width="1.3"/>' % (CX - 120, y, h, fill, STROKE))
        for k, ln in enumerate(lines):
            text(CX, y + h / 2 + 5 + (k - (len(lines) - 1) / 2) * 17, ln, 12)

        if "right" in nd:
            label, rlines = nd["right"]
            ry = y + h / 2
            p.append('<path d="M %.1f %.1f L 500 %.1f" stroke="%s" stroke-width="1.2" marker-end="url(#a)"/>'
                     % (CX + 120, ry, ry, STROKE))
            text(CX + 130, ry - 6, label, 11, MUTED, anchor="start")
            rh = max(40, 20 * len(rlines) + 14)
            p.append('<rect x="510" y="%.1f" width="230" height="%d" rx="5" fill="#ffffff" stroke="%s" stroke-width="1.2"/>'
                     % (ry - rh / 2, rh, STROKE))
            for k, ln in enumerate(rlines):
                text(625, ry - rh / 2 + 16 + k * 18, ln, 10.5)

        if idx < len(nodes) - 1:
            ny = y + h
            p.append('<path d="M %.1f %.1f L %.1f %.1f" stroke="%s" stroke-width="1.3" marker-end="url(#a)"/>'
                     % (CX, ny, CX, ny + GAP - 2, STROKE))
            if nd.get("down"):
                text(CX + 14, ny + GAP / 2 + 4, nd["down"], 11, MUTED, anchor="start")
        y += h + GAP
    return "\n".join(p + ["</svg>"]) + "\n"


FIGS = {
    "fig-2-1-structure": ("svg", structure),
    "fig-3-1-ipo-m01": ("ipo", lambda: ipo(
        ["账号、口令（明文仅用于本次比对）", "会话令牌（后续请求携带）", "请求上下文：角色、目标对象 ID"],
        ["散列比对（bcrypt）", "失败计数与锁定判定", "令牌签发与过期校验", "角色判定与归属校验"],
        ["令牌与角色、有效期", "401 / 403 / 404 判定结果", "锁定状态与剩余时间"],
        "")),
    "fig-3-2-flow-m01": ("flow", lambda: flow([
        {"kind": "end", "lines": ["开始：收到登录请求"]},
        {"kind": "diamond", "lines": ["账号存在？"], "right": ("否", ["统一返回 401", "不区分账号是否存在"]), "down": "是"},
        {"kind": "diamond", "lines": ["处于锁定期？"], "right": ("是", ["返回 401 + 剩余时间", "正确口令也不放行"]), "down": "否"},
        {"kind": "diamond", "lines": ["口令散列比对通过？"], "right": ("否", ["失败计数 +1", "满 5 次置锁定 5 分钟"]), "down": "是"},
        {"kind": "rect", "lines": ["失败计数清零", "签发令牌（含角色，24 小时）"]},
        {"kind": "rect", "lines": ["记录最近登录时间"]},
        {"kind": "end", "lines": ["结束：返回令牌与角色"]},
    ])),
    "fig-4-1-ipo-m02": ("ipo", lambda: ipo(
        ["课程 / 知识点 / 先修批次 / 资源字段", "现有先修图（用于整图环检测）", "当前登录管理员身份"],
        ["字段校验与同课程唯一性", "批量去重与自环剔除", "在原图 + 本批上做 DFS 三色环检测", "引用影响分析（停用 vs 删除）", "原子保存或整批回滚"],
        ["保存结果与受影响对象数", "环路路径与行号（成环时）", "引用提示（被版本引用时只允许停用）"],
        "")),
    "fig-4-2-flow-m02": ("flow", lambda: flow([
        {"kind": "end", "lines": ["开始：批量提交先修关系"]},
        {"kind": "diamond", "lines": ["两端存在且同课程？"], "right": ("否", ["整批拒绝 E1001", "指出越界行号"]), "down": "是"},
        {"kind": "rect", "lines": ["剔除自环、按有序对去重"]},
        {"kind": "diamond", "lines": ["原图 + 本批存在环？"], "right": ("是", ["整批拒绝 E2001", "返回环路路径"]), "down": "否"},
        {"kind": "rect", "lines": ["单事务写入本批关系"]},
        {"kind": "end", "lines": ["结束：返回保存结果"]},
    ])),
    "fig-5-1-ipo-m03": ("ipo", lambda: ipo(
        ["约束字段：目标、截止、周模板、排除日期、已掌握", "课程内容（知识点参考时长、先修）", "配置：缓冲比例、每日上限、截止窗口"],
        ["字段校验与规范化", "展开区间内实际可用时段", "计算原始容量 C 与缓冲 B", "判定 C 是否为零", "已掌握集合去重"],
        ["规范化约束对象", "容量摘要 C / B / C′", "容量为零时的拒绝原因", "目标路径所需时长估算"],
        "")),
    "fig-5-2-flow-m03": ("flow", lambda: flow([
        {"kind": "end", "lines": ["开始：提交约束"]},
        {"kind": "diamond", "lines": ["字段合法？"], "right": ("否", ["返回 E1001", "定位到字段与行"]), "down": "是"},
        {"kind": "diamond", "lines": ["截止在次日至 180 天内？"], "right": ("否", ["拒绝 E1001", "提示可用范围"]), "down": "是"},
        {"kind": "rect", "lines": ["展开可用时段、扣排除日期"]},
        {"kind": "diamond", "lines": ["原始容量 C > 0？"], "right": ("否", ["拒绝 E1003", "列出全部被排除原因"]), "down": "是"},
        {"kind": "rect", "lines": ["计算 B 与 C′，估算目标路径时长"]},
        {"kind": "end", "lines": ["结束：返回约束与容量摘要"]},
    ])),
}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, (kind, builder) in FIGS.items():
        svg = builder()
        (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
        w = int(svg.split('width="')[1].split('"')[0])
        h = int(svg.split('height="')[1].split('"')[0])
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-22s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

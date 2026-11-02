"""生成 D02 三张竖向泳道图（黑白线稿，宽高比 ≤1.2，时间轴唯一高度避免连线穿框）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "02_需求" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LANE = "#1f2937", "#6b7280", "#334155", "#94a3b8"
W = 900
LANE_W = 198
LANE_X = [24, 234, 444, 654]
HEAD_H = 44
TOP = 70
STEP = 94


class Canvas:
    def __init__(self, height):
        self.h = height
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            % (W, height, W, height),
            '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, height),
            '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            'markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="%s"/></marker></defs>' % STROKE,
        ]

    def lanes(self, names):
        for i, name in enumerate(names):
            x = LANE_X[i]
            self.parts.append('<rect x="%d" y="18" width="%d" height="%d" fill="#ffffff" '
                              'stroke="%s" stroke-width="1"/>' % (x, LANE_W, self.h - 30, LANE))
            self.parts.append('<rect x="%d" y="18" width="%d" height="%d" fill="#f1f5f9" '
                              'stroke="%s" stroke-width="1"/>' % (x, LANE_W, HEAD_H, LANE))
            self.text(x + LANE_W / 2, 46, name, 16, INK, "middle", True)

    def text(self, x, y, s, size=15, fill=INK, anchor="start", bold=False):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.parts.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                          'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                          % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))

    def box(self, idx, lane, lines, dash=False):
        h = 26 * len(lines) + 20
        y = TOP + idx * STEP
        x = LANE_X[lane] + 8
        self.parts.append('<rect x="%d" y="%d" width="%d" height="%d" rx="5" fill="#ffffff" '
                          'stroke="%s" stroke-width="1.3"%s/>'
                          % (x, y, LANE_W - 16, h, STROKE, ' stroke-dasharray="5 4"' if dash else ""))
        for k, ln in enumerate(lines):
            self.text(x + (LANE_W - 16) / 2, y + 22 + k * 24, ln, 15, INK, "middle")
        return {"i": idx, "x": x, "y": y, "w": LANE_W - 16, "h": h, "cx": x + (LANE_W - 16) / 2}

    def _p(self, d, dash=False, arrow=True):
        self.parts.append('<path d="%s" fill="none" stroke="%s" stroke-width="1.4"%s%s/>'
                          % (d, STROKE, ' stroke-dasharray="5 4"' if dash else "",
                             ' marker-end="url(#a)"' if arrow else ""))

    def link(self, a, b, label=None, dash=False):
        """相邻步骤在两者之间空带折线；跨步（如分支/跳过）从源泳道下行到目标上方的空带再横向，
        避免竖线穿过中间步骤的框。"""
        y1 = a["y"] + a["h"]
        y2 = b["y"]
        skip = b["i"] - a["i"] > 1
        gap = (y2 - 12) if skip else (y1 + y2) / 2
        if abs(a["cx"] - b["cx"]) < 2:
            self._p("M %.1f %.1f L %.1f %.1f" % (a["cx"], y1, a["cx"], y2 - 2), dash)
        else:
            self._p("M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f"
                    % (a["cx"], y1, a["cx"], gap, b["cx"], gap, b["cx"], y2 - 2), dash)
        if label:
            self.text((a["cx"] + b["cx"]) / 2, gap - 7, label, 13, MUTED, "middle")

    def loop(self, a, b, x0=12, label=None):
        """沿左边界的回卷箭头。"""
        y1 = a["y"] + a["h"] / 2
        y2 = b["y"] + b["h"] / 2
        self._p("M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f"
                % (a["x"] - 2, y1, x0, y1, x0, y2, b["x"] - 2, y2), True)
        if label:
            self.text(x0 + 46, (y1 + y2) / 2, label, 13, MUTED, "middle")

    def svg(self):
        return "\n".join(self.parts + ["</svg>"]) + "\n"


def render(name, lanes, spec, edges, loops):
    n = len(spec)
    c = Canvas(TOP + n * STEP + 34)
    c.lanes(lanes)
    boxes = [c.box(i, lane, lines, dash) for i, (lane, lines, dash) in enumerate(spec)]
    for a, b, label, dash in edges:
        c.link(boxes[a], boxes[b], label, dash)
    for a, b, label in loops:
        c.loop(boxes[a], boxes[b], label=label)
    return c.svg()


FIGS = {
    "fig-3-15-lane-constraint": dict(
        lanes=["学生", "前端", "约束服务", "排程引擎"],
        spec=[
            (0, ["填写目标、截止", "可用时间、已掌握"], False),
            (1, ["表单校验", "格式与范围提示"], False),
            (2, ["规范化约束", "去重与字段校验"], False),
            (3, ["展开区间内", "实际可用时段"], False),
            (3, ["计算原始容量 C", "缓冲 B、可排 C′"], False),
            (2, ["容量为 0：", "拒绝并说明原因"], True),
            (1, ["回显容量摘要", "C / B / C′"], False),
            (0, ["确认或调整约束"], False),
            (2, ["保存约束快照", "记录基准时刻"], False),
        ],
        edges=[(0, 1, None, False), (1, 2, None, False), (2, 3, None, False),
               (3, 4, None, False), (4, 6, "容量 ≥ 1", False), (4, 5, "容量 = 0", True),
               (5, 6, "原因", True), (6, 7, None, False), (7, 8, "确认", False)],
        loops=[(7, 0, "调整后重填")],
    ),
    "fig-3-16-lane-plan": dict(
        lanes=["学生", "智能体", "排程引擎", "数据仓储"],
        spec=[
            (0, ["提交约束", "与已掌握集合"], False),
            (1, ["自然语言转字段", "一次追问 ≤2 项"], False),
            (3, ["读取课程内容快照"], False),
            (2, ["求先修闭包", "去重减已掌握"], False),
            (2, ["每点拆学习/练习", "按 7:3 分配"], False),
            (2, ["拓扑排序", "按可用时段装箱"], False),
            (2, ["超长任务拆片", "每片留缓冲"], False),
            (3, ["写入草案", "任务与时间片"], False),
            (0, ["回显草案", "可改预计时长"], False),
        ],
        edges=[(0, 1, None, False), (1, 3, None, False), (2, 3, "快照", True),
               (3, 4, None, False), (4, 5, None, False), (5, 6, None, False),
               (6, 7, "写入", False), (7, 8, "回显", False)],
        loops=[(8, 0, "改约束或时长后重生成")],
    ),
    "fig-3-17-lane-confirm": dict(
        lanes=["学生", "接口", "版本服务", "事件记录"],
        spec=[
            (0, ["点击确认", "（带草案修订号）"], False),
            (1, ["校验归属", "与会话有效性"], False),
            (2, ["服务端重新校验", "四项检查"], False),
            (2, ["是否存在 ERROR？"], False),
            (1, ["返回问题码", "草案仍可查看"], True),
            (2, ["复核版本与进度", "写版本、切指针"], False),
            (0, ["确认 v1", "重复确认幂等"], False),
            (0, ["逐任务打卡", "两步确认"], False),
            (3, ["只追加学习事件", "不建新版本"], False),
            (2, ["更新完成率", "与逾期标记"], False),
        ],
        edges=[(0, 1, None, False), (1, 2, None, False), (2, 3, None, False),
               (3, 4, "是", True), (3, 5, "否", False), (5, 6, "写 v1", False),
               (6, 7, None, False), (7, 8, "提交打卡", False), (8, 9, None, False)],
        loops=[(4, 0, "改约束后重新生成")],
    ),
}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, cfg in FIGS.items():
        svg = render(name, cfg["lanes"], cfg["spec"], cfg["edges"], cfg["loops"])
        (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
        height = int(svg.split('height="')[1].split('"')[0])
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_svg(svg, (W, height)), str(raw), (W, height))
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-28s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

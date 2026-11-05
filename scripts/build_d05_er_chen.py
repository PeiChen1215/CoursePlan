"""D05 概念 ER 图（严格 Chen 记法）：矩形=实体，椭圆=属性（主键加下划线），菱形=联系，连线标基数。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "03_设计" / "figures" / "peer"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LINE = "#1f2937", "#6b7280", "#334155", "#64748b"
ENT_W, ENT_H = 190, 54
EW, EH = 88, 21          # 属性椭圆半径
FAN = 56                 # 属性垂直间距


class Chen:
    def __init__(self, w, h):
        self.W, self.H = w, h
        self.lines, self.nodes, self.texts = [], [], []
        self.ents, self.attrs = {}, {}

    # ---------- 基元
    def line(self, x1, y1, x2, y2, dash=False):
        self.lines.append((x1, y1, x2, y2, dash))

    def entity(self, key, name, x, y):
        self.ents[key] = (x, y)
        self.nodes.append(
            '<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff" stroke="%s" stroke-width="1.4"/>'
            % (x - ENT_W / 2, y - ENT_H / 2, ENT_W, ENT_H, STROKE))
        self.texts.append((x, y + 5, name, 13, INK, True, True))

    def attr(self, key, name, x, y, pk=False):
        self.attrs[(key, name)] = (x, y)
        rx = max(EW, len(name) * 3.9 + 16)
        self.nodes.append('<ellipse cx="%d" cy="%d" rx="%d" ry="%d" fill="#ffffff" stroke="%s" stroke-width="1.1"/>'
                          % (x, y, rx, EH, STROKE))
        self.texts.append((x, y + 4, name, 11, INK, False, True))
        if pk:                                   # 主键：属性名加下划线
            w = min(len(name) * 6.4, len(name) * 6.4)
            self.nodes.append('<path d="M %.1f %.1f L %.1f %.1f" stroke="%s" stroke-width="1"/>'
                              % (x - w / 2, y + 9, x + w / 2, y + 9, INK))

    def diamond(self, cx, cy, text, rw=56, rh=34):
        self.nodes.append('<path d="M %d %d L %d %d L %d %d L %d %d Z" fill="#ffffff" stroke="%s" stroke-width="1.2"/>'
                          % (cx, cy - rh, cx + rw, cy, cx, cy + rh, cx - rw, cy, STROKE))
        self.texts.append((cx, cy + 5, text, 12, INK, True, True))

    def label(self, x, y, s):
        self.texts.append((x, y, s, 11, MUTED, False, True))

    def note(self, x, y, s, size=11, anchor="middle"):
        self.texts.append((x, y, s, size, MUTED, False, anchor))

    # ---------- 组合：实体 + 一侧属性扇
    def entity_with_attrs(self, key, name, attrs, x, y, side):
        """side: left / right / up / down；attrs 为 (名称, 是否主键) 列表。"""
        self.entity(key, name, x, y)
        n = len(attrs)
        for i, (a, pk) in enumerate(attrs):
            off = (i - (n - 1) / 2) * FAN
            if side == "left":
                ax, ay = x - ENT_W / 2 - 108, y + off
                self.line(x - ENT_W / 2, y + off * 0.35, ax + EW, ay, dash=False)
            elif side == "right":
                ax, ay = x + ENT_W / 2 + 108, y + off
                self.line(x + ENT_W / 2, y + off * 0.35, ax - EW, ay)
            elif side == "up":
                ax, ay = x + (i - (n - 1) / 2) * 196, y - ENT_H / 2 - 62
                self.line(x + off * 0.5, y - ENT_H / 2, ax, ay + EH)
            else:
                ax, ay = x + off, y + ENT_H / 2 + 62
                self.line(x + off * 0.5, y + ENT_H / 2, ax, ay - EH)
            self.attr(key, a, int(ax), int(ay), pk)

    def render(self):
        p = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
             % (self.W, self.H, self.W, self.H),
             '<rect width="%d" height="%d" fill="#ffffff"/>' % (self.W, self.H)]
        for x1, y1, x2, y2, dash in self.lines:
            p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.1"%s/>'
                     % (x1, y1, x2, y2, LINE, ' stroke-dasharray="5 4"' if dash else ""))
        p.extend(self.nodes)
        for x, y, s, size, fill, bold, anchor in self.texts:
            s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
                     'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
                     % (x, y, size, fill,
                        "middle" if anchor is True else anchor,
                        ' font-weight="bold"' if bold else "", s))
        return "\n".join(p + ["</svg>"]) + "\n"


def fig_course():
    """图 3-1 课程内容概念 ER：管理员、课程、知识点、资源 + 先修自关联。"""
    c = Chen(1460, 900)

    c.entity_with_attrs("adm", "管理员", [("user_id", True), ("username", False), ("role", False)],
                        420, 120, "left")
    c.entity_with_attrs("course", "课程", [("course_id", True), ("name", False),
                                          ("semester", False), ("total_hours", False)],
                        900, 120, "up")
    c.entity_with_attrs("concept", "知识点", [("concept_id", True), ("name", False), ("chapter", False),
                                             ("difficulty", False), ("reference_minutes", False)],
                        900, 430, "right")
    c.entity_with_attrs("res", "资源", [("resource_id", True), ("title", False), ("type", False)],
                        900, 740, "left")

    # 维护：管理员 1 — 课程 N
    c.diamond(660, 120, "维护")
    c.line(420 + ENT_W / 2, 120, 604, 120); c.line(716, 120, 900 - ENT_W / 2, 120)
    c.label(600, 110, "1"); c.label(740, 110, "N")

    # 包含：课程 1 — 知识点 N
    c.diamond(900, 275, "包含")
    c.line(900, 147, 900, 241); c.line(900, 309, 900, 403)
    c.label(910, 175, "1"); c.label(910, 385, "N")

    # 关联：知识点 M — 资源 N
    c.diamond(900, 585, "关联")
    c.line(900, 457, 900, 551); c.line(900, 619, 900, 713)
    c.label(910, 485, "M"); c.label(910, 695, "N")

    # 提供：课程 1 — 资源 N（走最右侧，绕开知识点属性）
    c.diamond(1330, 275, "提供")
    c.line(900 + ENT_W / 2, 145, 1274, 262); c.line(1330, 309, 1330, 740); c.line(1330, 740, 900 + ENT_W / 2, 740)
    c.label(1000, 150, "1"); c.label(1342, 690, "N")

    # 先修：知识点自关联（左侧短回路）
    c.diamond(660, 470, "先修")
    c.line(716, 456, 900 - ENT_W / 2, 418); c.line(716, 486, 900 - ENT_W / 2, 448)
    c.label(760, 430, "M"); c.label(760, 508, "N")
    c.note(660, 525, "自关联（知识点 → 知识点）", 10)

    c.note(c.W / 2, c.H - 20, "椭圆为属性，主键属性名加下划线；菱形为联系，连线上的 1 / N / M 为基数", 11)
    return c.render()


def fig_plan():
    """图 3-2 学习规划概念 ER：学生、计划、约束、版本、版本任务、学习事件。"""
    c = Chen(1700, 1140)
    X = 800

    c.entity_with_attrs("stu", "学生", [("user_id", True), ("username", False), ("role", False)],
                        X, 90, "left")
    c.entity_with_attrs("plan", "学习计划", [("plan_id", True), ("status", False),
                                          ("current_version", False), ("progress_revision", False)],
                        X, 300, "left")
    c.entity_with_attrs("ver", "计划版本", [("version_id", True), ("version_no", False),
                                         ("snapshot", False), ("input_hash", False)],
                        X, 520, "left")
    c.entity_with_attrs("vtask", "版本任务", [("version_id + task_id", True), ("in_scope", False),
                                           ("estimated_minutes", False)],
                        X, 740, "left")
    c.entity_with_attrs("ev", "学习事件", [("event_id", True), ("event_type", False),
                                         ("actual_minutes", False)],
                        X, 940, "left")
    c.entity_with_attrs("cons", "学习约束", [("constraint_id", True), ("deadline", False),
                                          ("availability", False)],
                        1400, 300, "up")

    # 学生 1 — 拥有 — N 学习计划
    c.diamond(X, 195, "拥有")
    c.line(X, 117, X, 161); c.line(X, 229, X, 273)
    c.label(X + 10, 140, "1"); c.label(X + 10, 265, "N")

    # 计划 1 — 形成 — N 版本
    c.diamond(X, 410, "形成")
    c.line(X, 327, X, 376); c.line(X, 444, X, 493)
    c.label(X + 10, 350, "1"); c.label(X + 10, 485, "N")

    # 版本 1 — 包含 — N 版本任务
    c.diamond(X, 630, "包含")
    c.line(X, 547, X, 596); c.line(X, 664, X, 713)
    c.label(X + 10, 570, "1"); c.label(X + 10, 705, "N")

    # 版本任务 1 — 产生 — N 事件
    c.diamond(X, 840, "产生")
    c.line(X, 767, X, 806); c.line(X, 874, X, 913)
    c.label(X + 10, 790, "1"); c.label(X + 10, 905, "N")

    # 学习计划 1 — 由约束确定 — 1 学习约束
    c.diamond(1100, 300, "由约束确定", 72, 34)
    c.line(X + ENT_W / 2, 300, 1028, 300); c.line(1172, 300, 1400 - ENT_W / 2, 300)
    c.label(1180, 290, "1"); c.label(1290, 290, "1")

    c.note(c.W / 2, c.H - 20, "椭圆为属性，主键属性名加下划线；时间片（task_slice）在物理设计中按版本任务的弱实体处理", 11)
    return c.render()


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, builder in [("fig-3-1", fig_course), ("fig-3-2", fig_plan)]:
        svg = builder()
        (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
        w = int(svg.split('width="')[1].split('"')[0])
        h = int(svg.split('height="')[1].split('"')[0])
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-12s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

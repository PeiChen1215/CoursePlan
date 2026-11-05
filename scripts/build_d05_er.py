"""D05 概念 ER 图（带属性）：实体框内列属性，主键标 PK，联系用菱形 + 基数。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "03_设计" / "figures" / "peer"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

INK, MUTED, STROKE, LINE = "#1f2937", "#6b7280", "#334155", "#64748b"
HEAD_FILL = "#f1f5f9"

ENT_W = 210
HEAD_H = 26
ROW_H = 20


def _t(p, x, y, s, size=12, fill=INK, anchor="middle", bold=False):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    p.append('<text x="%.1f" y="%.1f" font-family="Microsoft YaHei, SimHei, sans-serif" '
             'font-size="%d" fill="%s" text-anchor="%s"%s>%s</text>'
             % (x, y, size, fill, anchor, ' font-weight="bold"' if bold else "", s))


class ER:
    def __init__(self):
        self.parts = []
        self.ents = {}

    def entity(self, key, name, attrs, x, y, w=ENT_W):
        h = HEAD_H + ROW_H * len(attrs) + 8
        p = self.parts
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="#ffffff" stroke="%s" stroke-width="1.4"/>'
                 % (x, y, w, h, STROKE))
        p.append('<rect x="%d" y="%d" width="%d" height="%d" rx="4" fill="%s" stroke="%s" stroke-width="1.1"/>'
                 % (x, y, w, HEAD_H, HEAD_FILL, STROKE))
        _t(p, x + w / 2, y + HEAD_H / 2 + 5, name, 13, INK, bold=True)
        for i, a in enumerate(attrs):
            yy = y + HEAD_H + 16 + i * ROW_H
            _t(p, x + 10, yy, a, 11, INK, anchor="start")
        self.ents[key] = (x, y, w, h)
        return (x, y, w, h)

    def diamond(self, cx, cy, text, rw=58, rh=34):
        self._diamonds = getattr(self, "_diamonds", [])
        self._diamonds.append((cx, cy, text, rw, rh))

    def _flush_diamonds(self):
        for cx, cy, text, rw, rh in getattr(self, "_diamonds", []):
            self.parts.append('<path d="M %d %d L %d %d L %d %d L %d %d Z" fill="#ffffff" stroke="%s" stroke-width="1.2"/>'
                              % (cx, cy - rh, cx + rw, cy, cx, cy + rh, cx - rw, cy, STROKE))
            _t(self.parts, cx, cy + 5, text, 12, INK)

    def link(self, a, b, label=None, lx=None, ly=None):
        """a、b 为实体 key 的边框点（由 caller 指定坐标），此处只画直线 + 基数标注。"""
        p = self.parts
        p.append('<path d="M %.1f %.1f L %.1f %.1f" fill="none" stroke="%s" stroke-width="1.2"/>'
                 % (a[0], a[1], b[0], b[1], LINE))
        if label:
            _t(p, lx if lx else (a[0] + b[0]) / 2, ly if ly else (a[1] + b[1]) / 2 - 6, label, 11, MUTED)

    def out(self):
        self._flush_diamonds()
        return "\n".join(self.parts + ["</svg>"]) + "\n"


def fig_course():
    W, H = 1080, 640
    e = ER()
    e.parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
               '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H)]

    e.entity("adm", "管理员（app_user）",
             ["PK user_id 用户标识", "username 账号", "password_hash 口令散列", "role 角色", "status 状态"],
             40, 40)
    e.entity("course", "课程（course）",
             ["PK course_id 课程标识", "maintainer_id 维护人", "name 名称", "semester 学期",
              "total_hours 总学时", "status 状态"], 430, 40)
    e.entity("concept", "知识点（concept）",
             ["PK concept_id 知识点标识", "course_id 所属课程", "name 名称", "chapter 章节",
              "difficulty 难度", "reference_minutes 参考时长"], 430, 330)
    e.entity("res", "资源（resource）",
             ["PK resource_id 资源标识", "course_id 所属课程", "title 标题", "type 类型",
              "url / summary 地址或摘要", "read_minutes 阅读分钟"], 820, 330)
    e.entity("pre", "前置知识点（自关联）",
             ["from_concept_id 先修端", "to_concept_id 后继端"], 40, 470)

    # 1) 管理员 1 — 维护 — N 课程
    e.diamond(335, 107, "维护")
    e.link((250, 107), (277, 107)); e.link((393, 107), (430, 107))
    _t(e.parts, 262, 97, "1", 11, MUTED); _t(e.parts, 410, 97, "N", 11, MUTED)

    # 2) 课程 1 — 包含 — N 知识点（竖直）
    e.diamond(535, 245, "包含")
    e.link((535, 194), (535, 211)); e.link((535, 279), (535, 330))
    _t(e.parts, 546, 206, "1", 11, MUTED); _t(e.parts, 546, 322, "N", 11, MUTED)

    # 3) 课程 1 — 提供 — N 资源（走右上，绕开知识点）
    e.diamond(745, 232, "提供")
    e.link((640, 130), (700, 205)); e.link((800, 252), (900, 330))
    _t(e.parts, 676, 152, "1", 11, MUTED); _t(e.parts, 862, 300, "N", 11, MUTED)

    # 4) 知识点 M — 关联 — N 资源
    e.diamond(730, 407, "关联")
    e.link((640, 407), (672, 407)); e.link((788, 407), (820, 407))
    _t(e.parts, 656, 397, "M", 11, MUTED); _t(e.parts, 804, 397, "N", 11, MUTED)

    # 5) 知识点 N — 先修 — M 前置知识点
    e.diamond(320, 452, "先修")
    e.link((430, 452), (378, 452)); e.link((262, 462), (152, 472))
    _t(e.parts, 404, 442, "N", 11, MUTED); _t(e.parts, 236, 492, "M", 11, MUTED)

    _t(e.parts, W / 2, H - 16, "实体框内列出关键属性，PK 为主键；属性较多，未画属性椭圆", 11, MUTED)
    return e.out()


def fig_plan():
    W, H = 1080, 1010
    e = ER()
    e.parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
               '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H)]

    e.entity("stu", "学生（app_user）",
             ["PK user_id 用户标识", "username 账号", "role 角色 = student"], 40, 40)
    e.entity("plan", "学习计划（study_plan）",
             ["PK plan_id 计划标识", "student_id 所属学生", "course_id 所属课程", "status 状态",
              "current_version 当前版本", "progress_revision 进度修订"], 430, 40)
    e.entity("cons", "学习约束（plan_constraint）",
             ["PK constraint_id 约束标识", "plan_id 所属计划", "target_concept_id 主目标",
              "deadline 截止日期", "availability 周模板"], 820, 40)
    e.entity("ver", "计划版本（plan_version）",
             ["PK version_id 版本标识", "plan_id 所属计划", "version_no 版本号", "snapshot 快照",
              "input_hash 输入摘要"], 430, 330)
    e.entity("vtask", "版本任务（version_task）",
             ["PK version_id + task_id", "in_scope 是否计入", "frozen 是否冻结",
              "estimated_minutes 本版时长", "schedule_state 排入状态"], 430, 570)
    e.entity("ev", "学习事件（learning_event）",
             ["PK event_id 事件标识", "task_id 所属任务", "event_type 类型",
              "actual_minutes 实际用时", "request_key 幂等键"], 430, 810)

    # 水平关系
    e.diamond(340, 107, "拥有")
    e.link((250, 107), (282, 107)); e.link((398, 107), (430, 107))
    _t(e.parts, 262, 97, "1", 11, MUTED); _t(e.parts, 412, 97, "N", 11, MUTED)

    e.diamond(730, 107, "由约束确定", 74, 32)
    e.link((640, 107), (656, 107)); e.link((804, 107), (820, 107))
    _t(e.parts, 660, 90, "1", 11, MUTED); _t(e.parts, 808, 90, "1", 11, MUTED)

    # 竖直关系（主干）：计划底 194 → 版本顶 330；版本底 464 → 版本任务顶 570；版本任务底 704 → 事件顶 810
    e.diamond(535, 262, "形成")
    e.link((535, 194), (535, 228)); e.link((535, 296), (535, 330))
    _t(e.parts, 546, 214, "1", 11, MUTED); _t(e.parts, 546, 322, "N", 11, MUTED)

    e.diamond(535, 517, "包含")
    e.link((535, 464), (535, 483)); e.link((535, 551), (535, 570))
    _t(e.parts, 546, 480, "1", 11, MUTED); _t(e.parts, 546, 562, "N", 11, MUTED)

    e.diamond(535, 757, "产生")
    e.link((535, 704), (535, 723)); e.link((535, 791), (535, 810))
    _t(e.parts, 546, 720, "1", 11, MUTED); _t(e.parts, 546, 802, "N", 11, MUTED)

    _t(e.parts, W / 2, H - 16, "实体框内列出关键属性，PK 为主键；时间片（task_slice）见 §3.3 物理设计", 11, MUTED)
    return e.out()


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
        print("%-14s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

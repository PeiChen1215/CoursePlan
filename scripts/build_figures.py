"""生成《软件需求说明书》所需的图表：Mermaid 源文件 + 界面原型 SVG，并栅格化为 PNG。

产物：
    docs/02_需求/figures/fig-x-y.png      插入文档用（约 1600px 宽）
    docs/02_需求/figures/src/fig-x-y.mmd  Mermaid 源文件（可编辑）
    docs/02_需求/figures/src/fig-x-y.svg  原型源文件（可编辑）

渲染方式：Edge headless 截图 → Pillow 去白边裁切。需要本机 Edge。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "docs" / "02_需求" / "figures"
SRC_DIR = FIG_DIR / "src"
TMP_DIR = ROOT / ".tmp_figures"

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
MERMAID_JS = "file:///D:/Gitproject/RJB_Demo/frontend/node_modules/mermaid/dist/mermaid.min.js"

TARGET_WIDTH = 1700
PAD = 24


# ----------------------------------------------------------------------
# 图源定义
# ----------------------------------------------------------------------
MERMAID_FIGURES = {
    "fig-2-1-context": {
        "skip": True,
        "window": (1800, 1800),
        "src": """flowchart TB
    ST["学生"]
    AD["课程管理员"]
    SYS["学径 StudyPath<br/>课程学习规划辅助系统"]
    LLM["大模型服务<br/>（可切换 Mock）"]

    ST -->|"目标 / 截止 / 可用时间"| SYS
    AD -->|"知识点 / 先修 / 资源"| SYS
    SYS -->|"计划 / 校验 / 进度"| ST
    SYS -->|"追问上下文"| LLM
    LLM -->|"自然语言答复"| SYS""",
    },
    "fig-3-1-function-tree": {
        "skip": True,
        "window": (2400, 2800),
        "src": """flowchart LR
    ROOT["学径 StudyPath<br/>课程学习规划辅助系统"]
    ROOT --- M1["课程内容管理"]
    ROOT --- M2["学习规划"]
    ROOT --- M3["执行与调整"]
    ROOT --- M4["基础支撑"]

    M1 --- A1["F-02 课程信息维护"]
    M1 --- A2["F-03 知识点维护"]
    M1 --- A3["F-04 先修关系维护"]
    M1 --- A4["F-05 课程资源维护"]

    M2 --- B1["F-06 学习约束设定"]
    M2 --- B2["F-07 智能体追问"]
    M2 --- B3["F-08 任务分解与计划生成"]
    M2 --- B4["F-09 计划校验"]

    M3 --- C1["F-10 计划确认与打卡"]
    M3 --- C2["F-11 计划调整"]
    M3 --- C3["F-12 计划版本追溯"]
    M3 --- C4["F-13 计划看板"]

    M4 --- D1["F-01 登录与角色"]
    M4 --- D2["离线演示（Mock Provider）"]
    M4 --- D3["数据备份与恢复"]""",
    },
    "fig-3-2-swimlane": {
        "window": (2800, 1900),
        "src": """flowchart TB
    subgraph L1["课程管理员"]
        direction LR
        A1["维护知识点、先修关系<br/>资源与参考时长"]
        A2["先修图检查<br/>（成环 / 孤立点）"]
        A1 --> A2
    end

    subgraph L2["学生"]
        direction LR
        S1["填写目标、截止日期<br/>可用时间、已掌握"]
        S2["确认计划"]
        S3["逐任务打卡<br/>记录实际用时"]
        S1 --> S2 --> S3
    end

    subgraph L3["智能体（大模型）"]
        direction LR
        G1["追问缺失信息<br/>归一化相对日期"]
        G2["生成冲突说明<br/>与调整建议"]
        G1 --> G2
    end

    subgraph L4["系统（排程与校验引擎）"]
        direction LR
        E1["先修闭包 + 任务分解"]
        E2["按可用时段装箱排程"]
        E3["四项校验"]
        E4["生成计划版本"]
        E5["检测延期 / 目标变更"]
        E1 --> E2 --> E3 --> E4
        E5 --> E1
    end

    S1 --> G1
    G1 --> E1
    A1 -.->|"课程内容"| E1
    E3 -->|"存在冲突"| G2
    G2 --> S2
    E4 --> S2
    S3 --> E5
    E5 -->|"触发调整"| E1""",
    },
    "fig-3-3-usecase": {
        "window": (2600, 1900),
        "src": """flowchart TB
    ST(("学生"))
    AD(("课程管理员"))

    ST --> UC1(["设定学习约束"])
    ST --> UC2(["与智能体对话补全信息"])
    ST --> UC3(["查看计划草案与冲突"])
    ST --> UC4(["确认计划并打卡"])
    ST --> UC5(["发起计划调整"])
    ST --> UC6(["查看计划版本与差异"])

    AD --> UC7(["维护课程与知识点"])
    AD --> UC8(["维护先修关系"])
    AD --> UC9(["维护课程资源"])

    UC2 -.->|"extend"| UC1
    UC1 -.->|"include"| UC3
    UC3 -.->|"include"| UC10(["校验计划（容量/重叠/先修/截止）"])
    UC5 -.->|"include"| UC10
    UC4 -.->|"include"| UC6""",
    },
    "fig-3-5-plan-state": {
        "window": (1600, 2400),
        "src": """stateDiagram-v2
    direction TB
    state "草稿" as Draft
    state "待确认" as Pending
    state "执行中" as Active
    state "已完成" as Done
    state "已归档" as Archived

    [*] --> Draft: 生成计划草案
    Draft --> Pending: 校验通过 / 存在冲突
    Pending --> Draft: 修改约束后重新生成
    Pending --> Active: 学生确认（生成 v1）
    Active --> Active: 打卡记录进度
    Active --> Done: 任务全部完成或超过截止日期
    Active --> Archived: 调整生效（旧版本归档）
    Archived --> [*]
    Done --> [*]""",
    },
    "fig-3-4-sequence": {
        "window": (2600, 2000),
        "src": """sequenceDiagram
    autonumber
    actor S as 学生
    participant W as 前端
    participant B as 后端服务
    participant AG as 智能体（LLM）
    participant EN as 排程与校验引擎
    participant DB as 数据库

    S->>W: 输入目标与时间约束
    W->>B: POST /api/constraints
    B->>DB: 保存约束
    B->>AG: 补全缺失字段
    AG-->>B: 抽取结果 + 追问问题
    B-->>W: SSE 推送追问
    W-->>S: 展示追问
    S->>W: 补充"每周一三五 19:00-21:00"
    W->>B: POST /api/plans/preview
    B->>EN: 先修闭包 + 任务分解
    EN-->>B: 任务列表
    B->>EN: 四项校验
    EN-->>B: 校验报告（含问题码）
    B->>AG: 生成冲突说明
    AG-->>B: 说明文本
    B-->>W: 计划草案 + 校验报告
    W-->>S: 看板展示（冲突任务标红）
    S->>W: 确认计划
    W->>B: POST /api/plans/{id}/confirm
    B->>DB: 写入版本 v1
    B-->>W: 确认成功
    W-->>S: 计划进入执行中""",
    },
    "fig-3-9-er": {
        "window": (2800, 2100),
        "src": """erDiagram
    USER ||--o{ STUDY_PLAN : "拥有"
    USER ||--o{ COURSE : "维护"
    COURSE ||--o{ CONCEPT : "包含"
    COURSE ||--o{ RESOURCE : "包含"
    CONCEPT ||--o{ CONCEPT_RESOURCE : "关联"
    RESOURCE ||--o{ CONCEPT_RESOURCE : "关联"
    CONCEPT ||--o{ PREREQUISITE : "作为先修"
    CONCEPT ||--o{ PREREQUISITE : "作为后继"
    CONCEPT ||--o{ PLAN_TASK : "被安排"
    STUDY_PLAN ||--|{ PLAN_TASK : "拆分为"
    STUDY_PLAN ||--o{ PLAN_VERSION : "形成版本"
    STUDY_PLAN ||--|| CONSTRAINT : "由约束确定"
    PLAN_VERSION ||--o| PLAN_VALIDATION : "记录校验"

    USER {
        int id PK
        string username
        string password_hash
        string role
    }
    COURSE {
        int id PK
        string name
        string semester
    }
    CONCEPT {
        int id PK
        int course_id FK
        string name
        int difficulty
        int reference_minutes
    }
    STUDY_PLAN {
        int id PK
        int student_id FK
        string status
        int current_version
    }
    PLAN_TASK {
        int id PK
        int plan_id FK
        string type
        int estimated_minutes
        string scheduled_date
    }
    PLAN_VERSION {
        int id PK
        int plan_id FK
        int version
        string change_reason
    }""",
    },
}


# ----------------------------------------------------------------------
# 界面原型（SVG）
# ----------------------------------------------------------------------
FONT = "Microsoft YaHei, SimHei, sans-serif"
INK = "#0f172a"
MUTED = "#64748b"
LINE = "#cbd5e1"
TEAL = "#0e7c6b"
TEAL_SOFT = "#e6f4f1"
AMBER = "#b45309"
AMBER_SOFT = "#fef3c7"
RED = "#b91c1c"
RED_SOFT = "#fee2e2"
BG = "#f8fafc"


class Svg:
    def __init__(self, w, h, title=""):
        self.w, self.h, self.title = w, h, title
        self.parts = []

    def rect(self, x, y, w, h, fill="#ffffff", stroke=LINE, rx=6, sw=1, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.parts.append(
            '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s" stroke="%s" stroke-width="%s"%s/>'
            % (x, y, w, h, rx, fill, stroke, sw, d)
        )

    def text(self, x, y, s, size=13, fill=INK, anchor="start", weight="normal"):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.parts.append(
            '<text x="%s" y="%s" font-family="%s" font-size="%s" fill="%s" text-anchor="%s" font-weight="%s">%s</text>'
            % (x, y, FONT, size, fill, anchor, weight, s)
        )

    def line(self, x1, y1, x2, y2, stroke=LINE, sw=1, dash=None):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        self.parts.append(
            '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s/>'
            % (x1, y1, x2, y2, stroke, sw, d)
        )

    def arrow(self, x1, y1, x2, y2, stroke="#94a3b8", dash=None, double=False):
        d = ' stroke-dasharray="%s"' % dash if dash else ""
        start = ' marker-start="url(#arr)"' if double else ""
        self.parts.append(
            '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="1.4"'
            ' marker-end="url(#arr)"%s%s/>' % (x1, y1, x2, y2, stroke, start, d)
        )

    def svg(self):
        defs = (
            '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"'
            ' markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
            '<path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker></defs>'
        )
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
            '<rect width="%d" height="%d" fill="#ffffff"/>%s%s</svg>'
            % (self.w, self.h, self.w, self.h, self.w, self.h, defs, "".join(self.parts))
        )


def chrome(s, title, subtitle="", width=980):
    """页头：标题 + 用户区"""
    s.rect(0, 0, width, 56, fill=TEAL, stroke=TEAL, rx=0)
    s.text(20, 35, "学径 StudyPath", 17, "#ffffff", weight="bold")
    s.text(150, 35, title, 14, "#d7efe9")
    s.text(width - 20, 35, "王昱涵（学生）  ▾", 12, "#e8f6f2", anchor="end")
    if subtitle:
        s.text(20, 78, subtitle, 12, MUTED)


def sidebar(s, items, active, width=980, top=56, bottom=600):
    s.rect(0, top, 168, bottom - top, fill=BG, stroke=LINE, rx=0)
    y = top + 34
    for item in items:
        if item == active:
            s.rect(10, y - 20, 148, 30, fill=TEAL_SOFT, stroke=TEAL_SOFT, rx=6)
            s.text(24, y, item, 12.5, TEAL, weight="bold")
        else:
            s.text(24, y, item, 12.5, MUTED)
        y += 42


def field(s, x, y, w, label, placeholder, h=34):
    s.text(x, y - 8, label, 11.5, MUTED)
    s.rect(x, y, w, h, fill="#ffffff", stroke=LINE, rx=4)
    s.text(x + 10, y + h / 2 + 4, placeholder, 11.5, "#94a3b8")


def button(s, x, y, w, h, label, primary=True):
    if primary:
        s.rect(x, y, w, h, fill=TEAL, stroke=TEAL, rx=5)
        s.text(x + w / 2, y + h / 2 + 4, label, 12, "#ffffff", anchor="middle", weight="bold")
    else:
        s.rect(x, y, w, h, fill="#ffffff", stroke=LINE, rx=5)
        s.text(x + w / 2, y + h / 2 + 4, label, 12, INK, anchor="middle")


def wire_wizard():
    s = Svg(980, 660)
    chrome(s, "新建学习计划 · 第 1 步 设定学习约束")
    sidebar(s, ["课程首页", "学习画像", "知识图谱", "学习计划", "学习资源", "掌握进度"], "学习计划")

    # 步骤条
    steps = ["设定目标与时间", "生成与校验", "确认计划"]
    x = 200
    for i, st in enumerate(steps):
        active = i == 0
        s.rect(x, 92, 118, 26, fill=TEAL_SOFT if active else BG,
               stroke=TEAL if active else LINE, rx=13)
        s.text(x + 59, 110, "%d. %s" % (i + 1, st), 10.5,
               TEAL if active else MUTED, anchor="middle")
        x += 130
    s.line(200, 140, 940, 140, stroke=LINE, dash="4 4")

    # 左：表单
    field(s, 200, 186, 300, "主目标知识点", "文件操作  ▾")
    s.text(516, 178, "必填", 10.5, RED)
    field(s, 520, 186, 190, "截止日期", "2026-11-10")
    field(s, 726, 186, 214, "附加知识点（选填）", "选择 0/10  ▾")

    s.text(200, 254, "每周可用时间", 11.5, MUTED)
    s.rect(200, 264, 740, 168, fill="#ffffff", stroke=LINE, rx=4)
    s.rect(200, 264, 740, 28, fill=BG, stroke=LINE, rx=0)
    s.text(212, 283, "星期", 11, MUTED)
    s.text(320, 283, "时段 1", 11, MUTED)
    s.text(540, 283, "时段 2", 11, MUTED)
    s.text(760, 283, "当日合计", 11, MUTED)
    rows = [("周一", "19:00 - 21:00", "—", "2.0 h"),
            ("周二", "—", "—", "0 h"),
            ("周三", "19:00 - 21:00", "—", "2.0 h"),
            ("周四", "—", "—", "0 h"),
            ("周五", "19:00 - 20:30", "—", "1.5 h")]
    y = 300
    for r in rows:
        s.line(200, y, 940, y, stroke="#eef2f6")
        s.text(212, y + 16, r[0], 11.5)
        s.text(320, y + 16, r[1], 11.5, MUTED if r[1] == "—" else INK)
        s.text(540, y + 16, r[2], 11.5, MUTED)
        s.text(760, y + 16, r[3], 11.5, MUTED if r[3] == "0 h" else INK)
        y += 26

    s.text(200, 458, "已掌握知识点（自评）", 11.5, MUTED)
    tags = ["Python 简介", "变量与赋值", "基本数据类型", "条件语句"]
    x = 200
    for t in tags:
        w = 16 + len(t) * 11
        s.rect(x, 468, w, 26, fill=TEAL_SOFT, stroke=TEAL, rx=13)
        s.text(x + w / 2, 485, t, 10.5, TEAL, anchor="middle")
        x += w + 8

    # 右：实时估算
    s.rect(200, 516, 740, 74, fill=AMBER_SOFT, stroke="#fcd34d", rx=6)
    s.text(216, 540, "可用时间估算", 12, AMBER, weight="bold")
    s.text(216, 562, "从 10-27 到 11-10 共 15 天，可用 27.5 小时；目标路径需 18.5 小时，余量 9.0 小时。",
           11.5, "#7c4a03")
    s.text(216, 580, "提示：周三、周五时段偏短，长任务可能被拆分。", 11, "#9a6a10")

    button(s, 760, 606, 84, 30, "下一步")
    button(s, 664, 606, 84, 30, "保存草稿", primary=False)
    s.text(200, 626, "第 1 / 3 步", 11, MUTED)
    return s.svg()


def wire_board():
    s = Svg(980, 660)
    chrome(s, "学习计划看板 · Python 程序设计")
    sidebar(s, ["课程首页", "学习画像", "知识图谱", "学习计划", "学习资源", "掌握进度"], "学习计划")

    # 顶部摘要
    cards = [("总任务", "18 个"), ("计划总时长", "18.5 h"), ("完成率", "6 / 18"),
             ("冲突项", "2 处", RED)]
    x = 200
    for label, value, *color in cards:
        c = color[0] if color else INK
        s.rect(x, 84, 176, 62, fill="#ffffff", stroke=LINE, rx=8)
        s.text(x + 14, 106, label, 11, MUTED)
        s.text(x + 14, 130, value, 18, c, weight="bold")
        x += 188

    # 工具条
    s.text(200, 176, "10-26 ~ 11-01", 12, INK, weight="bold")
    button(s, 320, 162, 78, 26, "周视图", primary=False)
    button(s, 406, 162, 78, 26, "全周期", primary=False)
    s.text(940, 176, "今天 10-28", 11, MUTED, anchor="end")

    # 日历列
    days = [("周一 26", []), ("周二 27", [("学习 · 函数定义", 45, "done")]),
            ("周三 28", [("学习 · 文件操作", 45, "doing"), ("练习 · 文件读写", 20, "conflict")]),
            ("周四 29", []), ("周五 30", [("练习 · 异常处理", 30, "todo")])]
    col_w = (940 - 200 - 4 * 8) / 5
    x = 200
    for name, tasks in days:
        s.rect(x, 196, col_w, 330, fill=BG, stroke=LINE, rx=8)
        s.text(x + 10, 216, name, 11.5, MUTED, weight="bold")
        y = 228
        for title, minutes, state in tasks:
            fill, stroke, tag = {
                "done": (TEAL_SOFT, TEAL, "已完成"),
                "doing": ("#e0f2fe", "#0369a1", "进行中"),
                "todo": ("#ffffff", LINE, "未开始"),
                "conflict": (RED_SOFT, RED, "冲突"),
            }[state]
            s.rect(x + 6, y, col_w - 12, 62, fill=fill, stroke=stroke, rx=6)
            s.text(x + 12, y + 20, title, 10.5, INK)
            s.text(x + 12, y + 38, "%d 分钟" % minutes, 10, MUTED)
            s.text(x + 12, y + 54, tag, 9.5, stroke)
            y += 70
        x += col_w + 8

    # 冲突提示
    s.rect(200, 540, 740, 52, fill=RED_SOFT, stroke=RED, rx=6)
    s.text(214, 562, "DEADLINE_UNREACHABLE：按当前排程，最后任务结束于 11-12，晚于截止日期 11-10。",
           11.5, RED, weight="bold")
    s.text(214, 580, "建议：① 每日时长增至 90 分钟；② 截止顺延至 11-12；③ 移除附加知识点「装饰器」。",
           11, "#7f1d1d")

    button(s, 812, 606, 128, 30, "确认计划")
    button(s, 700, 606, 100, 30, "调整计划", primary=False)
    s.text(200, 626, "版本 v0（草稿） · 生成于 10-28 09:12", 11, MUTED)
    return s.svg()


def wire_admin():
    s = Svg(980, 660)
    chrome(s, "课程内容管理 · 知识点维护", "当前课程：Python 程序设计（启用）")
    s.rect(0, 56, 980, 34, fill=BG, stroke=LINE, rx=0)
    s.text(20, 78, "课程信息", 11.5, MUTED)
    s.text(96, 78, "知识点", 11.5, TEAL, weight="bold")
    s.text(152, 78, "先修关系", 11.5, MUTED)
    s.text(216, 78, "课程资源", 11.5, MUTED)
    s.text(286, 78, "校验报告", 11.5, MUTED)

    # 左：章节树
    s.rect(20, 104, 180, 470, fill="#ffffff", stroke=LINE, rx=6)
    s.text(34, 126, "章节", 11.5, MUTED, weight="bold")
    chapters = [("基础语法", 5), ("控制流", 4), ("数据结构", 5), ("函数", 4),
                ("文件 IO", 3), ("异常处理", 2), ("面向对象", 3)]
    y = 148
    for name, count in chapters:
        s.text(34, y, "▸ %s" % name, 11.5, INK)
        s.text(186, y, str(count), 10.5, MUTED, anchor="end")
        y += 30
    s.text(34, 366, "合计 33 个知识点", 10.5, MUTED)
    button(s, 34, 528, 152, 28, "新增章节", primary=False)

    # 中：表格
    s.rect(212, 104, 520, 470, fill="#ffffff", stroke=LINE, rx=6)
    cols = [(224, "知识点"), (356, "难度"), (404, "参考时长"), (486, "先修数"), (556, "状态")]
    s.rect(212, 104, 520, 30, fill=BG, stroke=LINE, rx=0)
    for x, name in cols:
        s.text(x, 124, name, 11, MUTED, weight="bold")
    rows = [("变量与赋值", "1", "20 min", "0", "启用"),
            ("基本数据类型", "1", "30 min", "1", "启用"),
            ("条件语句", "2", "30 min", "1", "启用"),
            ("循环结构", "2", "45 min", "1", "启用"),
            ("函数定义与调用", "3", "45 min", "2", "启用"),
            ("文件操作", "3", "45 min", "1", "启用"),
            ("异常处理", "3", "40 min", "1", "停用"),
            ("装饰器", "5", "60 min", "1", "启用")]
    y = 152
    for r in rows:
        s.line(212, y, 732, y, stroke="#eef2f6")
        for (x, _), v in zip(cols, r):
            color = MUTED if v == "停用" else INK
            s.text(x, y + 18, v, 11, color)
        y += 30
    s.text(224, 460, "共 33 条 · 已启用 32 条", 10.5, MUTED)

    # 右：编辑面板
    s.rect(744, 104, 216, 470, fill="#ffffff", stroke=LINE, rx=6)
    s.text(758, 126, "编辑知识点", 11.5, INK, weight="bold")
    field(s, 758, 160, 188, "名称", "循环结构")
    field(s, 758, 216, 88, "难度", "2")
    field(s, 858, 216, 88, "参考时长", "45")
    field(s, 758, 272, 188, "所属章节", "控制流  ▾")
    s.text(758, 324, "学习目标", 11.5, MUTED)
    s.rect(758, 332, 188, 58, fill="#ffffff", stroke=LINE, rx=4)
    s.text(768, 350, "· 能写出 for / while 循环", 10.5, INK)
    s.text(768, 368, "· 能判断循环边界条件", 10.5, INK)
    s.text(758, 410, "常见错误", 11.5, MUTED)
    s.rect(758, 418, 188, 44, fill="#ffffff", stroke=LINE, rx=4)
    s.text(768, 436, "· 死循环（忘记更新变量）", 10, INK)
    s.text(758, 480, "状态", 11.5, MUTED)
    s.rect(758, 488, 70, 24, fill=TEAL_SOFT, stroke=TEAL, rx=12)
    s.text(793, 504, "启用", 10.5, TEAL, anchor="middle")
    button(s, 758, 528, 88, 28, "保存")
    button(s, 856, 528, 88, 28, "取消", primary=False)

    s.text(20, 610, "注：被计划引用的知识点不可删除，只能停用；保存时校验同课程内名称唯一，并即时检查先修图是否成环。",
           10.5, MUTED)
    return s.svg()


def draw_function_tree():
    """系统功能结构图：4 个功能域 + 13 项功能（F-01～F-13）"""
    s = Svg(1000, 430)
    s.rect(350, 14, 300, 58, fill=TEAL_SOFT, stroke=TEAL, rx=8)
    s.text(500, 40, "学径 StudyPath", 15, INK, anchor="middle", weight="bold")
    s.text(500, 60, "课程学习规划辅助系统", 11.5, MUTED, anchor="middle")

    modules = [
        ("课程内容管理", ["F-02 课程信息维护", "F-03 知识点维护",
                          "F-04 先修关系维护", "F-05 课程资源维护"]),
        ("学习规划", ["F-06 学习约束设定", "F-07 智能体追问",
                      "F-08 任务分解与计划生成", "F-09 计划校验"]),
        ("执行与调整", ["F-10 计划确认与打卡", "F-11 计划调整",
                        "F-12 计划版本追溯", "F-13 计划看板"]),
        ("基础支撑", ["F-01 登录与角色", "离线演示（Mock）", "数据备份与恢复"]),
    ]
    xs = [30, 258, 486, 714]
    m_y, m_h, bus_y = 118, 46, 100
    s.line(500, 72, 500, bus_y, stroke=MUTED)
    s.line(xs[0] + 105, bus_y, xs[-1] + 105, bus_y, stroke=MUTED)
    for x in xs:
        s.line(x + 105, bus_y, x + 105, m_y, stroke=MUTED)

    for x, (name, leaves) in zip(xs, modules):
        s.rect(x, m_y, 210, m_h, fill=TEAL_SOFT, stroke=TEAL, rx=6)
        s.text(x + 105, m_y + 29, name, 13.5, TEAL, anchor="middle", weight="bold")

        start_y, step, leaf_h = 196, 39, 30
        centers = [start_y + i * step + leaf_h / 2 for i in range(len(leaves))]
        s.line(x + 10, m_y + m_h, x + 10, centers[-1], stroke=MUTED)
        for (title, cy) in zip(leaves, centers):
            s.line(x + 10, cy, x + 22, cy, stroke=MUTED)
            s.rect(x + 22, cy - leaf_h / 2, 188, leaf_h, fill="#ffffff", stroke=LINE, rx=4)
            s.text(x + 32, cy + 4.5, title, 11.5, INK)
    return s.svg()


def draw_context():
    """系统上下文图：中心系统 + 三个外部实体（手绘，保证 A4 下可读）"""
    s = Svg(880, 470)

    # 本系统
    s.rect(320, 180, 240, 112, fill=TEAL_SOFT, stroke=TEAL, rx=8)
    s.text(440, 214, "学径 StudyPath", 16, INK, anchor="middle", weight="bold")
    s.text(440, 240, "课程学习规划", 12.5, MUTED, anchor="middle")
    s.text(440, 258, "辅助系统", 12.5, MUTED, anchor="middle")

    # 外部实体
    s.rect(10, 196, 156, 50, fill="#ffffff", stroke="#334155", rx=4)
    s.text(88, 227, "学生", 14, INK, anchor="middle", weight="bold")
    s.rect(714, 196, 156, 50, fill="#ffffff", stroke="#334155", rx=4)
    s.text(792, 227, "课程管理员", 14, INK, anchor="middle", weight="bold")
    s.rect(340, 376, 200, 56, fill="#ffffff", stroke="#334155", rx=4)
    s.text(440, 400, "大模型服务", 13.5, INK, anchor="middle", weight="bold")
    s.text(440, 420, "（可切换 Mock）", 10.5, MUTED, anchor="middle")

    # 学生 ↔ 系统
    s.arrow(166, 210, 320, 210)
    s.text(243, 200, "目标 / 截止 / 可用时间", 11.5, MUTED, anchor="middle")
    s.arrow(320, 244, 166, 244)
    s.text(243, 262, "计划 / 校验 / 进度", 11.5, MUTED, anchor="middle")

    # 管理员 ↔ 系统
    s.arrow(714, 210, 560, 210)
    s.text(637, 200, "知识点 / 先修 / 资源", 11.5, MUTED, anchor="middle")
    s.arrow(560, 244, 714, 244)
    s.text(637, 262, "校验提示", 11.5, MUTED, anchor="middle")

    # 系统 ↔ 大模型
    s.arrow(418, 292, 418, 376)
    s.text(410, 336, "追问上下文", 11.5, MUTED, anchor="end")
    s.arrow(462, 376, 462, 292)
    s.text(470, 336, "自然语言答复", 11.5, MUTED, anchor="start")
    return s.svg()


WIREFRAMES = {
    "fig-2-1-context": draw_context,
    "fig-3-1-function-tree": draw_function_tree,
    "fig-3-6-wizard": wire_wizard,
    "fig-3-7-board": wire_board,
    "fig-3-8-admin": wire_admin,
}


# ----------------------------------------------------------------------
# 渲染
# ----------------------------------------------------------------------
def html_for_mermaid(src, window):
    return """<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;padding:20px;background:#fff;}
#d{display:inline-block;}
</style>
<script src="%s"></script></head>
<body><div id="d"></div>
<script>
const src = %s;
mermaid.initialize({
  startOnLoad: false,
  theme: "neutral",
  securityLevel: "loose",
  fontFamily: '"Microsoft YaHei", "SimHei", sans-serif',
  themeVariables: { fontSize: "26px", fontFamily: '"Microsoft YaHei", "SimHei", sans-serif' },
  flowchart: { htmlLabels: true, curve: "basis", nodeSpacing: 50, rankSpacing: 70, useMaxWidth: false },
  sequence: { showSequenceNumbers: false, actorFontSize: 15, noteFontSize: 14, messageFontSize: 14, useMaxWidth: false },
  er: { fontSize: 15, useMaxWidth: false },
  state: { fontSize: 15, useMaxWidth: false }
});
mermaid.render("theGraph", src).then(({svg}) => {
  document.getElementById("d").innerHTML = svg;
}).catch(e => { document.getElementById("d").textContent = "RENDER_ERROR: " + e; });
</script></body></html>""" % (MERMAID_JS, json.dumps(src, ensure_ascii=False))


def html_for_svg(svg, window):
    return """<!doctype html>
<html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;background:#fff}</style></head>
<body>%s</body></html>""" % svg


def shoot(html, out_png, window):
    """用 Edge headless 截图。"""
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "fig.html"
        page.write_text(html, encoding="utf-8")
        profile = Path(td) / "profile"
        cmd = [
            EDGE,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--force-device-scale-factor=2",
            "--virtual-time-budget=6000",
            "--user-data-dir=%s" % profile,
            "--window-size=%d,%d" % window,
            "--screenshot=%s" % out_png,
            page.as_uri(),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 and not Path(out_png).exists():
            raise RuntimeError("Edge 截图失败: %s" % (proc.stderr or proc.stdout)[:500])


def trim_and_save(src_png, dst_png):
    im = Image.open(src_png).convert("RGB")
    diff = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255)))
    mask = diff.convert("L").point(lambda v: 255 if v > 12 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise RuntimeError("渲染结果为空（可能是语法错误或被裁掉）")
    clipped = bbox[2] >= im.width - 2 or bbox[3] >= im.height - 2
    left = max(0, bbox[0] - PAD)
    top = max(0, bbox[1] - PAD)
    right = min(im.width, bbox[2] + PAD)
    bottom = min(im.height, bbox[3] + PAD)
    out = im.crop((left, top, right, bottom))
    if out.width > TARGET_WIDTH:
        height = int(out.height * TARGET_WIDTH / out.width)
        out = out.resize((TARGET_WIDTH, height), Image.LANCZOS)
    out.save(dst_png, "PNG", optimize=True)
    return out.size, clipped


def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(exist_ok=True)
    only = sys.argv[1] if len(sys.argv) > 1 else ""

    for name, spec in MERMAID_FIGURES.items():
        if spec.get("skip"):
            continue
        if only and only not in name:
            continue
        (SRC_DIR / (name + ".mmd")).write_text(spec["src"] + "\n", encoding="utf-8")
        raw = TMP_DIR / (name + ".png")
        html = html_for_mermaid(spec["src"], spec["window"])
        shoot(html, str(raw), spec["window"])
        size, clipped = trim_and_save(raw, str(FIG_DIR / (name + ".png")))
        print("%-26s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))

    for name, builder in WIREFRAMES.items():
        if only and only not in name:
            continue
        svg = builder()
        (SRC_DIR / (name + ".svg")).write_text(svg, encoding="utf-8")
        raw = TMP_DIR / (name + ".png")
        html = html_for_svg(svg, (980, 660))
        shoot(html, str(raw), (980, 660))
        size, clipped = trim_and_save(raw, str(FIG_DIR / (name + ".png")))
        print("%-26s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

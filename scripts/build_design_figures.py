"""生成 D04/D05 设计文档所需的图：部署图、总体架构图、模块结构图、逻辑模型图。

架构图与模块结构图用 SVG 手绘（mermaid 分层会排成竖条，比例失衡）；
部署图与逻辑模型用 mermaid。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "03_设计" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work" / "design"

INK, MUTED, LINE = bf.INK, bf.MUTED, bf.LINE
TEAL, TEAL_SOFT = bf.TEAL, bf.TEAL_SOFT

MERMAID = {
    "fig-2-1-deploy": {
        "window": (2200, 1200),
        "src": """flowchart LR
    BROWSER["浏览器<br/>Chrome / Edge"] --> FE["静态前端<br/>React 构建产物"]
    FE -->|"HTTP /api"| API["后端服务<br/>FastAPI + Uvicorn :8000"]
    API --> DB[("SQLite<br/>studyplan.db")]
    API -.->|"可选，可关闭"| LLM["大模型服务<br/>（可切换本地 Mock）"]
    DB -.-> BAK["每日备份<br/>保留 7 份"]""",
    },
    "fig-3-1-logical": {
        "window": (2600, 1800),
        "src": """erDiagram
    USER ||--o{ STUDY_PLAN : "拥有"
    USER ||--o{ COURSE : "维护"
    COURSE ||--o{ CONCEPT : "包含"
    COURSE ||--o{ RESOURCE : "包含"
    CONCEPT ||--o{ CONCEPT_RESOURCE : "关联"
    RESOURCE ||--o{ CONCEPT_RESOURCE : "关联"
    CONCEPT ||--o{ PREREQUISITE : "先修"
    CONCEPT ||--o{ PLAN_TASK : "被安排"
    STUDY_PLAN ||--|{ PLAN_TASK : "拆分"
    STUDY_PLAN ||--|| CONSTRAINT : "约束"
    STUDY_PLAN ||--o{ PLAN_VERSION : "版本"
    PLAN_VERSION ||--o| PLAN_VALIDATION : "校验"
    PLAN_TASK ||--o{ LEARNING_EVENT : "事件\"""",
    },
}


def draw_architecture():
    """四层架构：横向分层带 + 层间箭头。"""
    s = bf.Svg(980, 560)
    bands = [
        ("表现层", 30, 90, 2),
        ("接口层", 150, 90, 5),
        ("领域层", 270, 110, 4),
        ("基础层", 410, 90, 4),
    ]
    names = {
        "表现层": ["学生端工作台<br/>约束向导 / 看板 / 打卡", "管理端<br/>课程 / 知识点 / 先修 / 资源"],
        "接口层": ["认证与权限", "课程内容", "约束管理", "计划与版本", "看板查询"],
        "领域层": ["排程引擎<br/>分解 + 装箱", "校验引擎<br/>四项检查", "智能体<br/>追问 / 说明", "版本与差异<br/>快照 + 对比"],
        "基础层": ["数据访问<br/>SQLite", "课程仓储<br/>内容快照", "LLM<br/>Provider", "配置与<br/>日志"],
    }
    for label, top, height, count in bands:
        s.rect(80, top, 880, height, fill="#f8fafc", stroke=LINE, rx=8)
        s.text(88, top + 20, label, 12, TEAL, weight="bold")
        boxes = names[label]
        width = int((880 - 24 - (count - 1) * 14) / count)
        x = 92
        for b in boxes:
            s.rect(x, top + 30, width, height - 42, fill="#ffffff", stroke="#334155", rx=6)
            first, _, second = b.partition("<br/>")
            s.text(x + width / 2, top + 30 + (height - 42) / 2 + (0 if not second else -6),
                    first, 11, INK, anchor="middle", weight="bold")
            if second:
                s.text(x + width / 2, top + 30 + (height - 42) / 2 + 12, second, 10, MUTED, anchor="middle")
            x += width + 14
    for y in (120, 240, 380):
        s.arrow(510, y, 510, y + 30)
    s.text(520, 136, "调用", 9.5, MUTED)
    s.text(520, 256, "调用", 9.5, MUTED)
    s.text(520, 396, "依赖", 9.5, MUTED)
    return s.svg()


def draw_modules():
    """模块结构：4 层 × 12 个模块（M-01 ~ M-12）。"""
    s = bf.Svg(900, 500)
    s.rect(320, 16, 260, 46, fill=TEAL_SOFT, stroke=TEAL, rx=8)
    s.text(450, 45, "课程学习规划辅助系统", 13, INK, anchor="middle", weight="bold")

    layers = [
        ("表现层", 30, ["M-09 看板与前端组件"]),
        ("接口层", 230, ["M-01 认证与权限", "M-02 课程内容", "M-03 约束管理", "M-10 接口与序列化"]),
        ("领域层", 440, ["M-04 追问与抽取", "M-05 分解与排程", "M-06 计划校验", "M-07 确认与版本", "M-08 进度与事件"]),
        ("基础层", 660, ["M-11 存储访问", "M-12 基础设施"]),
    ]
    centers = []
    for name, x, mods in layers:
        s.rect(x, 96, 190, 40, fill=TEAL_SOFT, stroke=TEAL, rx=6)
        s.text(x + 95, 121, name, 12, TEAL, anchor="middle", weight="bold")
        centers.append(x + 95)
        y = 160
        for m in mods:
            s.rect(x, y, 190, 34, fill="#ffffff", stroke=LINE, rx=4)
            s.text(x + 95, y + 22, m, 10, INK, anchor="middle")
            y += 42
    s.line(450, 62, 450, 80, stroke=MUTED)
    s.line(centers[0], 80, centers[-1], 80, stroke=MUTED)
    for c in centers:
        s.line(c, 80, c, 96, stroke=MUTED)
    return s.svg()


HAND = {"fig-2-2-architecture": draw_architecture, "fig-2-3-modules": draw_modules}


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    for name, spec in MERMAID.items():
        (SRC / (name + ".mmd")).write_text(spec["src"] + "\n", encoding="utf-8")
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_mermaid(spec["src"], spec["window"]), str(raw), spec["window"])
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-24s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))

    for name, builder in HAND.items():
        svg = builder()
        (SRC / (name + ".svg")).write_text(svg, encoding="utf-8")
        raw = TMP / (name + ".png")
        w, h = int(svg.split('width="')[1].split('"')[0]), int(svg.split('height="')[1].split('"')[0])
        bf.shoot(bf.html_for_svg(svg, (w, h)), str(raw), (w, h))
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-24s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

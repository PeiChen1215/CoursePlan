"""补充 D04 / D05 的三张图：生成侧模块交互时序、16 表关系全景、数据生命周期。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "03_设计" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

FIGS = {
    "fig-4-3-generate": ((2400, 2400), """sequenceDiagram
    autonumber
    participant B as 接口与应用层
    participant C as 约束服务
    participant P as 排程引擎
    participant V as 校验引擎
    participant R as 数据仓储

    B->>C: 提交约束
    C->>C: 规范化、展开时段、计算 C / B / C′
    C-->>B: 约束对象与容量摘要
    B->>R: 写入约束快照
    B->>P: 请求生成草案
    R-->>P: 课程内容快照与已掌握集合
    P->>P: 先修闭包、拆学习与练习、拓扑排序、装箱拆片
    P-->>B: 任务与时间片、未排入清单
    B->>V: 请求校验
    V->>V: 四项检查（时段 → 容量 → 重叠 → 先修）
    V-->>B: 校验报告与问题码
    alt 存在 ERROR
        B-->>B: 草案可查看、禁止确认
    else 无 ERROR
        B->>R: 写入草案
        R-->>B: 草案修订号
    end"""),
    "fig-3-6-overview": ((2800, 2200), """erDiagram
    APP_USER ||--o{ COURSE : "维护"
    APP_USER ||--o{ STUDY_PLAN : "拥有"
    COURSE ||--o{ CONCEPT : "包含"
    COURSE ||--o{ RESOURCE : "提供"
    CONCEPT ||--o{ PREREQUISITE : "先修"
    CONCEPT ||--o{ CONCEPT_RESOURCE : "关联"
    RESOURCE ||--o{ CONCEPT_RESOURCE : "关联"
    STUDY_PLAN ||--|| PLAN_CONSTRAINT : "约束"
    STUDY_PLAN ||--o{ PLAN_TASK : "稳定任务"
    STUDY_PLAN ||--o{ PLAN_VERSION : "版本"
    STUDY_PLAN ||--o{ PLAN_DRAFT : "草案"
    PLAN_TASK ||--o{ VERSION_TASK : "版本安排"
    PLAN_VERSION ||--o{ VERSION_TASK : "包含"
    VERSION_TASK ||--o{ TASK_SLICE : "时间片"
    VERSION_TASK ||--o{ LEARNING_EVENT : "事件"
    PLAN_VERSION ||--o| PLAN_VALIDATION : "校验报告"
    APP_USER ||--o{ PLAN_DRAFT : "操作\""""),
    "fig-3-7-lifecycle": ((2200, 2000), """flowchart TD
    A["plan_draft 草案<br/>可改、可删"] -->|"确认事务 BEGIN IMMEDIATE"| B["plan_version 版本<br/>不可变"]
    B --> C["version_task 版本任务<br/>不可变"]
    B --> E["plan_validation 校验报告<br/>每版一份"]
    C --> D["task_slice 时间片<br/>不可变"]
    C --> F["learning_event 学习事件<br/>只追加"]
    F -.->|"不回写快照"| D
    D -.->|"不改完成状态"| F"""),
}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, (win, src) in FIGS.items():
        (SRC / (name + ".mmd")).write_text(src + "\n", encoding="utf-8")
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_mermaid(src, win), str(raw), win)
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-24s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

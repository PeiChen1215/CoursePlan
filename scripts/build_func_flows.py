"""生成 D02 三张功能流程图，风格与图 3-4 一致（mermaid 时序图、autonumber、实线调用/虚线返回）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "02_需求" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

FLOWS = {
    "fig-3-15-lane-constraint": """sequenceDiagram
    autonumber
    actor S as 学生
    participant W as 前端
    participant C as 约束服务
    participant E as 排程引擎

    S->>W: 填写目标、截止日期、可用时间、已掌握
    W->>C: 提交约束
    C->>C: 规范化、去重、字段校验
    C->>E: 请求展开可用时段
    E->>E: 展开区间内实际可用时段
    E->>E: 计算原始容量 C、缓冲 B、可排容量 C′
    alt 容量为 0
        E-->>C: 容量不足
        C-->>W: 拒绝并说明原因
        W-->>S: 提示调整时间或截止
    else 容量不小于 1
        E-->>C: 原始容量、缓冲、可排容量
        C-->>W: 容量摘要 C / B / C′
        W-->>S: 回显摘要
        S->>W: 确认或调整
        W->>C: 提交确认
        C->>C: 保存约束快照、记录基准时刻
    end""",
    "fig-3-16-lane-plan": """sequenceDiagram
    autonumber
    actor S as 学生
    participant G as 智能体
    participant E as 排程引擎
    participant R as 数据仓储

    S->>G: 提交约束与已掌握集合
    G->>G: 自然语言转字段，一次追问不超过 2 项
    G-->>S: 回显待确认摘要
    S->>R: 请求生成草案
    R-->>E: 课程内容快照、可用时段
    E->>E: 求先修闭包、去重减已掌握
    E->>E: 每点拆学习与练习，按 7:3 分配时长
    E->>E: 拓扑排序，按可用时段装箱
    E->>E: 超长任务拆片，每片留缓冲
    E-->>R: 任务、时间片与指标
    R-->>S: 展示草案，可改预计时长
    S->>R: 修改预计时长或约束
    R-->>S: 重新生成草案""",
    "fig-3-17-lane-confirm": """sequenceDiagram
    autonumber
    actor S as 学生
    participant B as 接口
    participant V as 版本服务
    participant D as 事件记录

    S->>B: 点击确认（携带草案修订号）
    B->>B: 校验归属与会话有效性
    B->>V: 提交草案修订号
    V->>V: 服务端重新校验四项检查
    alt 存在 ERROR
        V-->>B: 校验报告与问题码
        B-->>S: 拒绝确认，草案仍可查看
        S->>B: 改约束后重新生成
    else 无 ERROR
        V->>V: 复核版本与进度
        V->>D: 写版本、版本任务与时间片
        D-->>V: 版本号 v1
        V-->>B: 确认成功
        B-->>S: 计划进入执行中
        Note over V,S: 重复确认返回同一版本，不产生第二版
    end
    S->>D: 逐任务打卡（两步确认）
    D->>D: 只追加学习事件，不建立新版本
    D-->>S: 完成率与逾期标记""",
}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    win = (2400, 2600)
    for name, src in FLOWS.items():
        (SRC / (name + ".mmd")).write_text(src + "\n", encoding="utf-8")
        raw = TMP / (name + ".png")
        bf.shoot(bf.html_for_mermaid(src, win), str(raw), win)
        size, clipped = bf.trim_and_save(raw, str(FIG / (name + ".png")))
        print("%-28s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

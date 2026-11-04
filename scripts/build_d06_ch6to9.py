"""D06 第 2 批：第 6/8/9 章的 6 张图。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_figures as bf  # noqa: E402
from build_d06_figures import ipo  # noqa: E402
from build_d06_ch3to5 import flow  # noqa: E402

ROOT = Path(r"D:\Gitproject\CoursePlan")
FIG = ROOT / "docs" / "04_实现" / "figures"
SRC = FIG / "src"
TMP = ROOT / ".tmp_work"

FIGS = {
    "fig-6-1-ipo-m04": lambda: ipo(
        ["学生自然语言输入", "已确认字段（多轮累积）", "课程内容快照（知识点与别名）", "配置：模型预算 10 秒"],
        ["本地规则抽取（日期、时长、星期）", "目标映射：精确 → 别名 → 模型 → 候选", "必填字段完备性判定", "追问选择（一次最多 2 项）", "降级：超时转表单"],
        ["结构化字段候选", "追问问题（≤2 条）", "知识点候选（≤5 个）", "模式标记 local / mock / llm", "降级原因码"],
        ""),
    "fig-6-2-flow-m04": lambda: flow([
        {"kind": "end", "lines": ["开始：收到一句自然语言"]},
        {"kind": "rect", "lines": ["本地规则抽取：日期、时长、星期"]},
        {"kind": "diamond", "lines": ["目标映射到唯一知识点？"], "right": ("否", ["返回候选（≤5 个）", "请学生选一个"]), "down": "是"},
        {"kind": "diamond", "lines": ["必填字段齐备？"], "right": ("否", ["追问 1–2 项", "按“不填无法排程”排序"]), "down": "是"},
        {"kind": "diamond", "lines": ["模型预算内返回？"], "right": ("否", ["转表单，保留已填字段", "标记 mode=local"]), "down": "是"},
        {"kind": "rect", "lines": ["丢弃非法候选（不存在的 ID）", "回显摘要请学生确认"]},
        {"kind": "end", "lines": ["结束：交 M-03 校验并保存"]},
    ]),
    "fig-8-1-ipo-m06": lambda: ipo(
        ["草案：任务与时间片", "约束对象（C、B、C′、截止）", "课程先修图", "配置：阈值 0.8、单片上限"],
        ["① 时段合法性", "② 容量 T ≤ C′", "③ 时间片两两不重叠", "④ 先修与学习先于练习", "⑤ 截止可达", "汇总问题码与建议"],
        ["passed 布尔值", "issues 列表（码、级别、定位）", "metrics：T / C / B / C′ / 缺口 / 利用率", "建议动作"],
        ""),
    "fig-8-2-flow-m06": lambda: flow([
        {"kind": "end", "lines": ["开始：收到草案与约束"]},
        {"kind": "diamond", "lines": ["① 时段合法？"], "right": ("否", ["SLOT_INVALID (ERROR)", "立即返回，不再检查"]), "down": "是"},
        {"kind": "diamond", "lines": ["② T ≤ C′？"], "right": ("否", ["CAP_EXCEEDED (ERROR)", "附缺口 D"]), "down": "是"},
        {"kind": "diamond", "lines": ["③ 无重叠？"], "right": ("否", ["TIME_OVERLAP (ERROR)", "附相交区间"]), "down": "是"},
        {"kind": "diamond", "lines": ["④ 先修顺序成立？"], "right": ("否", ["PREREQ_VIOLATED (ERROR)", "定位到任务"]), "down": "是"},
        {"kind": "diamond", "lines": ["⑤ 截止可达？"], "right": ("否", ["DEADLINE_UNREACHABLE", "ERROR"]), "down": "是"},
        {"kind": "rect", "lines": ["按阈值 0.8 追加 CAP_TIGHT（WARN）", "passed = True"]},
        {"kind": "end", "lines": ["结束：返回报告"]},
    ]),
    "fig-9-1-ipo-m09": lambda: ipo(
        ["草案 ID 与修订号", "确认幂等键 confirm_key", "当前指针、进度修订号、课程修订号", "学生身份"],
        ["归属与草案状态检查", "四项前置条件复核", "事务写版本、版本任务、时间片、报告", "切当前指针、标草案已消费", "计算版本差异"],
        ["新版本号 version_no", "差异列表（新增/移除/移动/时长变化）", "幂等回放结果", "E2004 冲突信息"],
        ""),
    "fig-9-2-flow-m09": lambda: flow([
        {"kind": "end", "lines": ["开始：学生点击确认"]},
        {"kind": "diamond", "lines": ["confirm_key 已消费？"], "right": ("是", ["返回原版本号", "不产生第二版"]), "down": "否"},
        {"kind": "rect", "lines": ["BEGIN IMMEDIATE 取得写锁"]},
        {"kind": "diamond", "lines": ["四项基线复核通过？"], "right": ("否", ["ROLLBACK", "返回 E2004"]), "down": "是"},
        {"kind": "rect", "lines": ["写版本、版本任务、时间片、校验报告"]},
        {"kind": "rect", "lines": ["切 current_version", "标草案 consumed", "COMMIT"]},
        {"kind": "end", "lines": ["结束：返回 v1 与差异"]},
    ]),
}


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    for name, builder in FIGS.items():
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

"""D06 第 4 批：第 13/14 章的 4 张图。"""
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
    "fig-13-1-ipo-m11": lambda: ipo(
        ["领域对象与查询条件", "事务上下文（UnitOfWork）", "迁移脚本与备份配置"],
        ["仓储读写与对象映射", "事务开启、提交与回滚", "乐观锁比对（版本号 / 进度修订号）", "迁移按版本顺序执行，失败回滚", "一致性备份与完整性校验"],
        ["领域对象 / 记录集", "提交结果或冲突异常", "备份文件与校验结论"],
        ""),
    "fig-13-2-flow-m11": lambda: flow([
        {"kind": "end", "lines": ["开始：业务用例请求写操作"]},
        {"kind": "rect", "lines": ["UnitOfWork 开启事务", "BEGIN IMMEDIATE"]},
        {"kind": "diamond", "lines": ["乐观锁比对通过？"], "right": ("否", ["ROLLBACK", "抛 E2004"]), "down": "是"},
        {"kind": "rect", "lines": ["经仓储写入，触发器拦截非法变更"]},
        {"kind": "diamond", "lines": ["触发器或约束报错？"], "right": ("是", ["映射为 E1xxx / E2xxx", "整体回滚"]), "down": "否"},
        {"kind": "rect", "lines": ["COMMIT，释放连接"]},
        {"kind": "end", "lines": ["结束：返回提交结果"]},
    ]),
    "fig-14-1-ipo-m12": lambda: ipo(
        ["默认配置常量表", "环境变量与显式参数", "运行期事件与异常"],
        ["按优先级合并配置", "范围校验（越界拒绝启动）", "日志格式化与脱敏", "健康检查分级", "模型适配器选择与降级"],
        ["装配后的配置对象", "结构化日志行", "健康检查四项状态", "模型模式 mock / real"],
        ""),
    "fig-14-2-flow-m12": lambda: flow([
        {"kind": "end", "lines": ["开始：进程启动"]},
        {"kind": "rect", "lines": ["加载默认值 → 环境变量 → 显式参数"]},
        {"kind": "diamond", "lines": ["取值在允许范围？"], "right": ("否", ["拒绝启动", "日志指出越界的键名"]), "down": "是"},
        {"kind": "rect", "lines": ["装配配置对象，注入各程序"]},
        {"kind": "diamond", "lines": ["模型可用（或 auto 探测成功）？"], "right": ("否", ["切 mock 模式", "记录 degraded_reason"]), "down": "是"},
        {"kind": "rect", "lines": ["启动健康检查", "主服务 / 数据库 / 模型 / 备份"]},
        {"kind": "end", "lines": ["结束：服务就绪"]},
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
        print("%-24s %s%s" % (name, size, "  [可能被裁切]" if clipped else ""))


if __name__ == "__main__":
    main()

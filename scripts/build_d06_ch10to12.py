"""D06 第 3 批：第 10/11/12 章的 6 张图。"""
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
    "fig-10-1-ipo-m08": lambda: ipo(
        ["任务 ID 与所属版本", "事件类型 done / correction / note", "实际用时、备注", "幂等键 request_key"],
        ["两步确认状态校验", "幂等检查（键唯一 + 每任务一条 done）", "更正链校验（同任务、最新一条）", "追加事件并递增进度修订号", "重算完成率与逾期标记"],
        ["事件 ID", "progress_revision", "完成率与逾期标记", "幂等回放结果"],
        ""),
    "fig-10-2-flow-m08": lambda: flow([
        {"kind": "end", "lines": ["开始：学生点“完成”（第一步）"]},
        {"kind": "rect", "lines": ["界面置为待提交状态", "未提交不写任何事件"]},
        {"kind": "diamond", "lines": ["request_key 已存在？"], "right": ("是", ["返回原事件", "不重复计数"]), "down": "否"},
        {"kind": "diamond", "lines": ["事件类型是 correction？"], "right": ("是", ["校验 corrects_event_id", "须同任务且为最新"]), "down": "否"},
        {"kind": "diamond", "lines": ["该任务已有 done？"], "right": ("是", ["拒绝重复 done", "ux_done_once"]), "down": "否"},
        {"kind": "rect", "lines": ["追加学习事件", "progress_revision + 1"]},
        {"kind": "rect", "lines": ["重算有效用时与完成率", "逾期按派生规则标记"]},
        {"kind": "end", "lines": ["结束：返回统计"]},
    ]),
    "fig-11-1-ipo-m09": lambda: ipo(
        ["计划与版本（当前或历史）", "版本任务与时间片（已排序）", "最新校验报告", "视图参数：按日 / 按周"],
        ["按日或周分组任务", "合并事件状态（完成 / 逾期 / 冲突）", "未排入任务单列", "只读判定（历史版本）", "标记渲染优先级"],
        ["分组后的任务卡片", "状态徽标（文字 + 底色）", "未排入清单与原因", "只读标识"],
        ""),
    "fig-11-2-flow-m09": lambda: flow([
        {"kind": "end", "lines": ["开始：打开看板或周视图"]},
        {"kind": "rect", "lines": ["读取版本任务与时间片", "不扫快照 JSON"]},
        {"kind": "rect", "lines": ["按日或周分组，按时间排序"]},
        {"kind": "rect", "lines": ["合并学习事件，算出状态", "完成 / 逾期 / 冲突"]},
        {"kind": "diamond", "lines": ["是历史版本？"], "right": ("是", ["隐藏打卡入口", "显示差异高亮"]), "down": "否"},
        {"kind": "rect", "lines": ["渲染卡片：文字 + 底色双通道"]},
        {"kind": "end", "lines": ["结束：返回视图数据"]},
    ]),
    "fig-12-1-ipo-m10": lambda: ipo(
        ["HTTP 请求：方法、路径、头、体", "路由表（与 D04 表 3.3 对应）", "领域程序返回结果或异常"],
        ["鉴权与角色判定", "路径参数与 DTO 校验", "调用领域程序", "异常到错误码映射", "统一响应包装"],
        ["HTTP 状态码 + JSON 响应", "错误对象 code / message / field / request_id", "幂等键透传结果"],
        ""),
    "fig-12-2-flow-m10": lambda: flow([
        {"kind": "end", "lines": ["开始：收到 HTTP 请求"]},
        {"kind": "diamond", "lines": ["令牌有效？"], "right": ("否", ["401 E4001"]), "down": "是"},
        {"kind": "diamond", "lines": ["角色允许？"], "right": ("否", ["403 E4003"]), "down": "是"},
        {"kind": "diamond", "lines": ["DTO 校验通过？"], "right": ("否", ["400 E1001", "定位到 field"]), "down": "是"},
        {"kind": "rect", "lines": ["调用领域程序（注入事务边界）"]},
        {"kind": "diamond", "lines": ["领域抛出异常？"], "right": ("是", ["映射：404 / 409 / 503", "不泄露内部细节"]), "down": "否"},
        {"kind": "rect", "lines": ["包装统一响应", "附带 request_id"]},
        {"kind": "end", "lines": ["结束：返回响应"]},
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

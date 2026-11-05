"""D06 全部流程图 v3：单列主干，失败分支沿右边距终止、需重填的沿左边距回流。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d06_flow3 import render  # noqa: E402


def D(kind, lines, no=None, no_label="否", no_note=None, next_label=None):
    n = {"kind": kind, "lines": lines}
    if no is not None:
        n["no"] = no
    if no_label != "否":
        n["no_label"] = no_label
    if no_note:
        n["no_note"] = no_note
    if next_label:
        n["next_label"] = next_label
    return n


FLOWS = {
    # 3.2 登录判定：失败回流到输入
    "fig-3-2-flow-m01": [
        D("term", ["开始"]),
        D("io", ["输入账号与口令"]),
        D("dec", ["账号存在且未锁定？"], no=1),
        D("dec", ["口令散列匹配？", "（失败 +1，满 5 次锁定 5 分钟）"], no=1),
        D("process", ["失败计数清零", "签发令牌（含角色，24 小时）"]),
        D("process", ["记录最近登录时间"]),
        D("term", ["结束"]),
    ],
    # 4.2 先修批量提交：整批拒绝后终止
    "fig-4-2-flow-m02": [
        D("term", ["开始"]),
        D("io", ["接收批量先修关系"]),
        D("dec", ["两端存在且同课程？"], no="end", no_note="整批拒绝 E1001，指出越界行号"),
        D("process", ["剔除自环、按有序对去重"]),
        D("dec", ["原图 + 本批存在环？"], no="end", no_label="是", no_note="整批拒绝 E2001，返回环路路径"),
        D("process", ["单事务写入本批关系"]),
        D("term", ["结束"]),
    ],
    # 5.2 约束提交：字段/截止/容量三类失败都回到填写
    "fig-5-2-flow-m03": [
        D("term", ["开始"]),
        D("io", ["填写目标、截止、可用时间、已掌握"]),
        D("dec", ["字段合法且截止在 2–180 天内？"], no=1),
        D("process", ["展开可用时段、扣排除日期"]),
        D("dec", ["原始容量 C > 0？", "（为零则返回 E1003 与原因）"], no=1),
        D("process", ["计算 B 与 C′，估算目标路径时长"]),
        D("term", ["结束"]),
    ],
    # 6.2 抽取与追问：映射失败、字段不齐都回到输入
    "fig-6-2-flow-m04": [
        D("term", ["开始"]),
        D("io", ["学生输入一句自然语言"]),
        D("process", ["本地规则抽取 + 模型补全（10 秒预算）"]),
        D("dec", ["目标唯一命中知识点？", "（否则给候选 ≤5 个）"], no=1),
        D("dec", ["必填字段齐备？", "（否则追问 1–2 项）"], no=1),
        D("process", ["回显摘要请学生确认"]),
        D("term", ["结束"]),
    ],
    # 7.2 计划生成主流程
    "fig-7-2-flow-m05": [
        D("term", ["开始"]),
        D("io", ["约束 + 内容快照 + 基准时刻"]),
        D("dec", ["目标非空且未全部已掌握？"], no="end", no_note="返回空草案 NOTHING_TO_PLAN"),
        D("process", ["求先修闭包（A2）"]),
        D("dec", ["图中无环？"], no="end", no_note="抛 PREREQ_CYCLE"),
        D("process", ["展开时段，计算 C、B、C′（A1）"]),
        D("dec", ["原始容量 C > 0？"], no="end", no_note="返回空草案 CAPACITY"),
        D("process", ["拆分学习/练习 7:3、稳定拓扑排序（A3、A4）"]),
        D("process", ["装箱与拆片（A5、A6）"]),
        D("process", ["汇总 T、C、B、C′、D、U，计算 input_hash"]),
        D("term", ["结束"]),
    ],
    # 8.2 校验：五项顺序 + 单出口
    "fig-8-2-flow-m06": [
        D("term", ["开始"]),
        D("io", ["接收草案与约束"]),
        D("process", ["按 ① 时段 → ② 容量 → ③ 重叠", "→ ④ 先修 → ⑤ 截止 依次检查"]),
        D("dec", ["任一项 ERROR？"], no="end", no_label="是", no_note="汇总问题码，passed = false（禁止确认）"),
        D("process", ["按阈值 0.8 追加 CAP_TIGHT 等提示", "passed = true"]),
        D("term", ["结束"]),
    ],
    # 9.2 确认事务：幂等与基线冲突都终止
    "fig-9-2-flow-m09": [
        D("term", ["开始"]),
        D("io", ["确认请求：草案 ID + 修订号 + 幂等键"]),
        D("dec", ["幂等键已消费？"], no="end", no_label="是", no_note="返回原版本，不产生第二版"),
        D("process", ["BEGIN IMMEDIATE 取得写锁"]),
        D("dec", ["四项基线一致？"], no="end", no_note="ROLLBACK，返回 E2004"),
        D("process", ["写版本、版本任务、时间片、校验报告"]),
        D("process", ["切当前指针、标草案 consumed、COMMIT"]),
        D("term", ["结束"]),
    ],
    # 10.2 打卡与更正
    "fig-10-2-flow-m08": [
        D("term", ["开始"]),
        D("io", ["点“完成”（第一步）→ 点“提交”（第二步）"]),
        D("dec", ["request_key 已存在？"], no="end", no_label="是", no_note="返回原事件，不重复计数"),
        D("dec", ["该任务已有 done？"], no="end", no_label="是", no_note="拒绝 E1003，提示改为更正"),
        D("process", ["追加学习事件，progress_revision +1"]),
        D("process", ["重算有效用时、完成率与逾期"]),
        D("term", ["结束"]),
    ],
    # 11.2 看板渲染
    "fig-11-2-flow-m09": [
        D("term", ["开始"]),
        D("io", ["打开看板或周视图"]),
        D("process", ["读取版本任务与时间片（不扫快照）"]),
        D("process", ["按日或周分组、按时间排序"]),
        D("process", ["合并学习事件，得出完成 / 逾期 / 冲突"]),
        D("process", ["渲染卡片：文字 + 底色双通道", "历史版本隐藏打卡入口、差异高亮"]),
        D("term", ["结束"]),
    ],
    # 12.2 请求管道
    "fig-12-2-flow-m10": [
        D("term", ["开始"]),
        D("io", ["收到 HTTP 请求"]),
        D("process", ["鉴权与 DTO 校验（失败返 401 / 403 / 400）"]),
        D("dec", ["校验通过？"], no="end", no_note="返回对应错误码，定位 field"),
        D("process", ["调用领域程序（注入事务边界）"]),
        D("dec", ["领域抛出异常？"], no="end", no_label="是", no_note="映射 404 / 409 / 503 后包装"),
        D("process", ["包装统一响应，附 request_id"]),
        D("term", ["结束"]),
    ],
    # 13.2 事务与备份
    "fig-13-2-flow-m11": [
        D("term", ["开始"]),
        D("io", ["业务用例请求写操作"]),
        D("process", ["UnitOfWork 开启事务（BEGIN IMMEDIATE）"]),
        D("dec", ["乐观锁比对通过？"], no="end", no_note="ROLLBACK，抛 E2004"),
        D("process", ["经仓储写入（触发器拦截非法变更）"]),
        D("dec", ["约束或触发器报错？"], no="end", no_label="是", no_note="ROLLBACK，映射为 E1xxx / E2xxx"),
        D("process", ["COMMIT，释放连接"]),
        D("term", ["结束"]),
    ],
    # 14.2 配置装配
    "fig-14-2-flow-m12": [
        D("term", ["开始：进程启动"]),
        D("process", ["加载 默认值 → 环境变量 → 显式参数"]),
        D("dec", ["取值在允许范围？"], no="end", no_note="拒绝启动，日志指出越界键名"),
        D("process", ["装配配置对象，注入各程序"]),
        D("process", ["选择模型适配器：auto 探测失败则降级 mock"]),
        D("process", ["启动健康检查：主服务 / 数据库 / 模型 / 备份"]),
        D("term", ["结束：服务就绪"]),
    ],
}


def main():
    for name, nodes in FLOWS.items():
        render(name, nodes)


if __name__ == "__main__":
    main()

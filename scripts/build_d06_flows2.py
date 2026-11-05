"""按标准符号重画 13 张程序流程图（含回流与起止框）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d06_flow2 import render  # noqa: E402


def D(kind, lines, no=None, no_label="否", no_note=None, next_label=None,
      side=False, to=None):
    n = {"kind": kind, "lines": lines}
    if side:
        n["side"] = True
    if to is not None:
        n["to"] = to
    if no is not None:
        n["no"] = no
        n["no_label"] = no_label
    if no_note:
        n["no_note"] = no_note
    if next_label:
        n["next_label"] = next_label
    return n


FLOWS = {
    # ---------------- M-01 登录
    "fig-3-2-flow-m01": [
        D("term", ["开始"]),
        D("io", ["输入账号与口令"]),
        D("dec", ["账号存在且未锁定？"], no=1, no_note="提示统一错误"),
        D("dec", ["口令散列匹配？"], no=1, no_note="失败 +1，满 5 次锁定 5 分钟"),
        D("process", ["失败计数清零", "签发令牌（含角色，24 小时）"]),
        D("process", ["记录最近登录时间"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-02 先修批量提交
    "fig-4-2-flow-m02": [
        D("term", ["开始"]),
        D("io", ["接收批量先修关系"]),
        D("dec", ["两端存在且同课程？"], no="end", no_note="整批拒绝 E1001，指出越界行号"),
        D("process", ["剔除自环、按有序对去重"]),
        D("dec", ["原图 + 本批存在环？"], no="end", no_label="是", no_note="整批拒绝 E2001，返回环路"),
        D("process", ["单事务写入本批关系"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-03 约束与容量
    "fig-5-2-flow-m03": [
        D("term", ["开始"]),
        D("io", ["填写目标、截止、可用时间、已掌握"]),
        D("dec", ["字段合法？"], no=1, no_note="返回 E1001，定位到字段"),
        D("dec", ["截止在次日至 180 天内？"], no=1, no_note="提示允许范围"),
        D("process", ["展开可用时段、扣排除日期"]),
        D("dec", ["原始容量 C > 0？"], no=1, no_note="返回 E1003 与原因"),
        D("process", ["计算 B 与 C′，估算目标路径时长"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-04 追问与抽取
    "fig-6-2-flow-m04": [
        D("term", ["开始"]),
        D("io", ["学生输入一句自然语言"]),
        D("process", ["本地规则抽取：日期、时长、星期"]),
        D("dec", ["目标唯一命中知识点？"], no=1, no_note="返回候选 ≤5 个，请学生重说"),
        D("dec", ["必填字段齐备？"], no=1, no_note="追问 1–2 项"),
        D("dec", ["模型预算内返回？"], no="end", no_note="转表单，保留已填字段（降级）"),
        D("process", ["回显摘要请学生确认"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-05 分解与排程
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
        D("process", ["汇总 T、C、B、C′、D、U", "计算 input_hash"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-06 计划校验
    # 五项检查的顺序与阻断用表表达（见表 8.x）；流程图只画主干，失败走侧链
    "fig-8-2-flow-m06": [
        D("term", ["开始"]),
        D("io", ["接收草案与约束"]),
        D("process", ["按 ① 时段 → ② 容量 → ③ 重叠 → ④ 先修 → ⑤ 截止 依次检查"]),
        D("dec", ["任一项 ERROR？"], no=6),
        D("process", ["按阈值 0.8 追加 CAP_TIGHT 等提示", "passed = true"]),
        D("term", ["结束"]),
        D("process", ["汇总问题码、受影响任务与建议", "passed = false（禁止确认）"], side=True, to="end"),
    ],

    # ---------------- M-07 确认与版本
    "fig-9-2-flow-m09": [
        D("term", ["开始"]),
        D("io", ["确认请求：草案 ID + 修订号 + 幂等键"]),
        D("dec", ["幂等键已消费？"], no=8, no_label="是"),
        D("process", ["BEGIN IMMEDIATE 取得写锁"]),
        D("dec", ["四项基线一致？"], no=9),
        D("process", ["写版本、版本任务、时间片、校验报告"]),
        D("process", ["切当前指针、标草案 consumed、COMMIT"]),
        D("term", ["结束"]),
        D("process", ["返回原版本，不产生第二版"], side=True, to="end"),
        D("process", ["ROLLBACK，返回 E2004"], side=True, to="end"),
    ],

    # ---------------- M-08 打卡与更正
    "fig-10-2-flow-m08": [
        D("term", ["开始"]),
        D("io", ["学生点“完成”（第一步）"]),
        D("process", ["界面置为待提交，不写库"]),
        D("io", ["学生点“提交”（第二步）"]),
        D("dec", ["request_key 已存在？"], no="end", no_label="是", no_note="返回原事件，不重复计数"),
        D("dec", ["事件类型是更正？"], no=7, no_note="否：按打卡处理"),
        D("dec", ["指向最新完成事件？"], no="end", no_note="拒绝 E1001 / E1003"),
        D("dec", ["该任务已有 done？"], no=8, no_note="是：拒绝，改为更正"),
        D("process", ["追加学习事件，progress_revision +1"]),
        D("process", ["重算有效用时、完成率与逾期"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-09 看板
    "fig-11-2-flow-m09": [
        D("term", ["开始"]),
        D("io", ["打开看板或周视图"]),
        D("process", ["读取版本任务与时间片（不扫快照）"]),
        D("process", ["按日或周分组、按时间排序"]),
        D("process", ["合并学习事件，得出完成 / 逾期 / 冲突"]),
        D("dec", ["是历史版本？"], no=7, no_note="否：允许打卡"),
        D("process", ["隐藏打卡入口、显示差异高亮"]),
        D("process", ["渲染卡片：文字 + 底色双通道"]),
        D("term", ["结束"]),
    ],
    # ---------------- M-10 请求管道
    "fig-12-2-flow-m10": [
        D("term", ["开始"]),
        D("io", ["收到 HTTP 请求"]),
        D("dec", ["令牌有效？"], no=9),
        D("dec", ["角色允许？"], no=10),
        D("dec", ["DTO 校验通过？"], no=11),
        D("process", ["调用领域程序（注入事务边界）"]),
        D("dec", ["领域抛出异常？"], no=12),
        D("process", ["包装成功响应，附 request_id"]),
        D("term", ["结束"]),
        D("process", ["返回 401 E4001"], side=True, to="end"),
        D("process", ["返回 403 E4003"], side=True, to="end"),
        D("process", ["返回 400 E1001（定位 field）"], side=True, to="end"),
        D("process", ["映射 404 / 409 / 503 后包装"], side=True, to="end"),
    ],

    # ---------------- M-11 事务
    "fig-13-2-flow-m11": [
        D("term", ["开始"]),
        D("io", ["业务用例请求写操作"]),
        D("process", ["UnitOfWork 开启事务（BEGIN IMMEDIATE）"]),
        D("dec", ["乐观锁比对通过？"], no=8),
        D("process", ["经仓储写入（触发器拦截非法变更）"]),
        D("dec", ["约束或触发器报错？"], no=9),
        D("process", ["COMMIT，释放连接"]),
        D("term", ["结束"]),
        D("process", ["ROLLBACK，抛 E2004"], side=True, to="end"),
        D("process", ["ROLLBACK，映射为 E1xxx / E2xxx"], side=True, to="end"),
    ],

    # ---------------- M-12 配置
    "fig-14-2-flow-m12": [
        D("term", ["开始：进程启动"]),
        D("process", ["加载 默认值 → 环境变量 → 显式参数"]),
        D("dec", ["取值在允许范围？"], no=9),
        D("process", ["装配配置对象，注入各程序"]),
        D("dec", ["模型可用（含 auto 探测）？"], no=6),
        D("process", ["选真实适配器"]),
        D("process", ["启动健康检查：主服务 / 数据库 / 模型 / 备份"]),
        D("term", ["结束：服务就绪"]),
        D("process", ["切 mock，记录 degraded_reason"], side=True, to=6),
        D("process", ["拒绝启动，日志指出越界键名"], side=True, to="end"),
    ],

}


def main():
    for name, nodes in FLOWS.items():
        render(name, nodes)


if __name__ == "__main__":
    main()

"""D06 第 3 批：插入第 10 章 M-08、第 11 章 M-09、第 12 章 M-10。"""
import io
from pathlib import Path

ROOT = Path(r"D:\Gitproject\CoursePlan")
DOC = ROOT / "docs" / "04_实现" / "D06_详细设计说明书_v0.1_20261103.md"

CH10 = '''## 10 M-08 进度与事件设计说明

### 10.1 程序描述

M-08 记录"实际发生了什么"：打卡、更正、备注。它是执行事实的唯一入口，与规划数据严格分离——**打卡不建版本，不回写快照**。

程序特点：

- **只追加**：事件一旦写入不可修改、不可删除，更正用"新事件指向旧事件"表达；
- **幂等**：客户端生成 `request_key`，重复提交返回原结果；
- **派生而非存储**：完成率、逾期标记都是算出来的，不落库，避免与规则不一致。

### 10.2 功能

![M-08 的 IPO 图](figures/fig-10-1-ipo-m08.png)

图 10-1 M-08 进度与事件的 IPO 图

| 功能 | 说明 |
|---|---|
| 两步确认打卡 | 先置"完成"再提交，未提交不写事件 |
| 幂等写入 | `request_key` 唯一，重复返回原事件 |
| 更正 | 追加 `correction` 事件，指向同任务的最新完成事件 |
| 有效用时 | 取最新 done/correction 的 `actual_minutes`；空值用预计值并标注"估算" |
| 完成率与逾期 | 按 `in_scope=1` 统计；逾期为派生标记 |

### 10.3 性能

表 10.1 M-08 的性能指标

| 操作 | 规模 | 目标耗时 |
|---|---|---|
| 单次打卡 | 单条事件 | ≤ 200 ms |
| 完成率重算 | 3000 任务内某计划 | ≤ 50 ms |
| 逾期判定 | 单计划 | ≤ 30 ms |

### 10.4 输入项

表 10.2 M-08 的输入项

| 名称 | 类型 | 有效范围 | 说明 |
|---|---|---|---|
| `task_id` | int | 属于当前版本 | 打卡对象 |
| `event_type` | enum | `done` / `correction` / `note` | 事件类型 |
| `actual_minutes` | int \| null | ≥ 0 | 实际用时 |
| `note` | string | ≤ 500 字 | 备注 |
| `request_key` | string | 客户端生成，全局唯一 | 幂等键 |
| `corrects_event_id` | int \| null | 仅 `correction` 必填 | 指向的前一事件 |

### 10.5 输出项

表 10.3 M-08 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `event_id` | int | 新事件 ID |
| `replayed` | bool | 是否幂等回放 |
| `completion_rate` | float | 0.0–1.0，保留一位小数 |
| `overdue` | bool | 逾期派生的标记 |

### 10.6 算法

#### 10.6.1 两步确认

界面状态机：`未完成 → 待提交 → 已完成`。**只有"提交"这一步才调用本程序**，第一步只在界面置状态，不写库。这样误触不会产生事件。

#### 10.6.2 幂等与唯一性

$$
\\text{写事件} \\iff request\\_key \\notin \\{e.request\\_key\\} \\ \\land \\ (type \\ne done \\ \\lor \\ \\nexists\\, done(task))
$$

```python
def submit(event, repo) -> Result:
    if (old := repo.find_by_request_key(event.request_key)):
        return Result(old, replayed=True)
    if event.type == "done" and repo.has_done(event.task_id):
        raise Conflict("E1003", "该任务已完成，如需改用时请用更正")
    return Result(repo.append(event), replayed=False)
```

数据库侧另有两条索引兜底：`ux_done_once`（`UNIQUE(task_id) WHERE event_type='done'`）与 `request_key` 的唯一约束。

#### 10.6.3 更正链校验

更正事件必须满足三个条件，缺一即拒：

1. `corrects_event_id` 指向的事件属于**同一任务**；
2. 该事件类型是 `done` 或 `correction`（`note` 不能被更正）；
3. 该事件是该任务**最新**的一条完成类事件。

$$
\\text{valid}(e_c) \\iff e_c.corrects \\in \\text{events}(e_c.task) \\ \\land \\ e_c.corrects \\ne \\text{note} \\ \\land \\ e_c.corrects = \\max\\{\\text{id of done/correction}\\}
$$

```python
def check_correction(e, repo):
    prev = repo.get_event(e.corrects_event_id)
    if prev is None or prev.task_id != e.task_id:
        raise Reject("E1001", "更正必须指向同一任务的事件")
    if prev.event_type == "note":
        raise Reject("E1001", "备注事件不能被更正")
    if prev.event_id != repo.latest_completion_event(e.task_id):
        raise Reject("E1003", "只能更正最新一次完成记录")
```

#### 10.6.4 有效用时与完成率

单任务有效用时：

$$
m(t) = \\begin{cases}
m_{event} & \\text{存在最新的 done/correction 且 } actual\\_minutes \\ne \\text{NULL} \\\\
m_{plan} & \\text{否则用预计值，界面标注“估算”}
\\end{cases}
$$

完成率（分母只含在范围内的必做任务）：

$$
R = \\frac{\\#\\{t \\mid t.in\\_scope=1 \\land done(t)\\}}{\\#\\{t \\mid t.in\\_scope=1\\}}
$$

```python
def completion_rate(tasks, events) -> float:
    scoped = [t for t in tasks if t.in_scope == 1]
    if not scoped:
        return 0.0
    return round(sum(1 for t in scoped if has_done(t, events)) / len(scoped), 3)
```

#### 10.6.5 逾期（派生标记）

$$
\\text{overdue}(t) = \\neg done(t) \\ \\land \\ \\big(\\text{now} > \\text{end}(t) \\ \\lor \\ \\text{now} > deadline\\big)
$$

**逾期不改完成状态**，只在界面上加标记；这是与"计划状态机"的边界——计划是否"已完成"只看必做任务是否全部完成。

```python
def is_overdue(task, now, deadline) -> bool:
    return not task.done and (now > task.last_slice_end or now > deadline)
```

### 10.7 流程逻辑

![M-08 打卡与更正流程](figures/fig-10-2-flow-m08.png)

图 10-2 M-08 打卡与更正流程

流程要点：

1. **幂等检查在最前**，重复请求不进入后续校验；
2. 更正与打卡走同一入口，靠 `event_type` 分流；
3. 同一任务第二次 `done` 被拒，提示改用更正——这比"允许覆盖"更安全；
4. 写入成功才递增 `progress_revision`，供确认事务比对。

### 10.8 接口

表 10.4 M-08 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 | 函数调用 | 打卡接口 |
| 被调用 | M-11 | 仓储 + 事务 | 追加事件、更新修订号 |
| 被读取 | M-09 | 查询 | 看板取事件算状态 |

```python
def submit(event: EventInput, actor: Claims) -> Result: ...
def completion_rate(plan_id: int) -> float: ...
def is_overdue(task, now, deadline) -> bool: ...
```

### 10.9 存储分配

表 10.5 M-08 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 事件行 | 约 200 B/条 | 与任务量同阶 |
| 完成率计算 | 单计划 ≤ 3000 任务 | 一次性内存聚合，不缓存 |
| 索引 | `ix_event_plan`、`ux_done_once` | 查询与唯一性 |

### 10.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 幂等 | 说明"返回原结果" | `# 同一 request_key 返回原事件，不重复计数` |
| 更正 | 说明为何只允许最新一条 | `# 只允许更正最新完成记录，避免事件链分叉` |
| 逾期 | 说明不改状态 | `# 逾期是派生标记，不改变计划的完成状态` |

### 10.11 限制条件

1. 本期不撤销完成（只可更正用时与备注）；
2. 事件不可删除，误操作靠新增更正事件修正；
3. 单进程写，并发更正由写锁串行化；
4. 完成率只统计 `in_scope=1` 的任务；
5. 逾期以服务端时钟为准。

### 10.12 测试计划

表 10.6 M-08 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-10-01 | 正常打卡 | 首次 `done` | 写一条事件，`progress_revision` +1 |
| T-10-02 | 重复打卡 | 同 `request_key` 两次 | 第二次 `replayed=true`，事件数不变 |
| T-10-03 | 换键重复打卡 | 新键、同任务再 done | 拒绝 `E1003` |
| T-10-04 | 更正用时 | `correction` 指向最新 done | 有效用时更新为新值 |
| T-10-05 | 更正跨任务 | `corrects_event_id` 属于别的任务 | 拒绝 `E1001` |
| T-10-06 | 更正非最新 | 指向更早的那条 done | 拒绝 `E1003` |
| T-10-07 | 备注事件 | `note` + 带 `corrects_event_id` | 拒绝 `E1001` |
| T-10-08 | 备注不影响用时 | 追加 `note` | 有效用时不变 |
| T-10-09 | 用时为空 | `actual_minutes=null` | 用预计值并标注“估算” |
| T-10-10 | 完成率分母 | 存在 `in_scope=0` 的已完成任务 | 不计入分母 |
| T-10-11 | 完成率边界 | 全部完成 / 全部未完成 | 1.0 / 0.0 |
| T-10-12 | 逾期 | 未完成且已过片结束时间 | `overdue=true`，状态仍为执行中 |

### 10.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-17 | 撤销完成 | 不支持 | 若需要，加 `undone` 事件类型并重算派生值 |
| Q-18 | 多设备并发更正 | 写锁串行 | 多用户时改为版本号比对 |

'''

CH11 = '''## 11 M-09 看板与前端组件设计说明

### 11.1 程序描述

M-09 是唯一的展示层程序：把"版本任务 + 时间片 + 事件"渲染成学生看得懂的日视图与周视图。它不写库、不做业务判断，只负责**取数、分组、标注、呈现**。

程序特点：

- **只读**：所有写操作在其他程序；
- **查询走索引**：读 `version_task` 与 `task_slice`，不扫快照 JSON；
- **双通道状态**：文字 + 底色，不使用颜色作为唯一区分。

### 11.2 功能

![M-09 的 IPO 图](figures/fig-11-1-ipo-m09.png)

图 11-1 M-09 看板与前端组件的 IPO 图

| 功能 | 说明 |
|---|---|
| 日视图 | 今日任务卡片、用时、状态 |
| 周视图 | 按周分组，标注冲突与逾期 |
| 未排入清单 | 单列展示，附原因码 |
| 历史版本 | 只读，无打卡入口，差异高亮 |
| 校验结果栏 | 展示问题码与建议 |

### 11.3 性能

表 11.1 M-09 的性能指标

| 操作 | 规模 | 目标耗时 |
|---|---|---|
| 首屏渲染 | 单日 ≤ 10 条 | ≤ 2 s（含静态资源） |
| 周视图切换 | 300 任务 | ≤ 300 ms |
| 未排入清单 | ≤ 100 条 | ≤ 100 ms |

### 11.4 输入项

表 11.2 M-09 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| `plan_id` / `version_no` | int | 当前或历史版本 |
| `view` | enum | `day` / `week` |
| `tasks` / `slices` | list | 由 M-11 查询返回，已按时间排序 |
| `report` | Report | 最新校验报告 |

### 11.5 输出项

表 11.3 M-09 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `groups` | list | 按日分组的任务卡片 |
| `badges` | map | 每个任务的状态徽标（文字 + 底色） |
| `unscheduled` | list | 未排入任务与原因 |
| `readonly` | bool | 历史版本为真 |

### 11.6 算法

#### 11.6.1 分组规则

$$
\\text{bucket}(t) = \\lfloor \\text{local\\_date}(t.start) \\rfloor \\quad (\\text{日视图})
$$

周视图按 `ISO 周` 分组，组内按时间片开始时间升序。

```python
def group_by_day(tasks, slices) -> dict[date, list[Card]]:
    by_task = defaultdict(list)
    for s in slices:
        by_task[s.task_id].append(s)
    out = defaultdict(list)
    for t in tasks:
        day = min(s.start for s in by_task[t.id]).date() if by_task[t.id] else None
        out[day].append(to_card(t, by_task[t.id]))
    return dict(sorted(out.items(), key=lambda kv: (kv[0] is None, kv[0])))
```

#### 11.6.2 状态展示的双通道规则

| 状态 | 文字 | 底色 | 附加图标 |
|---|---|---|---|
| 未开始 | “未开始” | 中性 | — |
| 已完成 | “已完成” | 浅绿 | ✓ |
| 逾期 | “已逾期 N 天” | 浅橙 | ! |
| 冲突 | “冲突：问题码” | 浅红 | ⚠ |
| 未排入 | “未排入：原因” | 斜纹 | — |

**只用底色不行**：黑白打印会全部变成灰块；所以每个状态必须有文字。

#### 11.6.3 标记优先级

同一卡片可能同时"逾期 + 冲突"，只显示一个主标记，按优先级：

$$
\\text{冲突} > \\text{逾期} > \\text{已完成} > \\text{未开始}
$$

理由：冲突会导致计划不可确认，比逾期更严重。

#### 11.6.4 历史版本只读

```python
def render(version, viewer_claims):
    readonly = version.version_no != version.plan.current_version
    return View(cards=..., readonly=readonly, show_checkin=not readonly)
```

历史版本隐藏打卡入口，并显示与上一版的差异高亮（调用 M-07 的差异结果）。

### 11.7 流程逻辑

![M-09 看板渲染流程](figures/fig-11-2-flow-m09.png)

图 11-2 M-09 看板渲染流程

流程要点：

1. 先判只读，再渲染——避免历史版本出现"点不了的按钮"；
2. 未排入任务单独成区，不混进时间轴（否则会以为是某天的任务）；
3. 状态合并以"事件为准"，不以计划安排为准——计划说今天学，实际已完成就显示已完成。

### 11.8 接口

表 11.4 M-09 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 | 查询接口 | 看板数据 |
| 被调用 | M-11 | 只读查询 | 版本任务、时间片、事件 |
| 被调用 | M-07 | 函数调用 | 历史版本的差异 |
| 被调用 | M-08 | 函数调用 | 完成率与逾期 |

```python
def build_view(plan_id: int, version_no: int, view: str, claims) -> View: ...
def to_card(task, slices, events) -> Card: ...
```

### 11.9 存储分配

表 11.5 M-09 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 视图数据 | 单周 ≤ 300 卡片 × 约 200 B ≈ 60 KB | 前端不缓存历史版本 |
| 未排入清单 | ≤ 100 条 | 单列渲染 |
| 无服务端缓存 | — | 每次查询现算，避免与事件不同步 |

### 11.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 双通道 | 说明为什么不用纯颜色 | `# 只用底色不行：黑白打印会全变灰块` |
| 优先级 | 说明冲突优先的理由 | `# 冲突会导致不可确认，优先于逾期` |
| 只读 | 说明历史版本行为 | `# 历史版本隐藏打卡入口，避免误操作` |

### 11.11 限制条件

1. 只支持日/周两种粒度，不做月视图；
2. 单个计划任务数按 3000 估算，超出需分页；
3. 不做拖拽调整（调整走 M-07 的调整草案）；
4. 桌面浏览器优先，不做移动端适配；
5. 不缓存视图数据。

### 11.12 测试计划

表 11.6 M-09 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-11-01 | 空计划 | 无任务 | 显示空状态，不报错 |
| T-11-02 | 仅未排入 | 全部任务未排入 | 时间轴为空，未排入区列出全部 |
| T-11-03 | 完成率 0 | 全部未完成 | 0.0，无异常 |
| T-11-04 | 完成率 100 | 全部完成 | 100.0 |
| T-11-05 | 历史版本 | `version_no < current` | `readonly=true`，无打卡按钮 |
| T-11-06 | 冲突卡片 | 任务带 `TIME_OVERLAP` | 显示文字“冲突：TIME_OVERLAP” |
| T-11-07 | 逾期卡片 | 逾期 3 天 | 显示“已逾期 3 天” |
| T-11-08 | 标记优先级 | 同时逾期与冲突 | 只显示冲突 |
| T-11-09 | 跨日任务 | 一任务两片跨两天 | 两天各出现一张卡片 |
| T-11-10 | 时区 | UTC 存储、本地展示 | 显示为本地时间 |

### 11.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-19 | 月视图 | 不做 | 若需要，复用周视图分组逻辑 |
| Q-20 | 拖拽调整 | 不做 | 需新增"移动任务"草案与校验 |

'''

CH12 = '''## 12 M-10 接口与序列化设计说明

### 12.1 程序描述

M-10 是系统唯一的 HTTP 入口，负责把请求翻译成领域调用、把结果翻译成响应。它**不写业务逻辑**，只做鉴权、校验、路由、包装、错误映射。

程序特点：

- **薄**：每个路由 5–15 行，业务全在领域程序；
- **统一响应**：所有接口同一信封，前端只写一套错误处理；
- **错误不泄露**：内部异常一律映射为固定错误码，不透出堆栈与 SQL。

### 12.2 功能

![M-10 的 IPO 图](figures/fig-12-1-ipo-m10.png)

图 12-1 M-10 接口与序列化的 IPO 图

| 功能 | 说明 |
|---|---|
| 鉴权与角色 | 调用 M-01，失败直接 401/403 |
| 路由映射 | 路径 → 领域函数 |
| DTO 校验 | 类型、必填、范围，错误定位到 `field` |
| 调用与事务 | 注入事务边界，一次请求一个事务 |
| 错误映射 | 领域异常 → HTTP 状态码 + 错误码 |
| 统一包装 | `code` / `message` / `field` / `detail` / `request_id` |

### 12.3 性能

表 12.1 M-10 的性能指标

| 操作 | 目标耗时 |
|---|---|
| 路由解析 + 鉴权 | ≤ 5 ms |
| DTO 校验 | ≤ 5 ms |
| 序列化 | ≤ 3 ms |

### 12.4 输入项

表 12.2 M-10 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| `method` / `path` | string | 路由键 |
| `headers` | map | `Authorization`、`Idempotency-Key` |
| `body` | JSON | 请求体，由 DTO 校验 |
| `query` | map | 查询参数 |

### 12.5 输出项

表 12.3 M-10 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `status` | int | HTTP 状态码 |
| `body` | JSON | `{"code","message","data","field","detail","request_id"}` |

### 12.6 算法

#### 12.6.1 路由到领域程序的映射

| 方法与路径 | 调用的程序 |
|---|---|
| `POST /api/constraints` | M-03 |
| `POST /api/plans/drafts` | M-05 |
| `POST /api/plans/{id}/confirm` | M-07 |
| `POST /api/plans/{id}/events` | M-08 |
| `GET /api/plans/{id}/versions` | M-07 |
| `GET /api/plans/{id}/tasks` | M-09 |

**与 D04 表 3.3 的关系**：那张表是"模块间调用"，本表是"HTTP 到模块"，两者逐条对应。

#### 12.6.2 错误码映射

| 异常 | HTTP | 错误码 | 说明 |
|---|---|---|---|
| 参数校验失败 | 400 | `E1001` | 附 `field` |
| 未认证/令牌过期 | 401 | `E4001` | — |
| 角色不符 | 403 | `E4003` | — |
| 对象不存在或不属于本人 | 404 | `E1002` | **不区分两者** |
| 状态不允许 | 400 | `E1003` | — |
| 基线已变（版本冲突） | 409 | `E2004` | 前端提示重新生成 |
| 数据库忙/写失败 | 503 | `E1005` | 提示稍后重试 |
| 模型不可用 | 200 | — | `mode=mock`，不阻断 |

最后一行是特例：**模型失败不返回错误**，而是降级成功，`detail` 里带 `degraded_reason`。

```python
def map_error(exc) -> tuple[int, dict]:
    table = {
        ValidationError: (400, "E1001"), NotFound: (404, "E1002"),
        StateError: (400, "E1003"), VersionConflict: (409, "E2004"),
        Busy: (503, "E1005"), Unauthorized: (401, "E4001"), Forbidden: (403, "E4003"),
    }
    for cls, (status, code) in table.items():
        if isinstance(exc, cls):
            return status, envelope(code, exc.message, getattr(exc, "field", None))
    return 500, envelope("E9000", "内部错误", request_id=ctx.request_id)
```

#### 12.6.3 统一响应包装

```json
{"code": "OK", "message": "", "data": {...}, "field": null,
 "detail": null, "request_id": "9f3c..."}
```

`request_id` 由入口生成并写入日志，便于根据前端报错定位。

#### 12.6.4 幂等键透传

客户端在 `Idempotency-Key` 头里带键，M-10 原样传给 M-07/M-08：

```python
confirm_key = request.headers.get("Idempotency-Key") or new_uuid()
```

缺省时生成新键——这意味着**同一次点击重复发送若没带键，会被当作两次操作**，所以前端必须带。

### 12.7 流程逻辑

![M-10 请求处理管道](figures/fig-12-2-flow-m10.png)

图 12-2 M-10 请求处理管道

流程要点：

1. 鉴权在最前，未认证请求不进入业务；
2. 校验失败返回 400 且带 `field`，前端可直接高亮；
3. 领域异常统一映射，**不把 SQL 或堆栈返回给前端**；
4. 任何响应都带 `request_id`。

### 12.8 接口

表 12.4 M-10 的调用关系

| 方向 | 对象 | 说明 |
|---|---|---|
| 上层 | 前端 / 测试脚本 | HTTP |
| 被调用 | M-01 | 鉴权 |
| 被调用 | M-03 / M-05 / M-07 / M-08 / M-09 | 业务 |
| 被调用 | M-11 | 事务边界 |

```python
def handle(request) -> Response: ...
def envelope(code, message, data=None, field=None, detail=None) -> dict: ...
```

### 12.9 存储分配

表 12.5 M-10 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 请求上下文 | < 10 KB | 每请求一份 |
| 响应体 | 列表接口 ≤ 200 KB | 超 100 条强制分页 |

### 12.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 错误映射 | 说明为何合并 404 | `# 越权与不存在返回同一码，不泄露存在性` |
| 幂等 | 说明缺省行为 | `# 未带 Idempotency-Key 时生成新键，前端应始终携带` |
| 模型降级 | 说明不报错 | `# 模型失败按降级处理，返回 200 + degraded_reason` |

### 12.11 限制条件

1. 单进程、同步处理，不引入异步队列；
2. 不支持批量接口（一次一个业务动作）；
3. 分页上限 100 条；
4. 不实现限流与熔断（单机应用）；
5. 只支持 JSON 请求体，不支持表单编码。

### 12.12 测试计划

表 12.6 M-10 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-12-01 | 字段错误定位 | 缺必填字段 | 400，`field` 指向该字段 |
| T-12-02 | 未认证 | 无令牌 | 401 `E4001` |
| T-12-03 | 角色不符 | 学生调管理接口 | 403 `E4003` |
| T-12-04 | 不存在 | 不存在的计划 ID | 404 `E1002` |
| T-12-05 | 越权不泄露 | 他人计划 ID | 404，与不存在响应完全一致 |
| T-12-06 | 版本冲突 | 过期修订号确认 | 409 `E2004` |
| T-12-07 | 数据库忙 | 模拟写锁超时 | 503 `E1005` |
| T-12-08 | 模型失败 | Provider 抛异常 | 200，`mode=mock`，带 `degraded_reason` |
| T-12-09 | 幂等透传 | 带 `Idempotency-Key` 重复提交 | 第二次返回 `replayed=true` |
| T-12-10 | 缺幂等键 | 不带键重复提交 | 视为两次操作（记录行为，提示前端必须带） |
| T-12-11 | 响应信封 | 任意成功请求 | 含 `code/message/data/request_id` |
| T-12-12 | 内部错误 | 模拟未捕获异常 | 500 `E9000`，不含堆栈与 SQL |

### 12.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-21 | 分页 | 上限 100 条 | 若看板数据多，改游标分页 |
| Q-22 | 并发限流 | 不实现 | 单机演示无需求，部署到服务器时加 |

'''

t = DOC.read_text(encoding="utf-8")
t = t.rstrip("\n") + "\n\n" + CH10 + CH11 + CH12
DOC.write_text(t, encoding="utf-8", newline="\n")
print("已插入第 10、11、12 章")

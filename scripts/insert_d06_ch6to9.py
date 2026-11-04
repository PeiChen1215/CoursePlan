"""D06 第 2 批：插入第 6 章 M-04、第 8 章 M-06、第 9 章 M-07。"""
import io
from pathlib import Path

ROOT = Path(r"D:\Gitproject\CoursePlan")
DOC = ROOT / "docs" / "04_实现" / "D06_详细设计说明书_v0.1_20261103.md"

CH6 = '''## 6 M-04 追问与抽取设计说明

### 6.1 程序描述

M-04 是**唯一调用大模型**的程序，位置在领域层，但它的产出必须经过校验才能进入计划。它做三件事：把自然语言转成结构化字段、发现缺失字段并追问、把程序结论转成学生能懂的话。

程序特点：

- **规则优先**：日期、时长、星期这类有明确写法的信息，用本地规则解析，不调模型；
- **模型只读**：模型输出只是候选，字段合法性、知识点存在性、日期合理性全部由程序复核；
- **必然降级**：模型不可用或超时，转表单，已填字段保留，主流程不受影响；
- **可复现**：模型参与的部分不进入计划快照的哈希计算（见 §9.6.5）。

### 6.2 功能

![M-04 的 IPO 图](figures/fig-6-1-ipo-m04.png)

图 6-1 M-04 追问与抽取的 IPO 图

| 功能 | 说明 |
|---|---|
| 本地规则抽取 | 相对日期、时长、星期几、数字范围 |
| 目标映射 | 把"循环那块"映射到具体知识点，四层降级 |
| 缺失字段判定 | 六项必填字段的完备性判断 |
| 追问选择 | 一次最多问 2 项，按"不填无法排程"排序 |
| 回显确认 | 把抽取结果整理成一句人话请学生确认 |
| 降级 | 10 秒预算内无结果 → 表单，标记 `mode=local` |

### 6.3 性能

表 6.1 M-04 的性能指标

| 操作 | 规模 | 目标耗时 | 说明 |
|---|---|---|---|
| 本地规则抽取 | 单句 ≤ 100 字 | ≤ 5 ms | 纯正则与词典匹配 |
| 目标映射（前两层） | 30 知识点 | ≤ 2 ms | 精确匹配 + 别名表 |
| 模型调用 | 单轮 | ≤ 10 s | 超时即降级，计入同一预算 |
| 整体交互 | 一次追问 | ≤ 10 s | 与 D02 §3.2.2 的模型辅助预算一致 |

### 6.4 输入项

表 6.2 M-04 的输入项

| 名称 | 类型 | 有效范围 | 来源 |
|---|---|---|---|
| `utterance` | string | 1–500 字 | 学生输入框 |
| `filled` | map | 已确认字段，可空 | 多轮累积 |
| `content` | ContentSnapshot | 30 知识点 + 别名 | M-02 只读快照 |
| `config` | EngineConfig | 模型预算、候选上限 | M-12 |

### 6.5 输出项

表 6.3 M-04 的输出项

| 名称 | 类型 | 内容 | 说明 |
|---|---|---|---|
| `fields` | map | 抽取到的字段 | 只含识别成功的项 |
| `questions` | list[string] | 追问问题 | **最多 2 条** |
| `candidates` | list[Concept] | 知识点候选 | 最多 5 个，含 ID 与名称 |
| `mode` | enum | `local` / `mock` / `llm` | 界面显示"离线可用" |
| `degraded_reason` | enum | `TIMEOUT` / `UNAVAILABLE` / `INVALID_OUTPUT` | 可空 |

### 6.6 算法

#### 6.6.1 目标映射的四层降级

设学生说出的目标文本为 $u$，课程知识点集合为 $C$：

$$
\\hat{c} = \\begin{cases}
\\text{exact}(u) & \\text{命中名称} \\\\
\\text{alias}(u) & \\text{命别名表} \\\\
\\text{llm}(u, C) & \\text{模型在候选内选择} \\\\
\\varnothing & \\text{以上均失败，返回候选列表}
\\end{cases}
$$

```python
def map_target(u, content, llm) -> Mapping:
    if (c := content.exact(u)):
        return Mapping.hit(c, "exact")
    if (c := content.alias(u)):          # 循环/for/while → 循环结构
        return Mapping.hit(c, "alias")
    choice = llm.pick(u, content.brief())  # 只允许从候选里挑，不允许自由生成
    if choice in content.ids():
        return Mapping.hit(content[choice], "llm")
    return Mapping.candidates(content.search(u)[:5])
```

**关键约束**：提示词要求模型"从给定候选里选一个 ID"，并在返回后校验 `choice in content.ids()`。模型编造的 ID 一律丢弃——这一条对应测试用例 T-06-06。

#### 6.6.2 相对日期归一化（纯本地规则）

以 `base_time` 的本地日期 $d_0$ 为锚：

| 说法 | 归一化 |
|---|---|
| 今天 / 明天 / 后天 | $d_0$、$d_0+1$、$d_0+2$ |
| 本周五 | 本周内的周五，若已过则顺延到下周 |
| 下周三 | **下一周**的周三（不是"最近的周三"） |
| 两周内 / 半个月 | $d_0 + 14$ |
| N 天后 / N 周后 | $d_0 + N$、$d_0 + 7N$ |

```python
def parse_relative(text, base_date) -> date | None:
    if "下周三" in text:
        return next_weekday(base_date, 2)      # 下周的周三
    if "本周" in text:
        return this_weekday(base_date, weekday_of(text))   # 已过则 +7
    if m := re.search(r"(\\d+)\\s*天", text):
        return base_date + timedelta(days=int(m.group(1)))
    ...
```

**边界**：`本周五` 若今天已是周六，必须顺延到下周，否则会得到过去的日期，被 M-03 直接拒掉。

#### 6.6.3 缺失字段判定与追问选择

必填六项：主目标、截止日期、可用时间（周模板）、每日上限、排除日期（可空）、已掌握集合（可空）。前四项缺一不可。

追问优先级（缺多项时取前 2）：

| 优先级 | 字段 | 理由 |
|---|---|---|
| 1 | 主目标 | 没有目标无法闭包 |
| 2 | 截止日期 | 没有截止无法算容量 |
| 3 | 可用时间 | 同上 |
| 4 | 每日上限 | 缺省可用 8 小时 |

```python
def pick_questions(missing, limit=2) -> list[str]:
    return [Q[f] for f in FIELD_PRIORITY if f in missing][:limit]
```

#### 6.6.4 模型调用与降级

```python
def call_model_safely(prompt, budget_s, provider) -> tuple[Out, str]:
    try:
        out = provider.complete(prompt, timeout=budget_s)
        return validate(out), "llm"
    except TimeoutError:
        return None, "TIMEOUT"
    except ProviderError:
        return None, "UNAVAILABLE"
```

降级后 `mode` 置为 `local`，界面提示"当前为离线模式，请用表单填写"，**已识别字段不清空**。

### 6.7 流程逻辑

![M-04 抽取与追问流程](figures/fig-6-2-flow-m04.png)

图 6-2 M-04 抽取与追问流程

流程要点：

1. 本地规则先跑，模型只在"规则搞不定"时才被调用，降低延迟与成本；
2. 映射失败不报错，而是**给候选让选**——这是对话式交互的关键；
3. 缺字段时只问 2 项，避免一次问太多把人问跑；
4. 模型异常走右侧降级出口，不阻断主流程。

### 6.8 接口

表 6.4 M-04 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 接口与序列化 | 函数调用 | 对话接口 |
| 被调用 | M-02 | 只读快照 | 知识点与别名 |
| 被调用 | M-12 | 适配器 | 模型 Provider（可能为 Mock） |
| 下游 | M-03 | 返回值 | 字段齐备后交其校验 |

```python
def extract(utterance: str, filled: dict, content, config) -> Extraction: ...
def build_questions(missing: set[str]) -> list[str]: ...
def explain(issue_codes: list[str]) -> str: ...   # 纯模板，不调模型
```

### 6.9 存储分配

表 6.5 M-04 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 提示词与上下文 | 约 2 KB（知识点全量注入） | 每轮构建，不缓存 |
| 抽取结果 | < 1 KB | 随请求释放 |
| 别名表 | 30 条 × 20 B | 随内容快照加载 |

### 6.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 映射降级 | 说明四层顺序不可调换 | `# 精确 → 别名 → 模型 → 候选：越往后越贵、越不确定` |
| 候选校验 | 说明为什么必须复核 | `# 模型可能编造 ID，必须校验存在性` |
| 降级 | 说明"不清空已填" | `# 降级只换输入方式，不丢用户已输入的内容` |

### 6.11 限制条件

1. 一次只处理一句输入，不做多轮上下文压缩；
2. 模型只允许在候选内挑选，不允许自由生成知识点；
3. 追问上限 2 项；
4. 单轮预算 10 秒，超时即降级；
5. 不支持语音输入；
6. 相对日期只支持中文常见说法，方言与模糊表达（"月底前吧"）归入模型处理。

### 6.12 测试计划

表 6.6 M-04 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-06-01 | 精确匹配 | "循环结构" | 直接命中，`mode=local` |
| T-06-02 | 别名匹配 | "for 循环" | 命中循环结构，`source=alias` |
| T-06-03 | 映射失败给候选 | "那个循环的东西" | 返回 ≤5 个候选，不报错 |
| T-06-04 | 相对日期-下周三 | "下周三之前" | 得到**下一周**的周三 |
| T-06-05 | 相对日期-本周已过 | 周六说"本周五" | 顺延到下周，日期在未来 |
| T-06-06 | 模型编造 ID | 模型返回不存在的 `concept_id` | 丢弃该结果，转为候选 |
| T-06-07 | 追问不超 2 项 | 缺 4 个必填字段 | 只问 2 项，且是优先级最高的两项 |
| T-06-08 | 超时降级 | Provider 抛 `TimeoutError` | `mode=local`、`degraded_reason=TIMEOUT`，已填字段保留 |
| T-06-09 | 非法 JSON 输出 | 模型返回非 JSON | 视为无效输出，转候选 |
| T-06-10 | 已掌握剔除后的空目标 | 目标全在已掌握集合 | 返回空草案标记，交 M-03 处理 |

### 6.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-11 | 多轮上下文 | 不保留历史 | 若体验不足，加最近 3 轮摘要 |
| Q-12 | 模糊日期（"月底"） | 归模型处理 | 模型不可用时，提示改用具体日期 |

'''

CH8 = '''## 8 M-06 计划校验设计说明

### 8.1 程序描述

M-06 判断一份草案"能不能用"。它是纯函数：只读草案、约束与内容，返回校验报告，不改任何数据。它是"确认"的前置闸门——**有 ERROR 就不能确认**。

程序特点：

- **顺序固定**：五项检查按 时段 → 容量 → 重叠 → 先修 → 截止 执行，前一 ERROR 即停；
- **可解释**：每个问题都带问题码、级别、受影响任务与建议；
- **确定性**：同一草案多次校验结果必须完全一致，便于复现与测试。

### 8.2 功能

![M-06 的 IPO 图](figures/fig-8-1-ipo-m06.png)

图 8-1 M-06 计划校验的 IPO 图

| 检查 | 问题码 | 级别 |
|---|---|---|
| 时段合法性 | `SLOT_INVALID` | ERROR |
| 容量 T ≤ C′ | `CAP_EXCEEDED` | ERROR |
| 时间片重叠 | `TIME_OVERLAP` | ERROR |
| 先修与学习先于练习 | `PREREQ_VIOLATED` | ERROR |
| 截止可达 | `DEADLINE_UNREACHABLE` | ERROR |
| 容量紧张（T/C > 0.8） | `CAP_TIGHT` | WARN |
| 知识点无先修且无后继 | `ISOLATED_CONCEPT` | INFO |

### 8.3 性能

表 8.1 M-06 的性能指标

| 操作 | 规模 | 目标耗时 | 说明 |
|---|---|---|---|
| 时段合法性 | 400 片 | ≤ 30 ms | 逐片与可用区间比对 |
| 重叠检测 | 400 片 | ≤ 80 ms | 按任务分组的区间排序 |
| 先修校验 | 60 任务 | ≤ 20 ms | 按拓扑序取首末片 |
| 整体 | 上述规模 | ≤ 200 ms | 对齐 D02 表 3.3 |

### 8.4 输入项

表 8.2 M-06 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| `draft` | Draft | 任务与时间片，可能含未排入项 |
| `constraint` | Constraint | C、B、C′、截止 |
| `content` | ContentSnapshot | 先修图与知识点状态 |
| `config` | EngineConfig | 阈值 0.8、单片上限 |
| `base_time` | datetime | 判断"过去时间"用 |

### 8.5 输出项

表 8.3 M-06 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `passed` | bool | 无 ERROR 即为真 |
| `issues` | list[Issue] | 码、级别、任务 ID、区间、建议 |
| `metrics` | Metrics | T、C、B、C′、缺口 D、利用率 U |

### 8.6 算法

#### 8.6.1 五项检查与短路

$$
\\text{report} = \\begin{cases}
\\text{ERROR}(k) & \\text{第 } k \\text{ 项失败，} k \\text{ 最小} \\\\
\\text{passed} & \\text{五项全部通过}
\\end{cases}
$$

```python
def validate(draft, constraint, content, config, base_time) -> Report:
    issues = []
    for check in (check_slots, check_capacity, check_overlap,
                  check_prereq, check_deadline):
        found = check(draft, constraint, content, config, base_time)
        if any(i.level == "ERROR" for i in found):
            return Report(passed=False, issues=found, metrics=metrics_of(draft, constraint))
        issues.extend(found)
    issues.extend(check_tight(draft, constraint, config))
    return Report(passed=True, issues=issues, metrics=metrics_of(draft, constraint))
```

**为什么顺序不能变**：先判时段，再判容量——如果一个任务排在"过去的时间"，报"容量不足"会误导学生。

#### 8.6.2 重叠判定（左闭右开区间代数）

两个时间片 $a = [a_s, a_e)$、$b = [b_s, b_e)$ 相交当且仅当：

$$
a_s < b_e \\ \\land \\ b_s < a_e
$$

相交区间为 $[\\max(a_s,b_s),\\ \\min(a_e,b_e))$。

```python
def overlaps(a, b):
    return a.start < b.end and b.start < a.end      # 端点相接不算重叠

def intersect(a, b):
    return (max(a.start, b.start), min(a.end, b.end))
```

**边界**：`19:00–20:00` 与 `20:00–21:00` 端点相接，**不算重叠**。这是最容易写错的地方（用 `<=` 就会误报），对应测试 T-08-02。

#### 8.6.3 先修与学习先于练习

对先修边 $u \\to v$，要求 $u$ 的最后一片结束时间不晚于 $v$ 的第一片开始时间：

$$
\\max_{s \\in slices(u)} s_e \\ \\le \\ \\min_{s \\in slices(v)} s_s
$$

同一知识点内，学习任务全部结束后练习才开始。未排入的任务不参与比较（它们没有时间片）。

#### 8.6.4 问题码聚合与建议

| 问题码 | 建议动作 |
|---|---|
| `CAP_EXCEEDED` | 延后截止、减少附加目标、增加每周时段 |
| `TIME_OVERLAP` | 重新生成草案（通常由手工改时长导致） |
| `PREREQ_VIOLATED` | 检查先修图或重新生成 |
| `DEADLINE_UNREACHABLE` | 延后截止或减少目标 |
| `CAP_TIGHT` | 提示余量紧张，不阻止确认 |

### 8.7 流程逻辑

![M-06 五项校验流程](figures/fig-8-2-flow-m06.png)

图 8-2 M-06 五项校验流程

流程要点：

1. **任一 ERROR 立即返回**，右侧出口即"阻断"，不再执行后续检查；
2. 全部通过后追加 WARN/INFO（`CAP_TIGHT`、`ISOLATED_CONCEPT`），**不阻断确认**；
3. `metrics` 无论如何都计算，界面才能显示缺口与利用率。

### 8.8 接口

表 8.4 M-06 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-05、M-07、M-10 | 函数调用 | 生成后校验、确认前复核 |
| 被调用 | M-02 | 只读快照 | 先修图 |
| 数据依赖 | 无 | — | **不写库**，纯函数 |

```python
def validate(draft, constraint, content, config, base_time) -> Report: ...
def metrics_of(draft, constraint) -> Metrics: ...
```

### 8.9 存储分配

表 8.5 M-06 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 片列表副本 | 400 × 约 120 B ≈ 48 KB | 排序时需要副本，不改入参 |
| 问题列表 | ≤ 20 条 | 通常 0–3 条 |
| 无跨调用缓存 | — | 纯函数，不持有状态 |

### 8.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 重叠判定 | 明确左闭右开 | `# 区间左闭右开，端点相接不算重叠` |
| 顺序 | 说明顺序的业务含义 | `# 先判时段：排在过去的任务不应报“容量不足”` |
| 短路 | 说明为何提前返回 | `# ERROR 即停：后续检查对不可排的草案没有意义` |

### 8.11 限制条件

1. 只校验单课程、单计划的草案；
2. 假定输入来自 M-05，不处理"任务缺知识点的孤儿数据"（由 M-05 保证）；
3. 不校验学生身份与归属（归 M-01）；
4. 不修改草案，也不产生"修正后的草案"；
5. 阈值 0.8 为全局配置，不按学科调整。

### 8.12 测试计划

表 8.6 M-06 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-08-01 | 全部通过 | 合法草案 | `passed=true`，issues 为空或仅 WARN |
| T-08-02 | 端点相接 | 19:00–20:00 与 20:00–21:00 | **不报** `TIME_OVERLAP` |
| T-08-03 | 真重叠 | 19:00–20:30 与 20:00–21:00 | 报 `TIME_OVERLAP` + 相交区间 |
| T-08-04 | 时段越界 | 片落在排除日期内 | `SLOT_INVALID` |
| T-08-05 | 超容量 | T > C′ | `CAP_EXCEEDED`，附缺口 D |
| T-08-06 | 先修倒置 | 练习排在先修知识点之前 | `PREREQ_VIOLATED` |
| T-08-07 | 学习晚于练习 | 同知识点练习片早于学习片 | `PREREQ_VIOLATED` |
| T-08-08 | 截止不可达 | 最晚片晚于截止边界 | `DEADLINE_UNREACHABLE` |
| T-08-09 | 阈值边界 | T/C = 0.80 | **不报** `CAP_TIGHT`（严格大于才报） |
| T-08-10 | 阈值超限 | T/C = 0.81 | 报 `CAP_TIGHT`，`passed` 仍为真 |
| T-08-11 | 空任务集 | 无任务 | `passed=true`，`DEADLINE` 检查跳过 |
| T-08-12 | ERROR 阻断 | 同时存在时段错与容量不足 | 只报 `SLOT_INVALID`（短路） |

### 8.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-13 | 单任务超单片上限但总时长够 | 由 M-05 拆片处理，本程序只校验片 | 若出现不可拆场景，补 `UNSPLITTABLE` 码 |
| Q-14 | 多课程扩展 | 不支持 | 需增加"跨课程先修"校验 |

'''

CH9 = '''## 9 M-07 确认与版本设计说明

### 9.1 程序描述

M-07 是**唯一写版本的入口**。它把"学生点了确认"变成"v2 生效、v1 转历史"，并且必须同时满足：只成功一次、冲突不覆盖、历史不被改。

程序特点：

- **事务型**：整个确认在一个事务内完成，任一步失败整体回滚；
- **幂等**：同一个 `confirm_key` 重复提交返回同一版本，不产生第二版；
- **乐观并发**：四项基线复核，任何一项变了就返回 `E2004`。

### 9.2 功能

![M-07 的 IPO 图](figures/fig-9-1-ipo-m09.png)

图 9-1 M-07 确认与版本的 IPO 图

| 功能 | 说明 |
|---|---|
| 确认草案 | 复核基线 → 写版本与子项 → 切指针 → 标草案已消费 |
| 幂等回放 | 同一 `confirm_key` 返回原结果 |
| 版本写入 | 版本、版本任务、时间片、校验报告一次写入 |
| 差异计算 | 新旧版本按稳定任务 ID 对比四类变化 |
| 快照哈希 | 规范化输入后计算摘要，用于判断"输入是否真变了" |

### 9.3 性能

表 9.1 M-07 的性能指标

| 操作 | 规模 | 目标耗时 |
|---|---|---|
| 确认事务 | 60 任务 + 400 片 | ≤ 300 ms |
| 差异计算 | 两版各 60 任务 | ≤ 100 ms |
| 快照哈希 | 约 40 KB JSON | ≤ 20 ms |

### 9.4 输入项

表 9.2 M-07 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| `draft_id` | int | 待确认草案 |
| `revision` | int | 客户端看到的草案修订号 |
| `confirm_key` | string | 幂等键，客户端生成 |
| `actor` | Claims | 当前学生 |

### 9.5 输出项

表 9.3 M-07 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `version_no` | int | 新版本号（首版为 1） |
| `replayed` | bool | 是否为幂等回放 |
| `diff` | Diff | 新增/移除/移动/时长变化 |
| `error` | enum | `E2004`（基线已变）/ `E1003`（状态不允许） |

### 9.6 算法

#### 9.6.1 确认事务的固定顺序

```
① BEGIN IMMEDIATE（取得写锁，阻止并发写）
② 若 confirm_key 已消费 → 返回原 result_version，结束
③ 复核四项基线：draft.revision、plan.current_version、
   plan.progress_revision、course.content_revision
④ 写 plan_version、version_task、task_slice、plan_validation
⑤ 切 study_plan.current_version，更新状态
⑥ 标草案 consumed，写 result_version_id
⑦ COMMIT
```

```python
def confirm(draft_id, revision, confirm_key, actor) -> ConfirmResult:
    with uow.transaction(immediate=True) as tx:
        d = tx.drafts.get(draft_id)
        if d.confirm_key == confirm_key and d.result_version_id:
            return ConfirmResult(d.result_version_id, replayed=True)
        assert_baseline(d, revision, tx)          # 不满足抛 E2004
        v = tx.versions.insert(d, actor)
        tx.version_tasks.insert_all(v, d.tasks)
        tx.slices.insert_all(v, d.slices)
        tx.validations.insert(v, d.report)
        tx.plans.switch_current(d.plan_id, v.version_no)
        tx.drafts.mark_consumed(d.draft_id, v.version_id, confirm_key)
        return ConfirmResult(v.version_no, replayed=False)
```

#### 9.6.2 幂等与并发

| 场景 | 处理 |
|---|---|
| 同一 `confirm_key` 再次提交 | 返回原版本，`replayed=true` |
| 两个窗口同时确认 | 先到者成功；后到者拿到写锁时基线已变 → `E2004` |
| 确认途中学生打卡 | `progress_revision` 递增 → 后确认方失败 |

$$
\\text{基线一致} \\iff r_{draft} = r'_{draft} \\ \\land \\ c_v = c'_v \\ \\land \\ p = p' \\ \\land \\ k = k'
$$

#### 9.6.3 差异计算

按**稳定任务 ID** 匹配，四类变化：

| 类型 | 判定 |
|---|---|
| 新增 | 新版本有、旧版本无 |
| 移除 | 旧版本有、新版本无 |
| 移动 | 两版都有，但首片开始日期不同 |
| 时长变化 | 两版都有，`estimated_minutes` 不同 |

```python
def diff(old: Version, new: Version) -> Diff:
    o = {t.task_id: t for t in old.tasks}
    n = {t.task_id: t for t in new.tasks}
    return Diff(
        added=[n[k] for k in n.keys() - o.keys()],
        removed=[o[k] for k in o.keys() - n.keys()],
        moved=[n[k] for k in n.keys() & o.keys() if first_day(n[k]) != first_day(o[k])],
        resized=[n[k] for k in n.keys() & o.keys() if n[k].minutes != o[k].minutes],
    )
```

**为什么按稳定任务 ID**：按"知识点 + 类型"也能匹配，但一旦某个知识点被拆成两条任务就无法对应；稳定 ID 是唯一不会误判的锚点。

#### 9.6.4 快照规范化哈希

$$
h = \\text{SHA256}\\big(\\text{canonical}(snapshot)\\big)
$$

规范化规则：键按字典序、数组按约定字段稳定排序、UTF-8 编码、去掉 `elapsed_ms` 与 `request_id`。

```python
def canonical_hash(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
```

排除耗时与请求 ID，是为了让"输入相同"能判为同一个哈希——否则每次调用都会得到新哈希，比较失去意义。

### 9.7 流程逻辑

![M-07 确认事务流程](figures/fig-9-2-flow-m09.png)

图 9-2 M-07 确认事务流程

流程要点：

1. 幂等检查在取写锁之后、复核之前，避免重复请求走完整事务；
2. 基线复核失败立即回滚并返回 `E2004`，**不做"尽力而为"的合并**；
3. 指针切换是事务内最后一步，保证"子项写完才生效"；
4. 提交成功后旧版本自动转为只读历史（由触发器保证）。

### 9.8 接口

表 9.4 M-07 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 | 函数调用 | 确认接口 |
| 被调用 | M-06 | 函数调用 | 确认前复核校验结论 |
| 被调用 | M-11 | 事务与仓储 | 写版本与子项 |
| 数据依赖 | `plan_version` 等 5 张表 | 写 | 见 D05 §4.1 |

```python
def confirm(draft_id: int, revision: int, confirm_key: str, actor: Claims) -> ConfirmResult: ...
def diff_versions(plan_id: int, a: int, b: int) -> Diff: ...
```

### 9.9 存储分配

表 9.5 M-07 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 快照 JSON | 约 40 KB / 版 | 含课程内容与全部任务 |
| 版本及其子项 | 400 片 ≈ 60 KB | 一次事务写入 |
| 写锁持有时间 | ≤ 300 ms | 模型调用不得在事务内 |

### 9.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 幂等分支 | 说明返回原结果 | `# 同一 confirm_key 重复提交，返回原版本，不新建` |
| 基线复核 | 说明四项含义 | `# 四项基线任一变化都说明用户看到的是过期草案` |
| 指针切换 | 说明为何最后做 | `# 指针最后切：子项写完才对外可见` |

### 9.11 限制条件

1. 单写者：靠 `BEGIN IMMEDIATE` 串行化，不支持多进程并发写；
2. 不合并冲突：冲突即报错，由学生重新生成；
3. 不支持回滚到历史版本（只读对比）；
4. 快照一旦写入不可修改（触发器保证）；
5. 模型调用不得出现在确认事务内。

### 9.12 测试计划

表 9.6 M-07 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-09-01 | 首次确认 | 合法草案 | 返回 `v1`，计划状态转"执行中" |
| T-09-02 | 重复确认 | 同一 `confirm_key` 两次 | 第二次 `replayed=true`，版本数不增 |
| T-09-03 | 不同键重复确认 | 草案已 consumed，用新键 | 拒绝 `E1003` |
| T-09-04 | 修订号过期 | `revision` 小于当前 | `E2004`，事务回滚 |
| T-09-05 | 进度已变 | 确认期间打卡使 `progress_revision` 递增 | `E2004` |
| T-09-06 | 课程内容已变 | `content_revision` 不一致 | `E2004` |
| T-09-07 | 差异-新增 | 新目标多一个知识点 | `diff.added` 含该任务 |
| T-09-08 | 差异-移除 | 新目标少一个知识点 | `diff.removed` 含该任务 |
| T-09-09 | 差异-移动 | 同一任务首片日期改变 | `diff.moved` 含该任务 |
| T-09-10 | 差异-时长 | 覆盖值改变 | `diff.resized` 含该任务 |
| T-09-11 | 已完成任务不被移动 | 调整时含已完成任务 | 该任务仍在原日期，`frozen=1` |
| T-09-12 | 哈希稳定性 | 同一输入两次 | 两个 `input_hash` 完全相同 |

### 9.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-15 | 版本回滚 | 不支持，只读对比 | 若需要，新增"以 v1 为基线重新生成"而非回滚 |
| Q-16 | 并发度 | 单写者串行 | 多用户时改用 WAL + 重试，或换 PostgreSQL |

'''

t = DOC.read_text(encoding="utf-8")
anchor7 = "## 7 M-05 分解与排程设计说明"
assert anchor7 in t
t = t.replace(anchor7, CH6 + anchor7, 1)
t = t.rstrip("\n") + "\n\n" + CH8 + CH9
DOC.write_text(t, encoding="utf-8", newline="\n")
print("已插入第 6、8、9 章")

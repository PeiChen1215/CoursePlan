"""D06 第 4 批：插入第 13/14 章与附录 A/B/C。"""
import io
from pathlib import Path

ROOT = Path(r"D:\Gitproject\CoursePlan")
DOC = ROOT / "docs" / "04_实现" / "D06_详细设计说明书_v0.1_20261103.md"

CH13 = '''## 13 M-11 存储访问设计说明

### 13.1 程序描述

M-11 是系统唯一直接接触 SQLite 的程序。所有领域程序通过仓储接口读写，禁止在业务代码里出现 SQL。它同时负责事务边界、迁移与备份。

程序特点：

- **唯一的数据出入口**：换库只改这一层；
- **事务边界在用例层**：一个业务动作一个事务，不跨请求持有连接；
- **对触发器友好**：触发器的报错在这里统一映射为业务错误码。

### 13.2 功能

![M-11 的 IPO 图](figures/fig-13-1-ipo-m11.png)

图 13-1 M-11 存储访问的 IPO 图

| 功能 | 说明 |
|---|---|
| 仓储读写 | 16 张表的对象映射与查询 |
| 事务管理 | `UnitOfWork` 开启、提交、回滚 |
| 乐观锁 | 版本号 / 进度修订号比对 |
| 迁移 | 按 `schema_version` 顺序执行，失败回滚 |
| 备份 | 一致性备份 + 完整性校验，保留 7 份 |

### 13.3 性能

表 13.1 M-11 的性能指标

| 操作 | 规模 | 目标耗时 |
|---|---|---|
| 单条按主键读 | 单行 | ≤ 2 ms |
| 计划聚合查询 | ≤ 400 片 | ≤ 30 ms |
| 事务提交 | 单事务 ≤ 500 行 | ≤ 50 ms |
| 一致性备份 | 数据库 < 100 MB | ≤ 2 s |

### 13.4 输入项

表 13.2 M-11 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| 查询条件 | 键值 / 范围 | 由仓储方法决定 |
| 领域对象 | dataclass | 写入时的行映射来源 |
| 事务声明 | 上下文 | 由调用方 `with uow.transaction()` 声明 |
| 迁移脚本 | `scripts/schema.sql` 或迁移文件 | 建库与升级 |

### 13.5 输出项

表 13.3 M-11 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| 记录集 | list[Row] | 已映射为领域对象 |
| 提交结果 | Result | 影响行数或冲突异常 |
| 备份结果 | BackupResult | 文件路径、大小、校验结论 |

### 13.6 算法

#### 13.6.1 UnitOfWork 与事务边界

```python
class UnitOfWork:
    def __enter__(self):
        self.conn = connect()                 # 每事务一条连接
        self.conn.execute("BEGIN IMMEDIATE")  # 立刻拿写锁，避免升级死锁
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()                      # 连接必须随事务释放
```

**规则**：连接不得跨层传递；领域程序只接收仓储接口，不接收连接对象。

#### 13.6.2 乐观锁

更新前比对"读到的修订号"与"库里的修订号"：

$$
\\text{允许更新} \\iff rev_{read} = rev_{db}
$$

```python
def update_with_guard(row, expected_rev: int):
    cur = db.execute(
        "UPDATE study_plan SET status=?, updated_at=? , progress_revision=progress_revision+1 "
        "WHERE plan_id=? AND progress_revision=?",
        (row.status, row.updated_at, row.plan_id, expected_rev))
    if cur.rowcount == 0:
        raise VersionConflict("E2004")
```

用 `WHERE` 带条件实现，比"先查再比再改"少一次往返，且天然原子。

#### 13.6.3 仓储映射与触发器错误

16 张表与领域对象的对应见 D05 §4.1。需要特别处理两类数据库错误：

| 触发场景 | SQLite 报错 | 映射为 |
|---|---|---|
| 复合外键失败（跨课程/跨计划） | `FOREIGN KEY constraint failed` | `E1001`（参数错） |
| 不可变触发器（改版本/删事件） | `ABORT: 计划版本不可修改` | `E1003`（状态不允许） |
| 唯一约束（重复 done、重复确认） | `UNIQUE constraint failed` | `E1003` 或幂等返回 |
| 忙等超时 | `database is locked` | `E1005` |

```python
def translate_sqlite_error(e: sqlite3.Error) -> AppError:
    msg = str(e)
    if "FOREIGN KEY" in msg: return ValidationError("E1001", msg)
    if "不可修改" in msg or "不可删除" in msg: return StateError("E1003", msg)
    if "UNIQUE" in msg: return StateError("E1003", msg)
    if "locked" in msg or "busy" in msg: return Busy("E1005")
    return InternalError(msg)
```

#### 13.6.4 迁移执行

```python
def migrate(target_version: str):
    backup()                                  # 迁移前强制备份
    cur = schema_version()
    for script in sorted(pending(cur, target_version)):
        try:
            with uow.transaction():
                run(script)
                set_schema_version(script.version)
        except Exception:
            restore_latest_backup()           # 失败即回到迁移前
            raise
```

**禁止**用"重复执行 `CREATE TABLE IF NOT EXISTS`"冒充迁移——那不会修改已有表的列。

#### 13.6.5 一致性备份

WAL 模式下不可只复制主库文件，必须用官方备份接口：

```python
def backup() -> BackupResult:
    tmp = temp_path()
    src = sqlite3.connect(DB)
    dst = sqlite3.connect(tmp)
    src.backup(dst)                            # 一致性快照
    check(dst, "PRAGMA integrity_check")
    check(dst, "PRAGMA foreign_key_check")
    final = rename_with_timestamp(tmp)
    prune(keep=7)                              # 只保留最近 7 份成功备份
    return BackupResult(final, size(final))
```

### 13.7 流程逻辑

![M-11 事务与备份流程](figures/fig-13-2-flow-m11.png)

图 13-2 M-11 事务与备份流程

流程要点：

1. 事务开启即取写锁，避免"读后升级写锁"的竞争；
2. 触发器与约束报错统一转成业务错误码，不把 SQL 文本透给前端；
3. 任何异常整体回滚，不留半提交状态。

### 13.8 接口

表 13.4 M-11 的调用关系

| 方向 | 对象 | 说明 |
|---|---|---|
| 上层调用方 | 全部领域程序 | 经仓储接口 |
| 被调用 | SQLite 文件 | 参数化 SQL |
| 对外 | 备份脚本 / 健康检查 | 一致性备份与状态查询 |

```python
def transaction(immediate=True) -> ContextManager["UnitOfWork"]: ...
def backup() -> BackupResult: ...
def health() -> HealthStatus: ...
```

### 13.9 存储分配

表 13.5 M-11 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 连接 | 1 条 / 事务 | 事务结束即关闭 |
| 页缓存 | 默认约 2 MB | 数据量小，基本常驻 |
| 备份占用 | 7 份 × 单库大小 | 预留 1 GB 可用空间 |

### 13.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 事务 | 说明为何用 IMMEDIATE | `# 立刻取写锁：避免先读后升级写锁时的死锁` |
| 错误映射 | 说明映射依据 | `# 触发器 ABORT 的语言是业务约定，据此映射 E1003` |
| 备份 | 说明不可直接复制 | `# WAL 模式不能只复制主库，必须用 backup API` |

### 13.11 限制条件

1. 单进程单写者，写操作串行；
2. 不支持分布式事务；
3. 迁移期间需停服，不做在线迁移；
4. 备份不加密，靠文件权限保护；
5. SQLite 版本需 ≥ 3.35（部分索引与 JSON 函数）。

### 13.12 测试计划

表 13.6 M-11 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-13-01 | 事务回滚 | 事务内抛异常 | 库中无残留行 |
| T-13-02 | 乐观锁冲突 | `expected_rev` 与库中不符 | 抛 `E2004`，不更新 |
| T-13-03 | 复合外键 | 跨课程插入先修 | 抛 `E1001` |
| T-13-04 | 触发器拦截 | 尝试 UPDATE 版本 | 抛 `E1003`，映射后不含 SQL 文本 |
| T-13-05 | 唯一约束 | 重复 `done` | 抛 `E1003` |
| T-13-06 | 忙锁映射 | 另一连接持写锁 | 等待 3 s 后抛 `E1005` |
| T-13-07 | 备份校验 | 备份后跑 `integrity_check` | `ok` |
| T-13-08 | 备份保留 | 连续备份 9 次 | 目录中只剩 7 份 |
| T-13-09 | 迁移幂等 | 重复执行同一迁移 | 无副作用，版本号不变 |
| T-13-10 | 迁移失败回滚 | 中途语法错误 | 恢复到迁移前状态 |
| T-13-11 | 外键完整性 | 随机删行后 `foreign_key_check` | 能报出孤儿行 |

### 13.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-23 | 大表分页 | 不分页 | 数据量到万级时改游标分页 |
| Q-24 | 备份加密 | 不加密 | 若含真实数据，加 GPG 或 SQLCipher |

'''

CH14 = '''## 14 M-12 配置与日志设计说明

### 14.1 程序描述

M-12 负责"进程启动时的装配"与"运行期的可观测性"：配置加载与校验、日志格式化与脱敏、健康检查、模型适配器的选择与降级。

程序特点：

- **启动即校验**：配置越界直接拒绝启动，不带着错配置跑；
- **脱敏优先**：日志功能先写"绝不能落盘"的字段清单，再写格式；
- **可降级**：模型不可用不影响主流程，标记模式即可。

### 14.2 功能

![M-12 的 IPO 图](figures/fig-14-1-ipo-m12.png)

图 14-1 M-12 配置与日志的 IPO 图

| 功能 | 说明 |
|---|---|
| 配置加载 | 默认值 < 环境变量 < 显式参数 |
| 取值校验 | 范围检查，越界拒绝启动并指出键名 |
| 日志 | 结构化输出 + 脱敏 |
| 健康检查 | 主服务 / 数据库 / 模型模式 / 备份状态 |
| 适配器切换 | `mock` / `real` / `auto`，失败降级 |

### 14.3 性能

表 14.1 M-12 的性能指标

| 操作 | 目标耗时 |
|---|---|
| 配置加载与校验 | ≤ 20 ms（启动时一次） |
| 单条日志写入 | ≤ 1 ms |
| 健康检查 | ≤ 100 ms（含一次数据库查询） |

### 14.4 输入项

表 14.2 M-12 的输入项

| 名称 | 类型 | 说明 |
|---|---|---|
| 默认配置 | 常量表 | 见 §2 表 2.2 |
| 环境变量 | `DSH_*` 前缀 | 部署时覆盖 |
| 显式参数 | 启动参数 | 测试与演示用 |
| 运行期事件 | 请求、异常、耗时 | 日志来源 |

### 14.5 输出项

表 14.3 M-12 的输出项

| 名称 | 类型 | 内容 |
|---|---|---|
| `config` | EngineConfig | 装配后的配置对象 |
| 日志行 | JSON | `ts`、`level`、`event`、`request_id`、`duration_ms` |
| `health` | enum × 4 | 四项状态与总判定 |
| `provider` | Adapter | 模型适配器实例 |

### 14.6 算法

#### 14.6.1 配置优先级

$$
\\text{cfg}(k) = \\text{arg}(k) \\ \\text{若存在}，\\ \\text{否则}\\ \\text{env}(k)\\ \\text{若存在}，\\ \\text{否则}\\ \\text{default}(k)
$$

```python
def load(overrides: dict) -> EngineConfig:
    raw = {}
    for k, default in DEFAULTS.items():
        raw[k] = overrides.get(k, os.getenv("DSH_" + k.upper(), default))
    return validate(raw)
```

#### 14.6.2 取值校验

每个键有类型与范围，越界即中止启动：

| 键 | 范围 | 越界后果 |
|---|---|---|
| `BUFFER_RATIO` | 0–0.5 | 拒绝启动 |
| `STUDY_RATIO` | 0.1–0.9 | 拒绝启动 |
| `MAX_SLICES_PER_TASK` | 1–500 | 拒绝启动 |
| `TOKEN_TTL_HOURS` | 1–72 | 拒绝启动 |
| `MODEL_TIMEOUT_SECONDS` | 1–60 | 拒绝启动 |

```python
def validate(raw) -> EngineConfig:
    for key, spec in SPECS.items():
        v = coerce(key, raw[key])
        if not spec.min <= v <= spec.max:
            raise ConfigError(f"{key}={v} 越界（允许 {spec.min}–{spec.max}）")
    return EngineConfig(**raw)
```

报错信息必须含**键名与允许范围**，否则部署时无从排查。

#### 14.6.3 日志脱敏

黑名单字段一律替换为 `***`：

| 字段 | 原因 |
|---|---|
| `password`、`password_hash` | 口令 |
| `token`、`Authorization` | 会话凭证 |
| `utterance` 全文 | 学生自由输入可能含隐私 |
| `deadline`、`availability` 明细 | 精确日程属私人信息 |

```python
REDACT = {"password", "password_hash", "token", "authorization", "utterance"}

def sanitize(record: dict) -> dict:
    return {k: ("***" if k.lower() in REDACT else v) for k, v in record.items()}
```

#### 14.6.4 健康检查分级

| 项 | 判据 | 失败含义 |
|---|---|---|
| 主服务 | 进程存活 | 服务不可用 |
| 数据库 | `SELECT 1` 成功且可写 | 只读或锁定 |
| 模型模式 | `mock` / `real` / `auto` 当前值 | 仅提示，不影响可用性 |
| 备份 | 最近一次成功时间 ≤ 24 h | 提示需要补做 |

```python
def health() -> dict:
    return {
        "service": "ok",
        "database": probe_db(),          # ok / readonly / locked
        "provider": config.provider_mode,
        "backup": backup_age_hours(),    # 超 24 小时给 warn
    }
```

#### 14.6.5 模型适配器切换

```python
def build_provider(mode: str, cfg) -> Adapter:
    if mode == "mock":
        return MockProvider()
    if mode == "real":
        return RealProvider(cfg.key, timeout=cfg.MODEL_TIMEOUT_SECONDS)
    # auto：探测一次，失败即降级
    try:
        p = RealProvider(cfg.key, timeout=cfg.MODEL_TIMEOUT_SECONDS)
        p.probe()
        return p
    except Exception:
        log.warn("provider_fallback", reason="probe_failed")
        return MockProvider()
```

### 14.7 流程逻辑

![M-12 配置装配与降级流程](figures/fig-14-2-flow-m12.png)

图 14-2 M-12 配置装配与降级流程

流程要点：

1. 配置校验在装配之前，**错配置不进入运行期**；
2. `auto` 模式先探测再决定，探测失败只降级不退出；
3. 健康检查四项独立，区分"不可用"与"可降级"。

### 14.8 接口

表 14.4 M-12 的调用关系

| 方向 | 对象 | 说明 |
|---|---|---|
| 上层调用方 | 全部程序 | 读取配置 |
| 上层调用方 | M-04 | 取模型适配器 |
| 对外 | 运维 | 健康检查接口、日志文件 |

```python
def load(overrides: dict) -> EngineConfig: ...
def build_provider(mode: str, cfg) -> Adapter: ...
def health() -> dict: ...
def sanitize(record: dict) -> dict: ...
```

### 14.9 存储分配

表 14.5 M-12 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 配置对象 | < 2 KB | 进程内单例 |
| 日志 | 按日切分，约 1–5 MB/日 | 保留 14 天 |
| 适配器 | 1 个实例 | 不随请求创建 |

### 14.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 脱敏 | 说明"为什么这些字段" | `# utterance 全文不落盘：可能含学生隐私` |
| 校验 | 说明报错要含键名 | `# 报错必须含键名与范围，否则部署时无从排查` |
| 降级 | 说明不退出 | `# 探测失败只降级，不阻断启动` |

### 14.11 限制条件

1. 配置只支持"启动时读取"，不支持热更新；
2. 日志同步写，不引入异步队列；
3. 健康检查不检测外部网站连通性；
4. 不支持多套配置文件切换（演示/生产靠环境变量区分）；
5. 模型密钥只从环境变量读取，不写入配置文件。

### 14.12 测试计划

表 14.6 M-12 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-14-01 | 默认值生效 | 无任何覆盖 | 使用 §2 表 2.2 的默认值 |
| T-14-02 | 环境变量覆盖 | `DSH_STUDY_RATIO=0.8` | 生效，其余仍为默认 |
| T-14-03 | 显式参数优先 | 参数与环境变量都设 | 参数生效 |
| T-14-04 | 越界拒绝启动 | `BUFFER_RATIO=0.9` | 拒绝启动，报错含键名与范围 |
| T-14-05 | 类型错误 | `MAX_SLICES_PER_TASK=abc` | 拒绝启动 |
| T-14-06 | 日志脱敏 | 记录含 `password` | 输出为 `***` |
| T-14-07 | 对话不落盘 | 记录含 `utterance` | 替换为 `***` |
| T-14-08 | mock 断网可用 | `mode=mock`、断网 | 主流程正常 |
| T-14-09 | auto 降级 | 真实 Provider 探测失败 | 切 mock，记录 `provider_fallback` |
| T-14-10 | 健康检查四项 | 正常环境 | 四项均有值，总判定为 ok |
| T-14-11 | 备份超期 | 最近备份 30 小时前 | 备份项给 warn |

### 14.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-25 | 日志轮转 | 按日切分 + 保留 14 天 | 量大时改异步与压缩 |
| Q-26 | 配置热更新 | 不支持 | 需重启，演示场景可接受 |

'''

APPENDIX = '''## 附录 A 函数清单

表 A.1 关键函数与所属章节

| 文件 | 函数 / 类 | 职责 | 所属章 | 估算行数 |
|---|---|---|---|---|
| `auth/service.py` | `login` | 认证并签发令牌 | 3 | 40 |
| `auth/service.py` | `authenticate` | 解析并校验令牌 | 3 | 25 |
| `auth/service.py` | `require_owner` | 归属校验（404 不泄露） | 3 | 15 |
| `content/service.py` | `save_concept` | 知识点保存与唯一性校验 | 4 | 35 |
| `content/service.py` | `submit_prereqs` | 批量先修提交与整批回滚 | 4 | 55 |
| `content/cycle.py` | `detect_cycle` | DFS 三色环检测 | 4 | 45 |
| `content/service.py` | `disable_concept` | 引用影响分析 | 4 | 30 |
| `constraint/service.py` | `normalize` | 约束字段规范化 | 5 | 50 |
| `constraint/capacity.py` | `expand` | 可用时段展开 | 5, 7 | 40 |
| `constraint/capacity.py` | `compute_capacity` | C / B / C′ 计算 | 5 | 15 |
| `agent/extract.py` | `map_target` | 目标映射四层降级 | 6 | 45 |
| `agent/extract.py` | `parse_relative` | 相对日期归一化 | 6 | 60 |
| `agent/client.py` | `call_model_safely` | 预算内调用与降级 | 6 | 30 |
| `planner/closure.py` | `prereq_closure` | 先修闭包 | 7 | 30 |
| `planner/split.py` | `split_tasks` | 7:3 拆分 | 7 | 25 |
| `planner/topo.py` | `topo_order` | 稳定拓扑排序 | 7 | 40 |
| `planner/pack.py` | `pack` | 装箱与拆片 | 7 | 70 |
| `planner/engine.py` | `generate_plan` | 编排上述步骤 | 7 | 35 |
| `validation/checks.py` | `validate` | 五项顺序校验 | 8 | 60 |
| `validation/overlap.py` | `overlaps` / `intersect` | 左闭右开区间判定 | 8 | 15 |
| `version/service.py` | `confirm` | 确认事务 | 9 | 80 |
| `version/diff.py` | `diff` | 版本差异四类 | 9 | 45 |
| `version/snapshot.py` | `canonical_hash` | 快照规范化哈希 | 9 | 15 |
| `progress/service.py` | `submit` | 打卡与更正 | 10 | 55 |
| `progress/stats.py` | `completion_rate` | 完成率与逾期 | 10 | 30 |
| `board/service.py` | `build_view` | 看板数据组装 | 11 | 50 |
| `api/routes.py` | `handle` | 请求管道 | 12 | 40 |
| `api/errors.py` | `map_error` | 异常到错误码 | 12 | 30 |
| `storage/uow.py` | `UnitOfWork` | 事务边界 | 13 | 40 |
| `storage/repo.py` | 各仓储方法 | 表到对象映射 | 13 | 200 |
| `storage/backup.py` | `backup` | 一致性备份 | 13 | 45 |
| `infra/config.py` | `load` / `validate` | 配置装配与校验 | 14 | 50 |
| `infra/logging.py` | `sanitize` | 日志脱敏 | 14 | 25 |
| `infra/health.py` | `health` | 健康检查分级 | 14 | 30 |

> 估算合计数千行，与 D01 的规模假设（源码 < 5000 行）一致；实际行数以编码为准。

## 附录 B 图表清单

表 B.1 图清单

| 图号 | 图题 | 所在章节 |
|---|---|---|
| 图 2-1 | 程序系统层次结构图 | 2 |
| 图 3-1 | M-01 认证与权限的 IPO 图 | 3.2 |
| 图 3-2 | M-01 登录判定流程 | 3.7 |
| 图 4-1 | M-02 课程内容管理的 IPO 图 | 4.2 |
| 图 4-2 | M-02 先修批量提交流程 | 4.7 |
| 图 5-1 | M-03 约束与容量的 IPO 图 | 5.2 |
| 图 5-2 | M-03 约束提交流程 | 5.7 |
| 图 6-1 | M-04 追问与抽取的 IPO 图 | 6.2 |
| 图 6-2 | M-04 抽取与追问流程 | 6.7 |
| 图 7-1 | M-05 分解与排程的 IPO 图 | 7.2 |
| 图 7-2 | M-05 主流程图 | 7.7 |
| 图 8-1 | M-06 计划校验的 IPO 图 | 8.2 |
| 图 8-2 | M-06 五项校验流程 | 8.7 |
| 图 9-1 | M-07 确认与版本的 IPO 图 | 9.2 |
| 图 9-2 | M-07 确认事务流程 | 9.7 |
| 图 10-1 | M-08 进度与事件的 IPO 图 | 10.2 |
| 图 10-2 | M-08 打卡与更正流程 | 10.7 |
| 图 11-1 | M-09 看板与前端组件的 IPO 图 | 11.2 |
| 图 11-2 | M-09 看板渲染流程 | 11.7 |
| 图 12-1 | M-10 接口与序列化的 IPO 图 | 12.2 |
| 图 12-2 | M-10 请求处理管道 | 12.7 |
| 图 13-1 | M-11 存储访问的 IPO 图 | 13.2 |
| 图 13-2 | M-11 事务与备份流程 | 13.7 |
| 图 14-1 | M-12 配置与日志的 IPO 图 | 14.2 |
| 图 14-2 | M-12 配置装配与降级流程 | 14.7 |

表 B.2 表清单（按章汇总）

| 章 | 表号范围 | 数量 |
|---|---|---|
| 2 | 表 2.1～2.2 | 2 |
| 3 | 表 3.1～3.6 | 6 |
| 4 | 表 4.1～4.6 | 6 |
| 5 | 表 5.1～5.6 | 6 |
| 6 | 表 6.1～6.6 | 6 |
| 7 | 表 7.1～7.5 | 5 |
| 8 | 表 8.1～8.6 | 6 |
| 9 | 表 9.1～9.6 | 6 |
| 10 | 表 10.1～10.6 | 6 |
| 11 | 表 11.1～11.6 | 6 |
| 12 | 表 12.1～12.6 | 6 |
| 13 | 表 13.1～13.6 | 6 |
| 14 | 表 14.1～14.6 | 6 |
| 附录 | 表 A.1、B.1、B.2、C.1 | 4 |

## 附录 C 与上游文档的对应关系

表 C.1 需求—模块—数据三向对应

| D02 需求 | D04 模块 | D05 数据表 | 本文章节 |
|---|---|---|---|
| F-01 登录与角色 | M-01 | `app_user` | 第 3 章 |
| F-02～F-05 内容维护 | M-02 | `course`、`concept`、`prerequisite`、`resource`、`concept_resource` | 第 4 章 |
| F-06 约束与容量 | M-03 | `plan_constraint` | 第 5 章 |
| F-07 追问与补全 | M-04 | — | 第 6 章 |
| F-08 分解与排程 | M-05 | `plan_task`、`version_task`、`task_slice` | 第 7 章 |
| F-09 计划校验 | M-06 | `plan_validation` | 第 8 章 |
| F-10 确认与进度 | M-07、M-08 | `plan_version`、`learning_event` | 第 9、10 章 |
| F-11 计划调整 | M-05、M-07 | `plan_draft`、`plan_version` | 第 7、9 章 |
| F-12 版本与差异 | M-07 | `plan_version` | 第 9 章 |
| F-13 看板 | M-09 | 只读汇总 | 第 11 章 |
| 全局 | M-10、M-11、M-12 | `schema_meta` | 第 12～14 章 |

'''

t = DOC.read_text(encoding="utf-8")
t = t.rstrip("\n") + "\n\n" + CH13 + CH14 + APPENDIX
DOC.write_text(t, encoding="utf-8", newline="\n")
print("已插入第 13、14 章与附录 A/B/C")

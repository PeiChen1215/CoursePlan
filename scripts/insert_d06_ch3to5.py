"""D06 第 1 批：插入第 3 章 M-01、第 4 章 M-02、第 5 章 M-03。"""
import io
from pathlib import Path

ROOT = Path(r"D:\Gitproject\CoursePlan")
DOC = ROOT / "docs" / "04_实现" / "D06_详细设计说明书_v0.1_20261103.md"

CH3 = '''## 3 M-01 认证与权限设计说明

### 3.1 程序描述

M-01 回答两个问题：**你是谁**（认证）、**你能碰什么**（授权）。它位于接口与应用层，是所有私有接口的第一道闸门。

程序特点：

- **登录是唯一写操作**：失败计数、锁定时间、最近登录时间需要落库；其余接口只做校验，不写库；
- **令牌无状态**：不在服务端保存会话表，每次请求用签名验令牌，避免"重启后所有人掉线"；
- **归属校验前置**：任何涉及学生私有数据的请求，先过归属判定，再进业务逻辑，避免"先查后判"泄露存在性。

### 3.2 功能

![M-01 的 IPO 图](figures/fig-3-1-ipo-m01.png)

图 3-1 M-01 认证与权限的 IPO 图

| 功能 | 说明 |
|---|---|
| 登录认证 | 校验账号存在、是否锁定、口令散列是否匹配 |
| 令牌签发 | 签发含角色与过期时间的令牌，返回给学生 |
| 令牌校验 | 每个请求验证签名与过期时间，解析出 `sub` 与 `role` |
| 角色判定 | 学生接口拒绝管理员越权访问，反之亦然 |
| 归属校验 | 操作对象必须属于当前登录学生；不属于时按"不存在"处理 |

**不归本程序管**：注册、找回密码、多设备会话管理、令牌吊销（见 §3.11）。

### 3.3 性能

表 3.1 M-01 的性能指标

| 操作 | 规模 | 目标耗时 | 说明 |
|---|---|---|---|
| 登录（含散列比对） | 单次 | ≤ 300 ms | bcrypt 工作因子 10，比对约 80–120 ms，其余为查询与写库 |
| 令牌校验 | 单次请求 | ≤ 2 ms | HMAC-SHA256 验签 + JSON 解析，纯内存 |
| 归属校验 | 单次请求 | ≤ 5 ms | 一次主键查询，命中索引 |
| 失败计数更新 | 单次失败 | ≤ 10 ms | 单行 UPDATE |

### 3.4 输入项

表 3.2 M-01 的输入项

| 名称 | 类型 | 有效范围 | 来源 | 必填 |
|---|---|---|---|---|
| `username` | string | 3–32 字符 | 登录表单 | 登录时必填 |
| `password` | string | ≥ 8 字符，含字母与数字 | 登录表单 | 登录时必填 |
| `token` | string | 签发格式，长度 ≤ 1024 | 请求头 `Authorization` | 私有接口必填 |
| `object_id` | int | 目标对象主键 | 路径参数 | 归属校验时必填 |
| `required_role` | enum | `student` / `admin` | 路由声明 | 是 |

### 3.5 输出项

表 3.3 M-01 的输出项

| 名称 | 类型 | 内容 | 说明 |
|---|---|---|---|
| `token` | string | 签名令牌 | 仅在登录成功时返回 |
| `role` | enum | `student` / `admin` | 前端据此渲染菜单 |
| `expires_at` | string | UTC ISO 8601 | 令牌过期时刻 |
| `error_code` | enum | `E4001`（未认证）/ `E4003`（无权限）/ `E1002`（不存在） | 见 §3.6.4 |
| `lock_remaining_seconds` | int | ≥ 0 | 锁定期间返回剩余秒数 |

### 3.6 算法

#### 3.6.1 口令散列校验

口令只存散列，不存明文。比对用库函数的常数时间比较，避免通过响应时间推断前缀：

```python
def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt 自带盐与代价因子；不要用 == 比较散列字符串
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

#### 3.6.2 失败计数与锁定

设连续失败次数 $f$，锁定边界 $L$：

$$
L = \\begin{cases} now + 300\\ \\text{s} & f \\ge 5 \\\\ \\text{不变} & f < 5 \\end{cases}
$$

登录成功时 $f \\leftarrow 0$、$L \\leftarrow \\text{NULL}$。**锁定期内即使口令正确也拒绝**，否则锁定形同虚设。

```python
def on_login_failed(user, now):
    user.failed_attempts += 1
    if user.failed_attempts >= config.LOCK_FAIL_LIMIT:
        user.locked_until = now + timedelta(minutes=config.LOCK_MINUTES)
    save(user)

def is_locked(user, now) -> bool:
    return user.locked_until is not None and user.locked_until > now
```

#### 3.6.3 令牌签发与校验

令牌采用 `payload.signature` 两段式：`payload` 是 Base64URL 的 JSON（含 `sub`、`role`、`exp`），`signature` 是对 payload 的 HMAC-SHA256。

$$
\\text{exp} = now + \\text{TOKEN\\_TTL\\_HOURS} \\times 3600
$$

```python
def issue_token(user, now) -> tuple[str, datetime]:
    exp = now + timedelta(hours=config.TOKEN_TTL_HOURS)
    payload = {"sub": user.id, "role": user.role, "exp": int(exp.timestamp())}
    body = b64u(json.dumps(payload, sort_keys=True))
    return body + "." + b64u(hmac_sha256(key, body)), exp

def parse_token(token, now) -> Claims:
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, b64u(hmac_sha256(key, body))):
        raise Unauthorized("E4001")
    claims = json.loads(b64u_decode(body))
    if claims["exp"] <= int(now.timestamp()):
        raise Unauthorized("E4001")
    return claims
```

#### 3.6.4 403 与 404 的区分规则

**这是本程序最容易被挑错的地方**：越权时返回 403 会泄露"这个对象存在"。

| 情形 | 返回 | 理由 |
|---|---|---|
| 未携带令牌 / 令牌无效 / 已过期 | 401 `E4001` | 身份未确立 |
| 角色不符（学生访问管理接口） | 403 `E4003` | 接口是公开的，不存在泄露问题 |
| 对象不存在 | 404 `E1002` | — |
| 对象存在但不属于当前学生 | **404 `E1002`** | 与"不存在"同响应，不泄露存在性 |
| 对象存在、属于本人但状态不允许 | 400 `E1003` | 此时无需隐藏 |

```python
def require_owner(obj, claims):
    if obj is None or obj.owner_id != claims.sub:
        raise NotFound("E1002")     # 故意不区分“不存在”与“不是你的”
```

### 3.7 流程逻辑

![M-01 登录判定流程](figures/fig-3-2-flow-m01.png)

图 3-2 M-01 登录判定流程

流程要点：

1. **账号不存在与口令错误返回同一响应**（401，同一文案），防止账号枚举；
2. **锁定判定在口令比对之前**，锁定期内不消耗比对开销，也不因"口令恰好正确"而放行；
3. 失败计数只在"账号存在且口令错"时累加，账号不存在不计数（否则可被用来探测）；
4. 成功后一次性完成三件事：清零计数、签发令牌、记录最近登录时间，在同一事务内。

### 3.8 接口

表 3.4 M-01 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 接口与序列化 | 函数调用（依赖注入） | 每个私有路由先调用 `authenticate` |
| 被调用 | M-11 存储访问 | 仓储 | 读取用户、写入失败计数 |
| 数据依赖 | `app_user` 表 | 只读 + 单行写 | 见 D05 §4.1.2 |

```python
def authenticate(token: str | None, now: datetime) -> Claims: ...
def require_role(claims: Claims, role: str) -> None: ...
def require_owner(obj, claims: Claims) -> None: ...
def login(username: str, password: str, now: datetime) -> tuple[str, datetime, str]: ...
```

### 3.9 存储分配

表 3.5 M-01 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 令牌解析结果 | 每请求约 0.3 KB | 请求结束即释放，不缓存 |
| 用户记录 | 50 条 × 约 0.5 KB | 由 M-11 缓存，本程序不额外持有 |
| 会话状态 | **无** | 无状态令牌，服务端不存会话表 |

### 3.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 模块首部 | 说明"为什么无状态" | `"""无状态认证：令牌自带角色与过期时间，不依赖会话表。"""` |
| 归属判定 | 说明 404 的用意 | `# 故意返回 404 而非 403：不泄露对象是否存在` |
| 锁定逻辑 | 说明顺序不可调换 | `# 锁定判定必须在口令比对之前，否则锁定期内可试错` |

### 3.11 限制条件

1. **令牌不可吊销**：本期不实现黑名单，学生改密码后旧令牌仍有效至过期（最长 24 小时）；
2. **无刷新令牌**：过期需重新登录；
3. 锁定按账号而非按 IP，不防分布式撞库（单机应用，风险可接受）；
4. 依赖服务器时钟；时钟回拨会导致令牌提前失效；
5. 口令强度只做长度与字符类型校验，不拦截常见弱口令；
6. 单进程运行，令牌密钥从环境变量读取，不落库。

### 3.12 测试计划

表 3.6 M-01 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-01-01 | 正常登录 | 正确账号口令 | 返回令牌、角色 `student`、24 小时有效期 |
| T-01-02 | 账号不存在 | 不存在的账号 | 401，文案与口令错误完全一致 |
| T-01-03 | 口令错误 | 正确账号 + 错口令 | 401，失败计数 +1 |
| T-01-04 | 连续失败 5 次 | 5 次错误口令 | 第 5 次后 `locked_until` 已置，返回剩余秒数 |
| T-01-05 | 锁定期内正确口令 | 锁定期 + 正确口令 | 401（**不放行**） |
| T-01-06 | 锁定到期 | 锁定时间已过 | 正常登录，计数清零 |
| T-01-07 | 令牌过期 | `exp` 早于当前时间 | 401 `E4001` |
| T-01-08 | 令牌签名被篡改 | 改动 payload 一位 | 401 `E4001` |
| T-01-09 | 学生访问管理接口 | 学生令牌 + 管理路由 | 403 `E4003` |
| T-01-10 | 访问他人计划 | 学生 A 的令牌 + 学生 B 的计划 ID | 404 `E1002`（与不存在同响应） |
| T-01-11 | 访问本人已归档计划 | 本人令牌 + 归档计划 | 400 `E1003`（状态不允许，非隐藏） |

### 3.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-05 | 令牌吊销 | 不实现，靠短有效期兜底 | 若需要"立即下线"，加一张 `token_denylist` 表并校验 |
| Q-06 | 锁定粒度 | 按账号 | 若演示环境被多机访问，改为账号 + IP 双维 |

'''
CH4 = '''## 4 M-02 课程内容管理设计说明

### 4.1 程序描述

M-02 维护"规划的依据"：课程、知识点、先修关系、资源。它不产生计划，但决定了计划的质量——知识点时长填错，排出来的任务时长就全错；先修关系有环，拓扑排序就会失败。

程序特点：

- **写操作为主**：CRUD 与批量导入；
- **强约束**：先修关系必须在"原图 + 本批"的完整图上做环检测，不能只查单条；
- **保护历史**：被版本引用的知识点只能停用，不能删除。

### 4.2 功能

![M-02 的 IPO 图](figures/fig-4-1-ipo-m02.png)

图 4-1 M-02 课程内容管理的 IPO 图

| 功能 | 说明 |
|---|---|
| 课程维护 | 名称、学期、总学时、启用状态 |
| 知识点维护 | 名称、章节、难度、参考时长、目标、常见错误、排序号 |
| 先修维护 | 支持单条与批量提交；成环时整批拒绝 |
| 资源维护 | 链接或摘要；与知识点多对多关联 |
| 引用影响分析 | 停用 / 删除前给出受影响版本数 |

**不归本程序管**：内容快照的生成（M-05）、草案生成（M-05）、权限（M-01）。

### 4.3 性能

表 4.1 M-02 的性能指标

| 操作 | 规模 | 目标耗时 | 说明 |
|---|---|---|---|
| 单条知识点保存 | 单条 | ≤ 50 ms | 含唯一性校验 |
| 批量先修提交 | 40 条 | ≤ 300 ms | 含整图环检测 |
| 引用影响查询 | 30 知识点 | ≤ 100 ms | 按 `version_task` 计数 |
| 资源关联更新 | 60 份 | ≤ 200 ms | 先删后插，单事务 |

### 4.4 输入项

表 4.2 M-02 的输入项

| 名称 | 类型 | 有效范围 | 来源 |
|---|---|---|---|
| `course` | object | 名称 1–100 字，总学时 > 0 | 管理端表单 |
| `concept` | object | 时长 5–600 分钟、难度 1–5、同课程名唯一 | 管理端表单 |
| `prereq_batch` | list | 每条为 `(from_concept_id, to_concept_id)`，最多 40 条 | 批量导入 |
| `resource` | object | 标题 1–200 字；url 或 summary 至少一项 | 管理端表单 |
| `status` | enum | `enabled` / `disabled` | 状态切换 |

### 4.5 输出项

表 4.3 M-02 的输出项

| 名称 | 类型 | 内容 | 说明 |
|---|---|---|---|
| `saved` | object | 保存后的实体 | 含服务端生成的 ID |
| `cycle_path` | list[int] | 环路节点序列 | 成环时返回，如 `[A, B, C, A]` |
| `blocked_rows` | list[int] | 被拒绝的行号 | 便于前端定位 |
| `impact` | object | 受影响版本数、受影响计划数 | 停用前提示 |

### 4.6 算法

#### 4.6.1 先修成环检测（DFS 三色标记）

对"原图 + 本批"构成的完整图做深度优先遍历，用三色标记识别回边：

- **白**：未访问；**灰**：在递归栈上；**黑**：已完成；
- 访问到灰色节点即有环，环路由递归栈中从该节点起的一段构成。

$$
\\text{cycle} = \\{v_k, v_{k+1}, \\dots, v_n, v_k\\} \\quad \\text{当 } \\exists (v_n, v_k) \\text{ 且 } v_k \\text{ 为灰}
$$

```python
def detect_cycle(edges, nodes) -> list[int] | None:
    adj = defaultdict(list)
    for u, v in edges:
        adj[u].append(v)
    color = {n: 0 for n in nodes}      # 0 白 / 1 灰 / 2 黑
    stack, path = [], []

    def dfs(u):
        color[u] = 1
        path.append(u)
        for v in adj[u]:
            if color.get(v, 0) == 1:            # 回边：找到环
                return path[path.index(v):] + [v]
            if color.get(v, 0) == 0:
                got = dfs(v)
                if got:
                    return got
        path.pop()
        color[u] = 2
        return None

    for n in sorted(nodes):
        if color[n] == 0:
            got = dfs(n)
            if got:
                return got
    return None
```

**为什么必须整图检测**：单条校验只能发现自环。A→B、B→C 各自合法，但加上 C→A 就成环——这正是批量提交的风险点。

#### 4.6.2 批量提交的原子性

整批要么全成功，要么全回滚。判定顺序固定：

1. 两端存在且同课程（否则 `E1001`）；
2. 剔除自环（`from == to`）与重复有序对；
3. 在"原图 ∪ 本批"上做环检测（否则 `E2001`）；
4. 单事务写入。

```python
def submit_prereqs(batch, course, repo) -> Result:
    for i, (u, v) in enumerate(batch):
        if u == v:
            return Reject("E1001", f"第 {i} 行自环")
        if not (repo.same_course(u, course) and repo.same_course(v, course)):
            return Reject("E1001", f"第 {i} 行跨课程")
    cleaned = sorted({(u, v) for u, v in batch})
    graph = repo.load_prereq_edges(course) | set(cleaned)
    cycle = detect_cycle(graph, repo.load_concept_ids(course))
    if cycle:
        return Reject("E2001", cycle=cycle)
    with repo.transaction():
        repo.insert_prereqs(cleaned)          # 任何异常整体回滚
    return Ok(len(cleaned))
```

#### 4.6.3 引用影响分析（停用 vs 删除）

$$
\\text{引用数} = \\#\\{\\,vt \\in version\\_task \\mid vt.concept\\_id = c\\,\\}
$$

- 引用数 = 0：允许删除；
- 引用数 > 0：只允许停用（`status = disabled`），历史版本仍可打开，新草案不再包含该知识点。

```python
def can_delete(concept_id, repo) -> tuple[bool, int]:
    refs = repo.count_version_task_refs(concept_id)
    return refs == 0, refs
```

#### 4.6.4 多对多关联写入

资源与知识点是 M:N。更新关联时采用"先删后插"，避免逐条比对：

```python
def replace_links(concept_id, resource_ids, repo):
    with repo.transaction():
        repo.delete_links_of_concept(concept_id)
        repo.insert_links([(concept_id, rid) for rid in set(resource_ids)])
```

### 4.7 流程逻辑

![M-02 先修批量提交流程](figures/fig-4-2-flow-m02.png)

图 4-2 M-02 先修批量提交流程

流程要点：

1. **越界检查在最前**：跨课程/自环属于"参数错"，不进环检测；
2. **去重在环检测之前**：重复边不构成环，先清理能减少无效遍历；
3. **环检测失败整批拒绝**，不做"部分成功"——半套先修关系比没有更危险；
4. 保存成功后使课程内容修订号 `content_revision` 递增，供草案判断"内容是否已变"。

### 4.8 接口

表 4.4 M-02 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 接口与序列化 | 函数调用 | 管理端路由 |
| 被调用 | M-11 存储访问 | 仓储 + 事务 | 见 D05 §4.1 |
| 被读取 | M-03 / M-05 | 只读快照 | 通过 `ContentSnapshot` 传递，不直接查库 |

```python
def save_concept(concept: ConceptInput, actor: Claims) -> Concept: ...
def submit_prereqs(batch: list[tuple[int, int]], course_id: int, actor: Claims) -> Result: ...
def disable_concept(concept_id: int, actor: Claims) -> Impact: ...
def replace_links(concept_id: int, resource_ids: list[int], actor: Claims) -> int: ...
```

### 4.9 存储分配

表 4.5 M-02 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 课程内容全量 | 30 知识点 + 40 边 + 60 资源 ≈ 60 KB | 环检测时整图读入内存 |
| 邻接表 | 40 条边 × 约 40 B | 每次提交重建，不复用 |
| 递归栈深度 | ≤ 30 | 图规模小，无栈溢出风险 |

### 4.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 环检测 | 说明三色含义 | `# 0 白=未访问 1 灰=在栈上 2 黑=已完成` |
| 批量提交 | 说明为何整批拒绝 | `# 半套先修关系比没有更危险，故整批回滚` |
| 删除保护 | 说明引用语义 | `# 被版本引用的知识点只能停用，否则历史版本打不开` |

### 4.11 限制条件

1. 单课程：所有知识点必须属于同一 `course_id`；
2. 批量提交上限 40 条，超过需分批（与验收规模一致）；
3. 环检测在应用层完成，数据库无法约束图性质；
4. 停用不影响历史版本，但会让新草案少一个知识点；
5. 不支持知识点合并、拆分等结构变更（需人工处理并重建内容）。

### 4.12 测试计划

表 4.6 M-02 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-02-01 | 正常新增知识点 | 合法字段 | 保存成功，返回 ID |
| T-02-02 | 同课程重名 | 重复名称 | 拒绝，`E1001` 定位到字段 |
| T-02-03 | 时长越界 | `reference_minutes=601` | 拒绝（CHECK + 应用双保险） |
| T-02-04 | 自环先修 | `(A, A)` | 拒绝，指出第几行 |
| T-02-05 | 跨课程先修 | B 属于另一门课 | 拒绝 `E1001` |
| T-02-06 | 重复边 | 提交两次 `(A, B)` | 去重后只存一条 |
| T-02-07 | 批量成环 | 已有 A→B、B→C，提交 C→A | 拒绝 `E2001`，返回环 `[A,B,C,A]` |
| T-02-08 | 部分合法部分非法 | 3 条中 1 条跨课程 | **整批拒绝**，库中无新增 |
| T-02-09 | 被引用知识点删除 | 该知识点已进入某个 version_task | 拒绝删除，提示改为停用 |
| T-02-10 | 停用后新草案 | 知识点停用 | 新草案不含该知识点，历史版本仍可打开 |
| T-02-11 | 资源关联替换 | 由 3 个关联改为 2 个 | 删旧插新，共 2 条 |
| T-02-12 | 内容修订号 | 任意写操作 | `content_revision` 递增 1 |

### 4.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-07 | 批量导入的冲突策略 | 整批拒绝 | 若导入数据量大，改为"预览差异 + 选择性应用" |
| Q-08 | 知识点停用后的资源孤立 | 不处理 | 看板提示"资源暂无关联知识点" |

'''
CH5 = '''## 5 M-03 约束与容量设计说明

### 5.1 程序描述

M-03 把学生填的"目标 + 截止 + 有空时间"变成**可计算的约束对象**与**容量数字**。它是 M-05 的输入准备程序：不排程，只回答"能排多少分钟"。

程序特点：

- **纯计算 + 一次写库**：计算部分无副作用，保存约束时写一次；
- **与 M-05 的分工**：本程序只展开时段、算 C/B/C′；M-05 才装箱；
- **必须给出理由**：容量为零时不能只说"失败"，要说明是哪条约束导致的。

### 5.2 功能

![M-03 的 IPO 图](figures/fig-5-1-ipo-m03.png)

图 5-1 M-03 约束与容量的 IPO 图

| 功能 | 说明 |
|---|---|
| 字段校验与规范化 | 目标去重、截止校验、周模板合法性、排除日期去重 |
| 时段展开 | 把周模板在 `[base_time, deadline)` 内展开为有序区间 |
| 容量计算 | 原始容量 C、缓冲 B、可排容量 C′ |
| 容量为零判定 | 全部被排除或时段为空时拒绝，并列出原因 |
| 已掌握剔除 | 目标与附加目标中剔除已掌握项 |

### 5.3 性能

表 5.1 M-03 的性能指标

| 操作 | 规模 | 目标耗时 |
|---|---|---|
| 字段校验 | 6 个字段 | ≤ 5 ms |
| 时段展开 | 180 天 × 每日 3 段 | ≤ 20 ms |
| 容量计算 | 540 个时段 | ≤ 5 ms |
| 整体（含保存） | 同上 | ≤ 300 ms |

### 5.4 输入项

表 5.2 M-03 的输入项

| 名称 | 类型 | 有效范围 | 说明 |
|---|---|---|---|
| `target_concept_id` | int | 本课程启用知识点 | 主目标 |
| `extra_concept_ids` | list[int] | 0–10 个，去重 | 附加目标 |
| `deadline` | date | 次日至 180 天内 | 截止日 |
| `availability` | 7 × list[(time, time)] | 每日 0–3 段，合计 ≤ 8 小时 | 周模板 |
| `excluded_dates` | list[date] | 0–30 个 | 排除日期 |
| `mastered_concept_ids` | list[int] | 本课程知识点 | 学生自评 |

### 5.5 输出项

表 5.3 M-03 的输出项

| 名称 | 类型 | 内容 | 说明 |
|---|---|---|---|
| `constraint` | object | 规范化后的约束 | 去重、排序后的字段 |
| `C` | int | 原始容量（分钟） | 展开后各段之和 |
| `B` | int | 缓冲（分钟） | `ceil(C × 0.10)` |
| `C_prime` | int | 可排容量 | `C − B` |
| `path_minutes` | int | 目标路径所需时长 | 闭包内知识点参考时长之和 |
| `reject_reason` | enum | `ALL_EXCLUDED` / `EMPTY_AVAILABILITY` | 容量为零时给出 |

### 5.6 算法

#### 5.6.1 时段展开（与 M-05 的 A1 的关系）

M-05 的 §7.6.1 已给出展开算法。本程序复用同一函数，但**只做展开与求和、不做装箱**，差异有两点：

1. 本程序按"整段"统计容量，不消费时段；
2. 本程序额外返回 `path_minutes`，用于界面"提交前估算"。

```python
def expand(constraint, config, base_time) -> list[Interval]:
    # 与 M-05 §7.6.1 完全相同的实现，由 M-05 与本程序共用同一工具函数
    ...
```

#### 5.6.2 容量计算

$$
C = \\sum_{k=1}^{m} \\left\\lfloor \\frac{|seg_k|}{60} \\right\\rfloor \\quad (\\text{分钟})
$$

$$
B = \\left\\lceil \\text{BUFFER\\_RATIO} \\times C \\right\\rceil,\\qquad C' = C - B
$$

```python
def compute_capacity(intervals, config) -> tuple[int, int, int]:
    C = sum(int((i.end - i.start).total_seconds() // 60) for i in intervals)
    B = math.ceil(config.BUFFER_RATIO * C)
    return C, B, C - B
```

#### 5.6.3 容量为零的判定与原因

三种情况都判为"不可排"，但原因不同：

| 条件 | 原因码 | 提示文案要点 |
|---|---|---|
| 周模板全空 | `EMPTY_AVAILABILITY` | "没有填写可用时间" |
| 区间内所有日期都被排除 | `ALL_EXCLUDED` | "排除日期覆盖了整个规划区间" |
| 区间内所有时段都早于基准时刻 | `ALL_EXCLUDED` | "可用的时间都已经过去" |

```python
def ensure_positive(C, intervals, constraint) -> None:
    if C > 0:
        return
    reason = "EMPTY_AVAILABILITY" if not constraint.availability_any() else "ALL_EXCLUDED"
    raise Reject("E1003", reason=reason)
```

#### 5.6.4 目标去重与已掌握剔除

$$
G' = (G \\setminus \\text{mastered}) \\quad \\text{且去重后} \\ |G'| \\ge 1
$$

若主目标已被自评为"已掌握"，允许继续，但附加目标必须至少有一个未掌握项；若全部已掌握，返回 `NOTHING_TO_PLAN`（与 M-05 的空草案一致）。

### 5.7 流程逻辑

![M-03 约束提交流程](figures/fig-5-2-flow-m03.png)

图 5-2 M-03 约束提交流程

流程要点：

1. **字段合法性与截止窗口最先判**，避免为非法输入做无用的时段展开；
2. **容量为零是阻断分支**，此时不保存约束，直接回显原因；
3. 保存成功后返回容量摘要，界面据此显示"排得下/紧张/排不下"；
4. 本程序不判断"排得下"——那是 M-05 与 M-06 的事，本程序只给数字。

### 5.8 接口

表 5.4 M-03 的调用关系

| 方向 | 对象 | 方式 | 说明 |
|---|---|---|---|
| 上层调用方 | M-10 接口与序列化 | 函数调用 | 约束提交接口 |
| 被调用 | M-02 课程内容管理 | 只读快照 | 取知识点与参考时长 |
| 被调用 | M-11 存储访问 | 仓储 | 保存约束 |
| 下游 | M-05 分解与排程 | 返回值 | 提供时段与 C/B/C′ |

```python
def normalize(constraint_input, content, now) -> Constraint: ...
def compute(constraint, content, config, base_time) -> CapacitySummary: ...
def save(constraint, actor) -> Constraint: ...
```

### 5.9 存储分配

表 5.5 M-03 的存储占用

| 对象 | 规模 | 说明 |
|---|---|---|
| 时段列表 | ≤ 540 段 × 约 80 B ≈ 43 KB | 随请求释放 |
| 约束对象 | 约 2 KB（含三个 JSON 字段） | 落库为 `plan_constraint` 一行 |
| 目标集合 | ≤ 11 个 ID | — |

### 5.10 注释设计

| 位置 | 要求 | 示例 |
|---|---|---|
| 容量公式 | 指明与本文公式号对应 | `# 见 §5.6.2 式 (5-1)：C = Σ 段长` |
| 缓冲 | 说明为何向上取整 | `# 向上取整：宁可少排一分钟，也不要超出真实可用时间` |
| 零容量 | 说明三种原因的区分 | `# 三种零容量原因不同，提示文案必须分开` |

### 5.11 限制条件

1. 只支持单课程约束，不支持跨课程合并；
2. 每日可用时段合计 ≤ 8 小时（超出视为误填）；
3. 排除日期最多 30 个；
4. 截止窗口 2–180 天，不接受当天截止；
5. 时区固定为 Asia/Shanghai，界面显示与存储分离（存储 UTC 秒）。

### 5.12 测试计划

表 5.6 M-03 单体测试用例

| 用例号 | 覆盖点 | 输入 | 预期结果 |
|---|---|---|---|
| T-03-01 | 正常容量 | 30 天、每周 3 天 × 120 分钟 | C、B、C′ 与手算一致 |
| T-03-02 | 截止边界-昨天 | 截止 = 昨天 | 拒绝 `E1001` |
| T-03-03 | 截止边界-180 天 | 截止 = 今天 + 180 | 接受 |
| T-03-04 | 截止边界-181 天 | 截止 = 今天 + 181 | 拒绝 |
| T-03-05 | 每日超 8 小时 | 某日 4 段 × 150 分钟 | 拒绝 `E1001` |
| T-03-06 | 排除日期含截止日 | 排除集合包含截止日 | 该日时段被扣除，仍可排 |
| T-03-07 | 全部排除 | 所有日期被排除 | `E1003` + `ALL_EXCLUDED` |
| T-03-08 | 周模板全空 | 七天都没有时段 | `E1003` + `EMPTY_AVAILABILITY` |
| T-03-09 | 目标去重 | 附加目标含重复项与主目标 | 去重后数量正确 |
| T-03-10 | 全部已掌握 | 目标与附加目标都在已掌握集合 | 返回 `NOTHING_TO_PLAN` |
| T-03-11 | 缓冲取整 | C = 1321 分钟 | B = 133（向上取整） |
| T-03-12 | 时段裁剪 | 基准时刻在某个时段中间 | 该段只计剩余分钟 |

### 5.13 尚未解决的问题

| 编号 | 问题 | 当前处理 | 计划 |
|---|---|---|---|
| Q-09 | 跨时区学生 | 固定上海时区 | 若有多时区，需把 `availability` 改为带时区的区间 |
| Q-10 | 排除日期的粒度 | 整天排除 | 若需"半天",改用区间排除 |

'''

t = DOC.read_text(encoding="utf-8")
anchor = "## 7 M-05 分解与排程设计说明"
assert anchor in t
t = t.replace(anchor, CH3 + CH4 + CH5 + anchor, 1)
DOC.write_text(t, encoding="utf-8", newline="\n")
print("已插入第 3、4、5 章，总行数:", t.count("\\n") + 1)

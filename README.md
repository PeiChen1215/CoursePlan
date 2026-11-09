# 学径 StudyPath —— 课程学习规划辅助系统

> 《软件工程综合实训》课程项目
> 实训周期：2026.10.26 — 2026.11.20（第 9–12 周，共 4 周 / 120 学时）
>
> 「学径」取“学习路径”之意：把一门课的零散知识点，规划成学生真正走得完的一条路。

---

## 一、项目简介

面向高校单门课程的学习规划辅助系统。课程管理员维护课程的知识点、学习资源、先修关系与参考学习时长；学生填写学习目标、截止日期、每周可用时间与已掌握内容，系统借助大模型智能体追问缺失信息、检索课程资源、把目标分解为可执行的学习任务，并由**程序**校验时间容量、任务重叠与先修条件，生成可确认的学习计划。执行过程中学生记录进度，出现延后或目标变化时，智能体给出调整建议，经学生确认后更新计划，并保留计划版本与调整原因。

**范围约定**：系统面向**一门课程**（示例课程由课程管理员创建），不追求多课程平台化。

---

## 二、目标用户与角色

| 角色 | 主要职责 |
|---|---|
| 学生 | 设定学习目标与时间约束、确认学习计划、记录任务进度、接受智能体辅导与调整建议 |
| 课程管理员 | 维护课程基本信息、知识点、先修关系、学习资源与参考学习时长 |

---

## 三、技术栈

| 层级 | 选型 | 状态 |
|---|---|---|
| 后端 | Python 3.12 + FastAPI + SQLite（WAL） | 已实现 |
| 前端 | React 18 + TypeScript + Vite 5 + Tailwind CSS | 已实现 |
| 大模型 | 统一 Provider 接口：`mock` / `real` / `auto`，真实实现走 OpenAI 兼容 `chat/completions` | 已实现 |
| 智能体 | 意图抽取 + 目标映射（精确 → 别名 → 模型 → 候选） | 已实现 |

> 模型调用遵循「规则优先、模型兜底」：日期、时长这类有明确写法的字段不调模型；
> 只有目标映射无法用规则命中时才调用，超时或失败自动降级为规则结果，已填字段不清空。

---

## 四、目录结构

```
CoursePlan/
├─ docs/              课程文档（14 类交付物 + 过程记录，见 docs/README.md）
├─ backend/           FastAPI 后端（app/ 25 个模块，tests/ 20 个测试文件）
├─ frontend/          React 前端（8 个页面 + 组件与 hooks）
├─ data/              演示库（dev_ui.db，不入库）
├─ scripts/           导出、校验、备份等脚本
├─ logs/              运行日志（不入库）
└─ backups/           数据备份（不入库）
```

---

## 五、本地运行

```powershell
# 终端 1：后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000 --reload

# 终端 2：前端
cd frontend
pnpm install
pnpm dev          # http://127.0.0.1:5173，/api 代理到 8000
```

### 演示数据

```powershell
cd backend
python scripts/seed.py --db ..\data\dev_ui.db
```

会重建演示库：12 个知识点、12 条先修关系、6 条资料、4 个账号、1 份已确认计划（22 个任务 / 29 片）。

演示账号：`alice / Passw0rd!`（学生）、`admin / Admin123!`（管理员）。

### 大模型配置

默认 `PROVIDER_MODE=mock`，**不联网、结果可复现**，适合演示与自动化测试。

接真实模型时用环境变量开启，密钥不要写进仓库：

```powershell
$env:DSH_PROVIDER_MODE  = "real"          # mock / real / auto
$env:DSH_PROVIDER_KEY   = "<你的 API Key>"
$env:DSH_PROVIDER_MODEL = "deepseek-flash"
$env:DSH_PROVIDER_BASE  = "https://api.deepseek.com"
```

`auto` 模式启动时用 `GET /models` 探测一次，失败即回落 `mock`。
密钥只从环境变量读取，`config` 里的默认值为空字符串。

---

## 六、文档索引

全部交付文档见 [`docs/README.md`](docs/README.md)。

# DataGuard AI

基于 LangGraph 的企业级数据治理 Agent 平台（Enterprise Data Governance Agent Platform）。

> 定位：**不是 AI 数据清洗工具**，而是一个由 Agent 负责理解与决策、由 Workflow 负责流程控制、
> 由 Tools 负责确定性执行、由 Validator 负责结果验证、由 Risk Engine 负责安全控制、
> 由 Trace 负责全过程可观测的企业级数据治理 Agent 系统。

## 当前进度

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 0 | 项目初始化（backend/frontend 脚手架、双 SQLite、配置、日志） | ✅ 完成 |
| Phase 1 | 单数据源 Agent 闭环（CSV + Minimal LangGraph Workflow） | ✅ 完成 |
| Phase 2 | LangGraph 完整 Workflow（Supervisor/Routing/Plan Validator/Risk/Re-plan） | ✅ 完成 |
| Phase 3 | Agent Trace 系统 + Workflow Studio | ✅ 完成 |
| Phase 4 | Human-in-the-loop（Approval Center） | ✅ 完成 |
| Phase 5 | 企业数据库接入（MySQL/PostgreSQL） | ✅ 完成 |
| Phase 6 | Web Data Source + 最终交付 | ✅ 完成 |

## Phase 6 已实现

- **WebSourceService**：`URL → Crawler（httpx）→ Parser → Structured Extractor（HTML 表格 / JSON）→ Dataset → Governance Flow`
- **Web API**：`POST /api/web/register`（单 URL）、`POST /api/web/register_batch`（批量 URL）
- **前端 DataSource 页 Web 入口**：单 URL 注册 + 批量 URL（每行一个）→ 注册结果 → 跳转治理
- 测试：MockTransport 本地 HTML/JSON fixture（不依赖真实网络）

## 最终交付物

一次治理流程完成后，系统产出两个交付物（存储于 ObjectStorage `outputs/{dataset_id}/`）：

| 交付物 | 内容 | 访问 |
|---|---|---|
| `cleaned.csv` | 清洗后的新数据（最终产物） | 治理工作台「治理成果」区一键下载 |
| `validation_report.json` | 治理报告（issues / plan / execution / 前后质量分） | 治理工作台「治理成果」区查看摘要 |

> 逻辑：Agent 负责"理解与决策"，确定性问题（统计/工具执行/验证）由 Python 完成，最终交付的是**清洗后的新数据 + 可审计的治理报告**，高风险操作需人工逐条审批后才真正写入。

**安全规则（硬性，Execution Engine 层强制执行，不依赖 LLM）**：数值列（int/float dtype，如 age/金额）一律禁止 `delete_duplicate`——数值列的重复值通常是正常分布，删除会误删正常数据；拦截结果记为 failed 并保留 error 说明。

## 问题列表（Issue Explorer）

「问题列表」页展示**跨运行**的所有数据质量问题：总数 / 数据集数 / 高 / 中 / 低统计卡片，可按严重度与类型筛选。**两级分级**：第一层级＝数据集名称（上传时可自定义，如「客户全量测试数据」，文件名作为副标题小字）→ 点击展开该数据集下的问题明细表（数据来自 `GET /api/issues`，筛选参数 `severity` / `issue_type`，按运行时间倒序）。

## 最终 Demo 流程（面试 8 步）

1. 上传 `customer.csv`（或注册 MySQL `customer` 表 / Web URL）
2. 点击 **Start Governance** → Supervisor 规划流程（展示路由决策）
3. Workflow Graph 实时展示执行状态（节点着色 + 当前节点高亮）
4. 点击 **Inspector** 节点 → 查看 Agent Input / Decision / Tool Calls / Output / Latency / Token / Detected Issues（真实 Trace）
5. 点击 **Planner** 节点 → 查看 Cleaning Plan（normalize_phone 等，含 risk）
6. **Risk Engine**：LOW 自动执行；MEDIUM/HIGH 进入审批
7. **Approval Center（逐条审批）**：每条高风险操作独立展示（操作编号/影响行数/变更预览），逐条选择「批准（执行）」或「拒绝（跳过）」，全部处理后点「提交审批结果」→ 工作流仅执行批准的操作，拒绝的自动跳过
8. **Validator**：Quality Score Before 93.93 → After 94.73（PASS）；完整 Agent 执行链路在 Trace 中可回放
9. **追踪详情**：事件流实时累积（每事件含耗时/Token）+ **Token 消耗统计卡片**（按 Agent 汇总 supervisor/profiler/inspector/planner + 合计，来自真实 usage）

## 测试数据

| 文件 | 说明 |
|---|---|
| `datasets/demo/customer.csv` | 504 行标准演示数据（含缺失/重复/格式/异常值） |
| `datasets/demo/all_issues.csv` | **28 行全问题覆盖测试数据**（缺失值、完全重复行、手机号/邮箱/日期格式异常、年龄异常值 150、金额负数/零、前后空格、空串、大小写不一致等），用于快速验证全流程能力 |

> 用 `all_issues.csv` 实测时：Inspector 可检出 8 类问题（duplicate/missing_value/format_error/outlier），Planner 在安全约束下只做 normalize/fill_missing（不对数值列执行危险 delete_duplicate）。

## 测试（56 passed）

| 套件 | 覆盖 |
|---|---|
| test_tools | normalize_phone/email/date/trim |
| test_profiler | profile 结构 / 异常检测 / 质量分 / Validator |
| test_agents | 4 Agent 结构化输出 schema |
| test_risk_engine | 风险策略表 / LOW 自动 / HIGH 审批 |
| test_plan_validator | 防幻觉三重校验 |
| test_replan | Supervisor 路由 / Re-plan 上限 / 条件路由 |
| test_approval | 审批暂停 / 恢复 / 拒绝 / API |
| test_database | SQL 防火墙 / MySQL 集成治理 |
| test_web | HTML/JSON 提取 / 批量 / 治理流程 |
| test_workflow / test_api | 全流程 / 持久化 / validation_report / Trace / API |

## Phase 1 已实现

- **CSV 上传**：`POST /api/dataset/upload` → ObjectStorage（Local）→ datasets 表
- **Minimal LangGraph Workflow**：`START → profiler → inspector → planner → execution → validator → END`
- **Python Data Profiler**：schema/统计/模式/异常候选（确定性，无 LLM）
- **Evidence Builder**：压缩 LLM Context（样本上限 `DG_MAX_SAMPLE_ROWS`，禁止全量数据入 LLM）
- **4 个核心 Agent**（Supervisor 在 Phase 2 接入图）：
  - Profiler Agent：统计结果的语义解释
  - Inspector Agent：输出 IssueReport（ID/type/severity/confidence/affected_rows/evidence）
  - Planner Agent：输出 CleaningPlan（仅使用已注册工具）
- **Tool Registry + 工具**：`profile_dataset / detect_missing / detect_duplicate / detect_pattern / detect_outlier` + LOW 清洗工具 `normalize_phone / normalize_email / normalize_date / trim_whitespace`
- **Execution Engine**：DRY_RUN / EXECUTE 双模式，产出 `cleaned.csv`（ObjectStorage `outputs/{dataset_id}/cleaned.csv`）
- **Quality Validator**：completeness / uniqueness / format_validity → 0-100 分，before/after 对比
- **TraceCollector 基础设施**：SQLite 持久化 trace_events（WORKFLOW_START / AGENT_START / AGENT_DECISION / TOOL_CALL / TOOL_RESULT / VALIDATION / ERROR / WORKFLOW_END）
- **后台执行模型**：`POST /workflow/start` 立即返回 run_id，工作流在后台线程执行，前端 1s 轮询
- **前端 Workflow Studio 基础版**：上传 → Start Governance → 轮询 → Issues / Plan / Validation 展示

## Phase 2 已实现

- **Supervisor Agent 接入图**：任务理解 + 流程规划 + 节点路由（`route_after_supervisor` 条件边）
- **Conditional Routing**：
  - `supervisor → profiler`（file/database 共享入口，Phase 5 拆数据库流）
  - `plan_validator → risk | planner | END`（PASS / FAIL 重规划 / 超限）
  - `validator → END | reflection`（PASS / FAIL 反思）
- **Plan Validator**（防幻觉，确定性代码）：工具已注册 + 参数合法 + issue_id 存在且列匹配
- **Risk Engine**（确定性规则表，LLM 不判风险）：LOW 自动 / MEDIUM 可配置（`DG_MEDIUM_RISK_MODE`）/ HIGH 必须审批；`delete_row` 不实现
- **Execution Mode per-action**：auto → EXECUTE；approval → DRY_RUN（预览，Phase 4 接审批中断）
- **Reflection + Re-plan**：Validator FAIL → Reflection（失败分析）→ Planner 重新规划；`MAX_ITERATION=3`（`DG_MAX_ITERATION`），超限进入人工处理（Phase 4）
- **前端 WorkflowGraph**（Vue Flow）：8 节点图 + 状态着色（running/success/failed/waiting）+ 条件边（PASS/FAIL/re-plan 虚线）+ 当前节点实时高亮

完整图：

```
START → supervisor -(route)→ profiler → inspector → planner → plan_validator
      -(PASS)→ risk → execution → validator -(PASS)→ END
      -(FAIL, iteration<MAX)→ reflection → planner (re-plan)
      -(FAIL, iteration>=MAX)→ END (human review, Phase 4)
```

## Phase 3 已实现

- **Trace API**：
  - `GET /api/trace/{run_id}`：全部 Trace 事件（支持 `?node=xxx` 过滤）
  - `GET /api/trace/{run_id}/usage`：按 Agent 聚合 token（AGENT_DECISION 事件）
- **Workflow Studio 三栏布局**：左 Dataset ｜ 中 WorkflowGraph ｜ 右 Trace Detail
- **TracePanel**：结构化事件时间线（时间 / node / event_type / latency / tokens / error status）
- **AgentDetail**：点击 Graph 节点 → 该节点真实 Trace 事件（Agent Input / Decision / Tool Calls / Output / Latency / Token）
- **Token Usage**：按 Agent 分布展示（supervisor/profiler/inspector/planner）
- 所有 Trace 来自真实运行，无静态假数据

## 界面与交互（中文版）

治理工作台三栏布局：左＝数据集（上传/信息/质量分/历史）、中＝工作流图谱 + 治理结果摘要（问题数/清洗动作/质量分/下载/「查看完整报告」按钮）、右＝追踪详情（可展开的实时 Trace + Agent 详情）。

**治理报告弹窗**：点击「查看完整报告」打开**居中 2/3 画布**（el-dialog 72% 宽、垂直居中，两侧仍可见原界面），全宽展示 4 大区块——发现的问题（编号/类型双语/列/严重度/置信度/影响行数/证据样例）、清洗计划（工具/列/风险/对应问题）、清洗动作明细（含 before→after 样例对比）、质量维度对比（完整性/唯一性/格式合规双进度条）。顶部含 cleaned.csv 下载入口与概要统计。关闭三入口：标题栏「收起报告」按钮 / 右上角 X / ESC / 点击遮罩；打开状态保存在 Pinia store，切换页面再返回保持打开且内容不丢（数据源为 `GET /api/dataset/{id}/outputs`）。

**数据源注册 → 治理跳转**：从「数据源」页注册网页/数据库数据集后点「前往治理工作台」，会自动**选中新数据集并清空上一次运行状态**（避免持久化恢复的旧检测信息误导）；数据库注册同样处理。
- **全中文界面**：菜单 / 视图 / 按钮 / 表格 / 提示全部中文化（技术值如 API 字段保持英文，仅展示层翻译）
- **数据持久化**：数据集与运行任务持久化到 SQLite + 浏览器 localStorage；运行时状态保存在 Pinia store（切换页面不丢失），刷新后按 run_id 自动恢复并**持续轮询直到任务终态**；审批暂停时 issues/plan/trace 同步持久化，恢复页面即可看到完整进度
- **待审批表达**：`WAITING_APPROVAL` 时不再显示停滞的进度条，改为醒目「等待人工审批」横幅 + 跳转审批按钮
- **使用步骤引导**：治理工作台顶部 8 步流程条（上传 → 启动 → 画像 → 质检 → 规划 → 审批 → 执行 → 验证），仪表盘含 4 步快速开始
- **进度可视化**：`GET /api/workflow/{run_id}` 返回 `node_states`（每个节点 waiting/running/success/failed），工作流图谱实时着色 + 当前节点提示 + 待审批横幅

## Phase 4 已实现

- **MEDIUM/HIGH 工具**：`fill_missing`（MEDIUM，众数/指定值填充）、`delete_duplicate`（HIGH，按标识列去重）；`delete_row` 不实现
- **Risk Engine 策略**：LOW 自动执行 / MEDIUM 可配置（默认审批）/ HIGH 必须审批；`approval_status` 进入 PENDING
- **LangGraph interrupt + Checkpointer**：`approval_node` 用 `interrupt()` 暂停工作流（携带 DRY_RUN 预览：预计影响行数 + Before/After samples），`checkpoints.db` 持久化线程状态；`Command(resume=...)` 恢复
- **Approval 流程**：`WAITING_APPROVAL` → Approval Center 审批 → APPROVED 恢复执行 / REJECTED 终止（FAILED）
- **Approval API**：`GET /api/approval/pending`、`POST /api/approval/approve`、`POST /api/approval/reject`（approvals 表持久化）
- **前端 Approval Center**：待审批卡片（Operation / Affected Rows / Risk / Before→After Preview / Reject / Approve），2s 轮询
- 审批 Trace：`HUMAN_APPROVAL` 事件进入 trace_events

Demo 验证：上传 customer.csv → 工作流停在 approval（delete_duplicate 4 行 + fill_missing 12 行）→ 批准后恢复执行 → SUCCESS。

## Phase 5 已实现

- **DatabaseConnector 统一接口**：MySQL（pymysql）/ PostgreSQL（psycopg）——`test_connection / list_tables / get_schema / sample_rows / preview_sql`
- **SQL 防火墙（默认 READ ONLY）**：拒绝 DROP/TRUNCATE/DELETE/ALTER/INSERT/UPDATE 等写语句与不安全标识符；Agent 无法执行写 SQL
- **数据库数据集注册**：`POST /api/database/register` 将表注册为虚拟数据集（source_type=database）
- **数据库治理流程**：Supervisor 路由 database → Profiler 从 MySQL 拉数据分析 → Inspector → Planner → Risk → 审批 → Execution（**数据库源强制 DRY_RUN，绝不写回生产表**）→ Validator
- **Database Source API**：`/api/database/test`、`/tables`、`/schema`、`/preview`、`/register`
- **前端 DataSource 页 Database 入口**：连接表单 → Test Connection → List Tables → Preview → 注册 → 跳转治理
- **Demo**：`docker compose`/`docker run dg-mysql` + `scripts/init_mysql_demo.py` 建 504 行 `dataguard_test.customer`；端到端验证：注册 → 治理 → 审批 → SUCCESS

> 生产写流程（Shadow Table / Transaction）为设计规范，Phase 5 保持 READ ONLY + Preview；实际写回在真实企业环境按 Plan → Risk → Approval → Transaction 启用。

## 本地运行（含无 Key 开发模式）

后端默认读取 `backend/.env`；**未配置 LLM API Key 时使用 FakeLLM**（确定性离线，仅开发/测试）。
配置真实模型：编辑 `.env` 设 `DG_LLM_PROVIDER=deepseek`（或 openai/qwen/openai_compatible）+ `DG_LLM_API_KEY`。

## API 概览（当前）

| Method | Path | 说明 |
|---|---|---|
| POST | /api/dataset/upload | 上传数据集（CSV/Excel/JSON） |
| GET | /api/dataset/{id} | 数据集详情 |
| POST | /api/workflow/start | 启动治理流程（body: dataset_id, goal） |
| GET | /api/workflow/{run_id} | 状态轮询（status/current_node/progress/nodes） |
| GET | /api/issues/{run_id} | Agent 发现的问题 |
| GET | /api/plan/{run_id} | Cleaning Plan |
| GET | /api/validation/{run_id} | 前后质量分 |
| GET | /health | 健康检查 |

## 技术栈

- **Backend**: Python 3.11 · FastAPI · LangGraph · LangChain · Pydantic v2 · Pandas · Polars · SQLAlchemy · SQLite/PostgreSQL · Loguru · pytest
- **LLM**: 云端 OpenAI-Compatible API（OpenAI / DeepSeek / Qwen），FakeLLM 仅用于测试/CI
- **Frontend**: Vue3 · Vite · Element Plus · Pinia · ECharts · Vue Flow

## 本地运行

### Backend

```bash
cd backend
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # 填入 DG_LLM_API_KEY（DeepSeek/OpenAI/Qwen 任一）
uvicorn app.main:app --reload --port 8000
```

- 健康检查：`GET http://localhost:8000/health`
- API 文档：`http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install          # 已配置 npmmirror 镜像
npm run dev          # http://localhost:5173
```

### 测试

```bash
cd backend
.venv\Scripts\python.exe -m pytest tests/ -v
```

## 目录结构

```
dataguard-ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # Pydantic Settings（全部外部依赖可配置）
│   │   ├── models.py            # 9 张业务表 ORM
│   │   ├── api/                 # dataset/workflow/trace/approval/database
│   │   ├── agents/              # 4 核心 Agent（Phase 1+）
│   │   ├── graph/               # LangGraph state/nodes/builder（Phase 1+）
│   │   ├── tools/               # BaseTool + ToolRegistry（Phase 1+）
│   │   ├── governance/          # Risk Engine / Validator / Approval（Phase 1+）
│   │   ├── trace/               # TraceCollector（Phase 1+）
│   │   ├── llm/                 # LLM Client Layer（Phase 1+）
│   │   ├── schemas/             # Pydantic 数据结构
│   │   └── storage/             # 业务 DB（app.db）+ ObjectStorage 抽象
│   ├── prompts/                 # Agent Prompt 独立文件（Phase 1+）
│   ├── storage/                 # app.db / checkpoints.db / datasets / outputs
│   ├── datasets/demo/           # demo 数据（Phase 1）
│   ├── scripts/check_db.py      # 开发验收工具
│   └── tests/
├── frontend/src/
│   ├── views/                   # Dashboard/Workflow/Issues/Approval/DataSource
│   └── components/              # WorkflowGraph/TracePanel/AgentDetail/IssueCard/DiffViewer/QualityChart
├── docs/architecture.md         # Production Architecture Specification
└── docker-compose.yml           # 可选：模拟生产依赖（PostgreSQL/Redis/MinIO）
```

## 架构

- 分层架构、LLM 策略、数据库、Object Storage、执行模型、安全规则详见 [docs/architecture.md](docs/architecture.md)。
- 本地开发环境是 Production Architecture 的轻量化版本（SQLite + LocalObjectStorage + 云端 LLM API），
  同一套应用代码可通过 `DG_DATABASE_URL` / `DG_OBJECT_STORAGE_BACKEND=s3` 切换到生产依赖。

## Agent 设计（4 个核心 Agent）

| Agent | 职责 | 禁止 |
|---|---|---|
| Supervisor | 任务理解、流程规划、节点路由 | 修改数据、执行工具 |
| Profiler | 解读统计结果，输出语义画像 | 自行计算统计、修改数据 |
| Quality Inspector | 基于证据发现问题，输出 IssueReport | 凭空捏造、修改数据 |
| Cleaning Planner | 生成 CleaningPlan | 直接执行、使用未注册工具、自定风险 |

## License

Internal project for portfolio / demo purpose.

# DataGuard AI — Architecture Specification

> 定位：基于 LangGraph 的企业级 Data Governance Agent Platform。
> 不是本地玩具 Demo：本地开发环境是 Production Architecture 的轻量化版本，
> 而不是另一套 Demo Architecture。所有 Phase 必须遵守本规范。

---

## 1. 核心原则

| 原则 | 含义 |
|---|---|
| Agent 负责决策，不负责计算 | 统计/验证/风险判断全部是确定性 Python；LLM 只做理解/判断/规划 |
| Agent 不直接修改数据 | 一切修改必须走 Plan → Validator → Risk Engine → Approval → Execution Engine |
| 所有行为可追踪 | Trace 记录输入/输出/工具调用/延迟/token/状态/错误，来自真实运行，禁止假数据 |
| 强类型 | 核心数据结构用 Pydantic / TypedDict / Enum，禁止核心逻辑裸 dict |
| Tool 必须经 Registry | Agent 禁止 import 具体 Tool，一律 registry.get(name) |
| 默认 READ ONLY | 企业数据源只读；写操作必须审批 + Transaction/Shadow Table |
| Production-Ready | 可部署云端、可接企业数据、可用真实 LLM API、可长期运行 |

---

## 2. 分层架构

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (Vue3 + Vite + Element Plus + Pinia + ECharts)        │
│ Dashboard │ Workflow Studio │ Issues │ Approval │ DataSource   │
└──────────────┬───────────────────────────────────────────────┘
               │ REST (JSON) + 1s polling（第一版不做 SSE）
┌──────────────▼───────────────────────────────────────────────┐
│ FastAPI Service Layer（只编排与持久化，不直接调用 Agent）        │
└──────────────┬───────────────────────────────────────────────┘
┌──────────────▼───────────────────────────────────────────────┐
│ Agent Worker（后台执行，不阻塞请求线程）                        │
│  LangGraph：State → Nodes → Conditional Edges → Checkpointer  │
│    │                                                          │
│    ├─ 4 核心 Agent（仅决策）                                    │
│    │   Supervisor / Profiler / Inspector / Planner            │
│    └─ 确定性 Node（纯 Python）                                  │
│        Evidence Builder / Plan Validator / Risk Engine /      │
│        Execution Engine / Validator / Reflection              │
│         │                                                     │
│         ▼                                                     │
│  Tool Registry → Tool Validator → BaseTool                     │
└───────┬───────────────┬───────────────┬──────────────────────┘
        │               │               │
┌───────▼────────┐ ┌────▼─────┐ ┌───────▼────────┐
│ LLM Client     │ │Object    │ │Business DB     │
│ Interface      │ │Storage   │ │(SQLite 本地 /   │
│ → Provider     │ │Interface │ │ PG/MySQL 生产)  │
│ → Cloud API    │ │Local/S3  │ └────────────────┘
└────────────────┘ └──────────┘
        ┌───────────────────────────────┐
        │ Checkpoint DB（与业务库隔离）    │
        │ Redis（预留：cache/锁/队列）     │
        └───────────────────────────────┘
```

## 3. LLM 策略（Cloud API 优先）

- 默认 LLM 通过云端 OpenAI-Compatible API 调用：OpenAI / DeepSeek / Qwen / 其他。
- 链路：`Agent → LLM Client Interface → Provider → Cloud LLM API`；Agent 禁止直接依赖具体 SDK。
- Provider 可配置：`DG_LLM_PROVIDER=deepseek|openai|qwen|openai_compatible`，配合 `DG_LLM_BASE_URL / DG_LLM_MODEL / DG_LLM_API_KEY`。
- API Key 只经环境变量/Secret 管理，禁止硬编码。
- 模型输出必须过 Pydantic 结构化校验（with_structured_output 或 parse），不轻信模型 JSON。
- **FakeLLM 仅用于 Unit Test / CI / 无 Key 开发测试 / Workflow 测试；不是生产运行模式，禁止在最终 Demo 中伪装真实 Agent 推理。**
- 禁止引入需要本地下载大模型才能运行的方案。

## 4. 数据库

- 业务库（datasets / workflow_runs / issues / cleaning_plans / executions / validations / approvals / trace_events）：
  - 本地开发/测试/简单 Demo：SQLite（默认 `storage/app.db`）
  - 生产：PostgreSQL（优先）或 MySQL，通过 `DG_DATABASE_URL` 切换，应用代码不变
- LangGraph Checkpoint Storage 与业务库职责分离（`storage/checkpoints.db`），不与业务表耦合。

## 5. Object Storage

- 禁止生产数据集依赖容器本地文件系统。
- 抽象 `ObjectStorage Interface`：`LocalStorage`（本地开发）/ `S3-compatible`（AWS S3、阿里云 OSS、腾讯云 COS、MinIO，生产）。
- Dataset Service 只依赖接口，不直接使用本地文件路径。

## 6. Agent Execution 模型

- 生产环境 FastAPI 请求线程不阻塞等待 Workflow：
  `POST /workflow/start` → 创建 workflow_run → 返回 run_id → **后台执行 Agent Workflow**。
- 前端通过 `GET /workflow/{run_id}` 轮询（第一版 1s polling，不实现 SSE）。
- 后续可扩展：Redis Queue / Celery / RQ / 独立 Worker（预留 `DG_REDIS_URL`，当前不引入）。

## 7. 配置管理

所有外部依赖配置化，经 Environment Variables + Pydantic Settings 管理，禁止硬编码：
LLM（provider/base_url/key/model/timeout/retries）、Database URL、Redis、Object Storage、
Risk Policy（`DG_LOW_RISK_AUTO_EXECUTE`、`DG_MEDIUM_RISK_MODE`）、并发、超时、重试。

## 8. 安全规则

- 企业数据库默认 READ ONLY；Agent 禁止直接执行 SQL。
- 写操作链路：`结构化 Plan → SQL/Operation Validator → Risk Engine → Approval → Execution Engine`。
- 生产数据修改优先 Shadow Table（`customers → customers_agent_runXXX → 验证 → Promote`）或 Transaction；禁止默认直接修改生产表。
- SQL 防火墙：禁 DROP / TRUNCATE / DELETE / ALTER（默认）。

## 9. 生产部署拓扑

```
Internet
  ↓
Load Balancer / Reverse Proxy
  ↓
Frontend (静态资源/CDN)
  ↓
FastAPI API
  ↓
Agent Worker (后台执行 LangGraph)
  ↓
LLM Provider (Cloud API)
```
并连接：PostgreSQL / Redis / Object Storage / Enterprise Database / Cloud LLM API。

本地开发用 Docker Compose（`docker-compose.yml`，可选）模拟生产依赖；最终可部署到
Cloud VM / Container Platform / Kubernetes（第一版不要求 K8s）。

## 10. YAGNI 原则

"Production-ready" 不等于堆砌基础设施。不强行引入 Kafka / Kubernetes / 微服务 /
复杂消息队列 / 大量 Agent。优先保证：可靠性、可恢复性、安全性、可观测性、可配置性、可扩展性。
本地与云端尽量保持相同应用代码和运行方式。

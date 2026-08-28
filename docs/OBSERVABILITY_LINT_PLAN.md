# DataGuard AI — 可观测性 + 前端质量门槛 实施规划书

> 面向"无项目上下文的开发 agent"的自包含任务书。按本规划实施，不要自行扩展范围。
> 项目：DataGuard AI，GitHub `git@github.com:xy98773-jpg/DataGuard-AI.git`，分支 `main`，仓库 **private**。
> 交付前必须先本地自测通过，再 push。

---

## 一、目标（两项独立任务）

### 任务 1：可观测性（含 LLM 缓存命中统计）
新增**系统状态页**：展示治理运行指标（总运行/成功率/发现问题数/平均耗时）+ **LLM 结果缓存命中统计**（命中/未命中/命中率/当前缓存条数），用于验证缓存设计是否真的省 token。

### 任务 2：前端质量门槛（vue-tsc 类型检查 + ESLint）
为前端接入 `vue-tsc --noEmit` 类型检查与 ESLint 规范检查，修复现有问题，让 `npm run type-check` 与 `npm run lint` 均通过（0 error）。

**验收标准（必须全部满足）**：
1. 后端新增 `GET /api/system/stats`，返回运行指标 + 缓存统计
2. 前端新增「系统状态」页（侧边栏入口），展示上述指标
3. 前端 `npm run type-check` 通过（vue-tsc 0 error）
4. 前端 `npm run lint` 通过（ESLint 0 error）
5. 后端 88 个测试仍全部通过；前端 `npm run build` 仍成功

---

## 二、项目现状（开发 agent 必须知道的）

```
D:\Desktop\DataGuard AI\
├── backend/                        # Python FastAPI
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口（注册 router 处）
│   │   ├── api/
│   │   │   ├── dashboard.py        # GET /api/dashboard/stats（已有聚合指标，可参考）
│   │   │   └── ...（dataset/workflow/trace/approval/settings/auth/report）
│   │   ├── llm/
│   │   │   └── providers.py        # ★ LLM client + 结果缓存（_cache 模块级变量）
│   │   └── models.py               # ORM：WorkflowRun / Issue / TraceEvent 等
│   ├── tests/                      # pytest 88 个（conftest.py 自动隔离 + fake LLM）
│   └── requirements.txt
└── frontend/                       # Vue3 + Element Plus + Vite + Pinia + TS
    ├── package.json                # scripts: dev/build/preview；devDeps 有 typescript 无 vue-tsc/eslint
    ├── tsconfig.json               # 已 strict: true
    ├── vite.config.ts
    └── src/
        ├── router/index.ts         # 路由（加新页面在这里）
        ├── App.vue                 # 侧边栏菜单（加入口在这里）
        ├── views/                  # 页面：Dashboard/Workflow/Issues/Approval/DataSource/Settings/Login
        ├── components/
        └── stores/app.ts           # Pinia store
```

### 关键事实
- 后端测试命令（Windows）：`cd backend && .venv\Scripts\python.exe -m pytest tests/ -q` → 期望 `88 passed`
- 前端构建：`cd frontend && npm run build` → 期望 `✓ built`
- **LLM 结果缓存实现位置**：`backend/app/llm/providers.py` 模块级：
  ```python
  _CACHE_MAX = 128
  _cache: OrderedDict[str, tuple[float, str, dict]] = OrderedDict()
  _cache_lock = threading.Lock()
  def _cache_get(key): ...   # 命中返回 (payload, usage)，未命中返回 None
  def _cache_put(key, payload, usage): ...
  ```
  **在 `_cache_get` 命中/未命中处加计数器**即可（见步骤 1）。
- **运行平均耗时数据来源**：`TraceEvent` 表有 `latency` 字段（每节点耗时）。按 run_id 聚合求和可得到单次运行总耗时。参考 `backend/app/api/trace.py` 的现有查询方式。
- **Dashboard 聚合参考**：`backend/app/api/dashboard.py::get_dashboard_stats()` 已返回 total_runs/success_rate/issues_found/datasets/recent_runs/quality_trend，可直接复用其中的查询写法。
- 前端页面均为 `<script setup lang="ts">`，Element Plus 全局注册（main.ts 中 `app.component` 遍历注册全部图标）。
- 前端登录：路由守卫在 `router/index.ts`（无 token 跳 /login）；新页面要加入守卫保护（放业务路由区即可自动被守卫覆盖）。

### ⚠️ 已知坑
1. **vue-tsc 首次运行会报大量类型错误**：现有代码用了很多 `any`（例如 `ref<any[]>`、`(row: any)`）。任务 2 的目标是 **type-check 0 error**——处理策略：
   - 优先修正简单类型（为 ref 声明具体类型）；
   - 对第三方/复杂对象可用 `// @ts-expect-error` 或显式 `any`（**在行内注释说明**）；
   - **不要**为了过检查而大改业务逻辑。
2. **ESLint 配置**：前端无任何 eslint 配置，需要从零创建 `eslint.config.js`（flat config，ESLint 9 风格）或 `.eslintrc.cjs`（legacy）。选型建议：**ESLint 9 flat config + eslint-plugin-vue + typescript-eslint**（现代且与 Vite 生态兼容）。
3. **不要动后端业务逻辑**：可观测性只新增接口/计数器，不改治理流程。
4. **不要提交** `.env` / `storage/` / `docker-storage/`（.gitignore 已覆盖）。

---

## 三、任务 1：可观测性实施步骤

### 步骤 1：后端 — 缓存计数器（backend/app/llm/providers.py）

在模块级缓存区增加计数器（注意线程安全）：

```python
# 在 _cache 定义附近新增
_cache_hits = 0
_cache_misses = 0

def _cache_get(key: str):
    global _cache_hits, _cache_misses
    with _cache_lock:
        item = _cache.get(key)
        if item is None:
            _cache_misses += 1
            return None
        ts, payload, usage = item
        if time.time() - ts > 3600:
            _cache.pop(key, None)
            _cache_misses += 1
            return None
        _cache.move_to_end(key)
        _cache_hits += 1
        return payload, usage
```

并新增一个公开函数（供 API 读取统计）：

```python
def cache_stats() -> dict:
    """返回 LLM 结果缓存统计（进程内计数）。"""
    with _cache_lock:
        total = _cache_hits + _cache_misses
        return {
            "hits": _cache_hits,
            "misses": _cache_misses,
            "hit_rate": round(_cache_hits / total * 100, 1) if total else 0.0,
            "size": len(_cache),
            "max_size": _CACHE_MAX,
        }
```

### 步骤 2：后端 — 系统状态接口（新建 backend/app/api/system.py）

```python
"""System stats API: 可观测性指标（运行统计 + LLM 缓存命中统计）。"""

from fastapi import APIRouter
from sqlalchemy import func

from app.llm.providers import cache_stats
from app.models import Dataset, Issue, TraceEvent, Validation, WorkflowRun
from app.storage.database import SessionLocal

router = APIRouter(tags=["system"])


@router.get("/system/stats")
def get_system_stats() -> dict:
    """平台可观测性指标：运行统计 + 平均耗时 + LLM 缓存命中。"""
    with SessionLocal() as session:
        total_runs = (
            session.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.status != "CANCELLED")
            .scalar() or 0
        )
        succeeded = (
            session.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.status == "SUCCESS")
            .scalar() or 0
        )
        issues_found = session.query(func.count(Issue.id)).scalar() or 0
        datasets = session.query(func.count(Dataset.id)).scalar() or 0

        # 平均运行耗时：按 run 聚合 trace_events.latency 总和，再取平均（仅成功/失败 run）
        rows = (
            session.query(
                WorkflowRun.id,
                func.sum(TraceEvent.latency),
            )
            .join(TraceEvent, TraceEvent.run_id == WorkflowRun.id)
            .filter(WorkflowRun.status.in_(["SUCCESS", "FAILED"]))
            .group_by(WorkflowRun.id)
            .all()
        )
        run_times = [t for _, t in rows if t is not None]
        avg_run_seconds = round(sum(run_times) / len(run_times), 1) if run_times else 0.0

    return {
        "total_runs": total_runs,
        "success_runs": succeeded,
        "success_rate": round(succeeded / total_runs * 100, 1) if total_runs else 0.0,
        "issues_found": issues_found,
        "datasets": datasets,
        "avg_run_seconds": avg_run_seconds,
        "cache": cache_stats(),
    }
```

### 步骤 3：后端 — 注册路由（backend/app/main.py）

仿照现有代码注册：

```python
from app.api import system as system_api   # 加入 import 列表

for router in (..., system_api.router):    # 加入 router 元组
    app.include_router(router, prefix=settings.api_prefix)
```

> ⚠️ 注意：`main.py` 中 `from app.api import ...` 和 `for router in (...)` 两处都要加。

### 步骤 4：前端 — 系统状态页（新建 frontend/src/views/SystemStatus.vue）

参考 `frontend/src/views/Dashboard.vue` 的写法（el-card + el-row/el-col 统计卡）：

- 页面标题「系统状态」
- 顶部 4 张统计卡：运行总数 / 治理成功率 / 发现问题数 / 平均运行耗时（秒）
- 下方「LLM 结果缓存」卡片：
  - 命中次数 / 未命中次数 / **命中率**（进度条或大字）
  - 当前缓存条数（size / max_size）
  - 说明文案：`缓存 key = prompt 哈希，TTL 1 小时；同一数据重复治理直接命中，节省 token。重启后端后计数清零（进程内缓存）。`
- 数据源：`GET /api/system/stats`（无需登录 token，只读）
- 页面结构示例：
  ```vue
  <script setup lang="ts">
  import { onMounted, ref } from 'vue'
  const stats = ref<any>(null)
  async function load() {
    const resp = await fetch('/api/system/stats')
    stats.value = await resp.json()
  }
  onMounted(load)
  </script>
  <template>
    <div class="system-page">
      <el-row :gutter="12">
        <el-col :span="6"><el-card>…运行总数 {{ stats?.total_runs }}…</el-card></el-col>
        …（4 张卡）…
      </el-row>
      <el-card>…LLM 结果缓存…</el-card>
    </div>
  </template>
  ```

### 步骤 5：前端 — 路由 + 侧边栏入口

- `frontend/src/router/index.ts`：新增
  ```ts
  {
    path: '/system',
    name: 'system',
    component: () => import('../views/SystemStatus.vue'),
  },
  ```
  （放在其他业务路由之间即可，路由守卫自动保护）
- `frontend/src/App.vue`：侧边栏 `<el-menu>` 加一项
  ```html
  <el-menu-item index="/system">
    <el-icon><Monitor /></el-icon>
    <span>系统状态</span>
  </el-menu-item>
  ```
  （`Monitor` 图标在 @element-plus/icons-vue 中存在，main.ts 已全局注册）

---

## 四、任务 2：前端质量门槛实施步骤

### 步骤 1：安装依赖（frontend 目录下）

```bash
npm install -D vue-tsc eslint @vue/eslint-config-typescript @vue/eslint-config-prettier eslint-plugin-vue typescript-eslint
```

> 说明：`@vue/eslint-config-typescript` + `typescript-eslint` 提供 TS 规则；若不想引入 prettier，可去掉 `@vue/eslint-config-prettier`，仅保留 lint 检查。

### 步骤 2：package.json 加 scripts

在 `frontend/package.json` 的 `"scripts"` 中新增：

```json
"type-check": "vue-tsc --noEmit",
"lint": "eslint src --ext .ts,.vue"
```

### 步骤 3：创建 ESLint 配置（frontend/eslint.config.js，flat config）

```js
import pluginVue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'scripts/**'] },
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },
  {
    rules: {
      'vue/multi-word-component-names': 'off',     // 单文件名单词组件名允许
      'vue/no-v-html': 'off',
      '@typescript-eslint/no-explicit-any': 'off', // 项目广泛使用 any，先不强制
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
)
```

> 若安装的 eslint 是 v8（而非 v9），flat config 需 `export default [...配置]` 或改用 `.eslintrc.cjs` legacy 格式；按实际安装版本选择，**以 lint 能跑且 0 error 为准**。

### 步骤 4：修复类型错误与 lint 报错

1. 先跑 `npm run type-check`，记录错误清单。
2. 逐文件修复：
   - `ref` / `reactive` 泛型显式声明（如 `ref<File | null>(null)`）；
   - 无法快速解决的第三方/复杂对象：`// @ts-expect-error 原因说明` 或显式 `as any`；
   - 未使用变量：删除或前缀 `_`。
3. 再跑 `npm run lint`，修复报错（多为未使用变量、隐式 any、组件命名）。
4. **目标：两个命令都 0 error**（允许 warn 存在）。

> ⚠️ 重要：修复过程**不要改变任何业务逻辑**，只做类型标注/格式调整。改完必须 `npm run build` 确认仍成功。

---

## 五、本地自测（push 前必须执行）

```bash
# 后端
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q        # 期望 88 passed

# 前端
cd frontend
npm run type-check                                    # 期望 0 error
npm run lint                                          # 期望 0 error
npm run build                                         # 期望 built 成功
```

若后端测试新增了 system 接口但没写测试，**建议**补一个最小测试 `backend/tests/test_system.py`（验证 /api/system/stats 返回字段齐全、缓存命中率计算正确）——不强求，但加分。

---

## 六、推送

```bash
git add -A
git commit -m "feat: 系统状态页（可观测性+缓存命中统计）+ 前端 type-check/lint 质量门槛"
git push origin main
```

推送后 GitHub Actions 自动跑（CI #N），**两个 job 必须全绿**——这也是本轮交付的自动验证。

---

## 七、禁止事项（范围红线）

- **不要改动**治理核心逻辑（agents/graph/tools/governance 等）。
- **不要改动** `docker-compose.yml` / Dockerfile（除非绝对必要）。
- **不要提交**密钥与本地数据（.env/storage/docker-storage）。
- **不要**重命名/删除现有路由、页面、组件（只新增）。

---

## 八、交付清单

- [ ] `backend/app/api/system.py` + main.py 注册
- [ ] `providers.py` 缓存计数器 + `cache_stats()`
- [ ] （可选）`backend/tests/test_system.py`
- [ ] `frontend/src/views/SystemStatus.vue`
- [ ] `frontend/src/router/index.ts` + `frontend/src/App.vue` 加入口
- [ ] `frontend/package.json` 加 `type-check` / `lint` scripts + devDeps
- [ ] `frontend/eslint.config.js`（或 .eslintrc）
- [ ] 本地：后端 88 passed / type-check 0 error / lint 0 error / build 成功
- [ ] push 后 Actions 两 job 全绿

## 九、完成后通知

开发完成后，回复中说明：
1. 系统状态页展示效果（可截图/文字描述）
2. type-check / lint 各修了多少个问题、最终 0 error
3. 是否用了 @ts-expect-error / as any（数量与位置）
4. Actions 运行结果

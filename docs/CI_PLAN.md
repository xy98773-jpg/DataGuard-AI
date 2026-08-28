# DataGuard AI — CI/CD 实施规划书（GitHub Actions）

> 面向"无项目上下文的开发 agent"的自包含任务书。按本规划实施，不要自行扩展范围。
> 项目：DataGuard AI（企业数据治理 Agent 平台），GitHub 仓库 `git@github.com:xy98773-jpg/DataGuard-AI.git`，分支 `main`。

---

## 一、目标

在仓库配置 **GitHub Actions CI**：每次 push / pull request 到 `main` 自动执行后端测试 + 前端构建，结果以**状态徽章**显示在仓库首页与 README。

**验收标准（必须全部满足）**：
1. push 后 GitHub Actions 自动运行两个 job（backend-test / frontend-build）
2. 后端测试 **88 个全部通过**（CI 用 `fake` LLM 离线跑，不需要任何 API Key）
3. 前端 `npm run build` 成功
4. 仓库首页出现绿色「✅ build passing / test passing」徽章
5. README 顶部嵌入徽章（SVG 图片链接）

---

## 二、项目现状（开发 agent 必须知道的）

```
D:\Desktop\DataGuard AI\
├── backend/                 # Python 后端（FastAPI + LangGraph + SQLAlchemy + SQLite）
│   ├── app/                 # 应用代码
│   ├── tests/               # pytest 测试（88 个，全部离线可跑）
│   ├── requirements.txt     # 后端依赖
│   └── conftest.py 不存在    # ⚠️ 注意：tests/conftest.py 在 tests/ 目录下
├── frontend/                # Vue3 + Element Plus + Vite + Pinia
│   ├── package.json         # 依赖与 scripts（build = vite build）
│   └── src/
├── docker-compose.yml       # 无关 CI，不要动
└── .gitignore               # 已排除 .env / storage / docker-storage
```

### 关键事实
- **后端测试命令**（Windows 本地）：
  ```bash
  cd backend
  .venv\Scripts\python.exe -m pytest tests/ -q
  ```
  期望结果：`88 passed`
- **测试环境隔离已内置**（`backend/tests/conftest.py` 顶部自动设置环境变量，无需 CI 额外配置）：
  - `DG_DATABASE_URL` → 临时 SQLite（不碰真实库）
  - `DG_LLM_PROVIDER=fake` → **离线假模型**，测试不调用真实 LLM、不需要 API Key
  - `DG_WORKFLOW_EXECUTION_MODE=sync` → 工作流同步执行，测试确定性
- **前端构建命令**：
  ```bash
  cd frontend
  npm ci && npm run build
  ```
  期望结果：`✓ built in ...`
- **后端 Python 版本**：本地 3.11（requirements 兼容 3.10+；CI 用 **3.12** 亦可，建议 3.12 以与 Docker 镜像一致）
- **前端 Node 版本**：本地 v25（CI 用 **20 LTS**，稳定；无 packageManager 字段，用 npm）

### ⚠️ 已知坑（必须处理，否则 CI 会挂）
1. **PDF 导出测试依赖本机浏览器**：`backend/tests/test_report.py::test_render_pdf_is_valid` 调用 `render_pdf()`，该函数用系统 Edge/chromium 打印 PDF。**CI（ubuntu-latest）没有 Edge**，候选列表包含 `/usr/bin/chromium` 与 `/usr/bin/chromium-browser`。→ CI 后端 job 需 `apt-get install -y chromium`（Ubuntu 装后路径通常是 `/usr/bin/chromium-browser`），或在 CI 中设环境变量跳过该测试（优先选择装 chromium，保持测试完整）。
2. **pytest 需要 `--disable-warnings` 可选**：现有 17 个 warning 不影响通过，不必处理。
3. **仓库还没有 `.github/workflows/` 目录**：需要新建。

---

## 三、实施步骤

### 步骤 1：创建 `.github/workflows/ci.yml`

在仓库根目录新建 `.github/workflows/ci.yml`，内容如下（可直接复制，按需微调）：

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend-test:
    name: Backend Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # PDF 测试需要浏览器（无本机 Edge，用 chromium）
      - name: Install chromium (for PDF export tests)
        run: |
          sudo apt-get update
          sudo apt-get install -y --no-install-recommends chromium
          echo "CHROMIUM_BIN=/usr/bin/chromium-browser" >> $GITHUB_ENV

      - name: Install backend dependencies
        working-directory: backend
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run backend tests
        working-directory: backend
        run: |
          python -m pytest tests/ -q

  frontend-build:
    name: Frontend Build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install frontend dependencies
        working-directory: frontend
        run: npm ci

      - name: Build frontend
        working-directory: frontend
        run: npm run build
```

> 说明：
> - 两个 job 并行执行，互不依赖。
> - 后端 job 的 chromium 是给 `render_pdf()` 找浏览器用的（`report_service.py` 候选含 `/usr/bin/chromium-browser`）。
> - 若某镜像/网络导致 chromium 安装失败，可改为在 CI 中跳过 PDF 测试（见"备选方案"）。

### 步骤 2：验证 CI 配置文件语法（可选）

本地可以用 `actionlint` 或直接推送后看 Actions 日志；没有 actionlint 也不阻塞。

### 步骤 3：README 顶部加徽章

在 `README.md` 顶部（标题附近）插入两个徽章：

```markdown
![CI](https://github.com/xy98773-jpg/DataGuard-AI/actions/workflows/ci.yml/badge.svg)
```

或分开两个：
```markdown
![Backend Tests](https://github.com/xy98773-jpg/DataGuard-AI/actions/workflows/ci.yml/badge.svg)
```
（GitHub Actions badge 同一 workflow 一个 SVG 即可；如需按 job 徽章，可查 Actions 页面「Create status badge」生成各 job 链接。）

### 步骤 4：本地自测（推送前）

在**本机 Windows** 验证 CI 会跑的命令能通过：

```bash
# 后端（隔离环境自动生效）
cd backend
.venv\Scripts\python.exe -m pytest tests/ -q
# 期望 88 passed

# 前端
cd frontend
npm run build
# 期望 built 成功
```

> 若本机 PDF 测试因无 Edge 失败，说明环境问题；本机一般有 Edge 能过。CI 用 chromium。

### 步骤 5：推送并观察

```bash
git add -A
git commit -m "ci: add GitHub Actions (backend tests + frontend build)"
git push origin main
```

推送后：
1. 打开 GitHub 仓库 → Actions 页 → 应看到 CI workflow 运行，两个 job 绿勾。
2. 首次运行约 2-4 分钟（装依赖）。
3. 失败则点进 job 看日志，按错误修（常见：依赖版本、chromium 安装、路径）。

### 步骤 6：确认徽章

- 仓库首页应显示 Actions 状态徽章（绿色「passing」）。
- README 顶部徽章图片加载成功。

---

## 四、备选方案（如果 chromium 安装失败）

若 CI 中 `apt-get install chromium` 失败或太慢，**改为跳过 PDF 测试**：

在 `ci.yml` 后端 job 中加环境变量，并给 `test_report.py` 加条件跳过：

```yaml
      - name: Run backend tests
        working-directory: backend
        env:
          DG_SKIP_PDF_TEST: "1"
        run: |
          python -m pytest tests/ -q
```

在 `backend/tests/test_report.py::test_render_pdf_is_valid` 顶部加：

```python
import os
import pytest

@pytest.mark.skipif(os.environ.get("DG_SKIP_PDF_TEST") == "1", reason="CI 无浏览器")
def test_render_pdf_is_valid(run_id):
    ...
```

> 优先用主方案（装 chromium），测试完整；备选仅作兜底。

---

## 五、禁止事项（范围红线）

- **不要改动**任何 `backend/app/`、`frontend/src/` 业务代码（CI 只是基础设施）。
- **不要提交** `.env`、`storage/`、`docker-storage/`、`.venv/`、`node_modules/`（.gitignore 已覆盖，保持即可）。
- **不要**引入额外 CI 平台（如 Jenkins/Travis），只用 GitHub Actions。
- **不要**加 Docker 构建 job（那是后续部署环节，本轮只做测试 + 前端构建）。

---

## 六、交付清单

- [ ] `.github/workflows/ci.yml`（内容见上）
- [ ] `README.md` 顶部徽章
- [ ] （备选方案下）`test_report.py` 的 skip 标记
- [ ] 推送后 Actions 全绿
- [ ] 仓库首页/README 显示绿色徽章

## 七、完成后通知

开发完成后，请在回复中说明：
1. `ci.yml` 最终内容摘要
2. 是否用了备选方案（chromium 还是跳过 PDF 测试）
3. Actions 运行结果截图/日志摘要（或"已推送，待运行"）
4. README 徽章是否显示

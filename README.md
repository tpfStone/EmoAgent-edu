# EmoEdu MAS

EmoEdu MAS 是一个面向中国初中生（12-15 岁）的中文情感教育多智能体对话系统。项目目标是在安全边界内生成更具体、更适龄、更有社会情感学习价值的回应，并用可验证的 critic / pairwise 流程为后续离线优化积累证据。

当前仓库已集成 FastAPI 后端运行时、F9 / corpus 离线实验链路，以及 `frontend/` pnpm workspace。默认 `LLM_PROVIDER=mock`，本地测试不需要外网模型调用。

## Background

系统以 CASEL 社会情感学习能力作为顶层教育目标，用 EPITOME 的 ER / IP / EX 维度解释单条支持性回应质量，并把 IRI 作为认知共情与情感共情的理论说明层。当前工程主线需要区分两件事：

- 当前 `/chat` 运行时已跑通 F1-F4，但 F4 仍使用 pointwise `scores` / `weighted_total` 选择最佳候选。
- 目标 F4 主线是 pairwise preference selection。pairwise service、规格和离线 pilot 已存在，但尚未接管默认 runtime；F9 / pairwise gate 未通过前，偏好对不能直接用于 DPO。

## Architecture

后端入口是 `app.main:app`，挂载以下接口：

- `POST /api/safety/evaluate`：F1 安全门，基于 C-SSRS 风险分级，yellow / red 中断生成并返回转介话术。
- `POST /api/scenario/evaluate`：F2 情境分析，输出学业压力、同伴关系、亲子摩擦或其他，并激活 CASEL 辅助维度。
- `POST /api/generator/generate`：F3 双取向生成，当前包含情感共情型 `c1` 与认知共情型 `c2`。
- `POST /api/critic/evaluate`：F4 pointwise critic，使用 EPITOME、激活 CASEL 维度和 boundary 检测，按 `weighted_total` 择优。
- `POST /chat`：编排入口，串联 F1-F4、历史窗口、落库和最终回复。

RAG 检索（F6）、第三取向行动建议（F8）、pairwise runtime adapter 和 DPO（F7）仍是后续或离线验证阶段内容。

更细的端到端输入、处理、输出和去向见 [`docs/specs/README.md#端到端技术路线表`](docs/specs/README.md#端到端技术路线表)。

## Figures

<p>
  <img src="./docs/figures/figure-1-three-phase-lifecycle.svg" alt="EmoEdu MAS 三阶段生命周期" width="760">
</p>

<p>
  <img src="./docs/figures/figure-2-runtime-pipeline.svg" alt="当前 /chat 运行时与目标 pairwise 迁移点" width="760">
</p>

上图是当前 `/chat` 运行时与目标 pairwise 迁移点的视觉总览；完整技术路线表以 [`docs/specs/README.md#端到端技术路线表`](docs/specs/README.md#端到端技术路线表) 为准。

<p>
  <img src="./docs/figures/figure-3-argument-loop.svg" alt="理论框架到 Pairwise Gate 的证据链" width="760">
</p>

## Quick Start

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest tests -q
uvicorn app.main:app --reload
```

若 PowerShell 拦截 `Activate.ps1`，可在当前窗口临时执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

启动后访问：

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

### Database

生产目标数据库是 PostgreSQL，配置项为：

```env
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
```

迁移命令：

```powershell
alembic upgrade head
```

测试使用 SQLite in-memory，不需要本地 PostgreSQL。

### Tests

```powershell
python -m pytest tests/test_services -q
python -m pytest tests/test_handlers -q
python -m pytest tests -q
```

### Frontend

前端位于 `frontend/`，是 pnpm workspace，包含学生端、研究分析台和 shared API/type 层。

```powershell
pnpm --dir frontend install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

默认 mock 模式不连接真实后端。live 模式可设置 `VITE_API_MODE=live`，Vite 会将 `/chat` 代理到 `http://localhost:8000`。

- Student app: http://localhost:5173
- Research console: http://localhost:5174
- GitHub Pages mock 与本机 live 演示说明：`docs/frontend/github-pages-mock-local-live.md`

## Documentation

- `docs/README.md`：文档结构总览和推荐阅读路径。
- `docs/overview/`：项目方案、工程拆分和阶段计划。
- `docs/specs/`：F1-F4、F4 pairwise 与 F9 的实现规格。
- `docs/corpus/`：合成语料、F9 产物和 pairwise pilot 记录。
- `docs/frontend/`：前端设计、部署和演示说明。
- `docs/figures/`：项目图示 SVG。
- `docs/issues/`：开发过程问题记录。

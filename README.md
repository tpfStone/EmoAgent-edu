# EmoEdu MAS

中文 | [English](README_EN.md)

EmoEdu MAS 是一个面向中国初中生（12-15 岁）的中文情感教育多智能体对话系统。项目目标是在安全边界内生成更具体、更适龄、更有社会情感学习价值的回应，同时把 critic、pairwise 和人工校准结果沉淀为后续离线优化证据。

当前项目已经从“每轮完整同步跑 F1-F4”调整为更适合产品交互的快慢双路径：

```text
在线路径：快
首次对话：F1 本地安全门 -> F2 情境/支持模式/风险兜底 -> F3 单候选流式返回 -> 后台 F4
后续对话：轻量 CBT 支持 -> 注入最近历史 -> 如 F4 guidance 已完成则注入 -> 流式返回

后台路径：准
F4 critic -> 写质量标签和 session guidance -> 聚合实验报告 -> 反哺 prompt / 策略表 / DPO 数据
```

这样保留 generator-critic、多智能体和离线优化的理论依据，也避免让学生在真实交互中等待完整双候选和 critic 链路。

## 当前状态

- 后端已集成 FastAPI、PostgreSQL、Redis 会话历史、SSE 流式返回和 `/chat` 编排入口。
- F1 安全门在 `/chat` 中默认使用本地分类器：`bert-base-chinese` 文本特征 + 人工审查关键词特征 + soft rule + 阈值。
- F2 使用 LLM 判断情境、支持模式和二次安全兜底；即使 F1 漏判，F2 仍可要求转介。
- F3 可在本地 `exp/data/psyqa_labelled.json` 存在时使用 PsyQA-derived 策略先验和 support card；数据缺失时 support-card enrichment 为空或退回通用策略，首轮仍按 F2 的 `support_mode` 生成单候选。
- F4 critic 不再阻塞在线响应，而是在后台生成 `session guidance`，下一轮对话可使用。
- `exp/` 保存 PsyQA 标注、F1 训练、F3 RAG 验证和 F4 pairwise 对照实验，详见 `exp/README.md`。
- 默认 `LLM_PROVIDER=mock`，可无外网运行测试；真实交互推荐使用 DeepSeek v4：在线生成走 `deepseek-v4-flash`，后台 critic 走 `deepseek-v4-pro`。

## Architecture

后端入口是 `app.main:app`，核心接口如下：

| 接口 | 用途 | 当前口径 |
| --- | --- | --- |
| `POST /chat` | 非流式编排入口 | 按快路径返回完整 `ChatResponse` |
| `POST /chat/stream` | SSE 流式编排入口 | 学生端推荐使用，事件包括 `stage`、`metadata`、`delta`、`done` |
| `POST /api/safety/classifier/evaluate` | F1 本地分类器安全门 | 生产链路使用，启动时预加载模型 |
| `POST /api/safety/evaluate` | F1 LLM 安全门 | 保留兼容和对照实验，不是 `/chat` 默认安全门 |
| `POST /api/scenario/evaluate` | F2 情境分析 | 输出 `scenario`、`activated_casel`、`support_mode`、`secondary_safety` |
| `POST /api/generator/generate` | F3 双取向生成模块接口 | 实验和调试可用；`/chat` 首轮在线只生成一个方向 |
| `POST /api/critic/evaluate` | F4 pointwise critic | 模块接口可同步调用；`/chat` 中作为后台任务使用 |
| `GET /api/memory/status` | F6 memory/RAG 状态 | 默认关闭，后续扩展长期记忆 |
| `DELETE /api/memory` | 清理 memory/RAG 数据 | 支持按 `anonymous_user_id` 或 `session_id` 清理 |

`/chat` 和 `/chat/stream` 的请求体：

```json
{
  "session_id": "browser-session-id",
  "anonymous_user_id": "optional-stable-browser-user-id",
  "current_message": "我最近考试压力很大，晚上睡不着"
}
```

`anonymous_user_id` 用于无登录场景下的连续性设计；同一浏览器可长期保存一个匿名 ID，多个 session 可以归属于同一匿名用户。未登录时也可以只传 `session_id`。

## Figures

<p>
  <img src="./docs/figures/figure-1-three-phase-lifecycle.svg" alt="EmoEdu MAS 三阶段生命周期" width="760">
</p>

<p>
  <img src="./docs/figures/figure-2-runtime-pipeline.svg" alt="当前 /chat 快路径与后台/离线路径" width="760">
</p>

<p>
  <img src="./docs/figures/figure-3-argument-loop.svg" alt="理论框架到 Pairwise Gate 的证据链" width="760">
</p>

## Quick Start

### 1. Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

如果要复现 `exp/` 下的算法实验和报告脚本，再安装实验依赖：

```powershell
python -m pip install -r requirements-exp.txt
```

若 PowerShell 拦截 `Activate.ps1`：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

默认 mock 模式可直接跑测试：

```powershell
python -m pytest tests -q
```

### 2. F1 Safety Model

F1 本地安全门模型不提交到 GitHub。模型产物已经发布到 HuggingFace：

```text
https://huggingface.co/Nacgisac/EmoEduF1-bert-base-chinese/tree/main/manual-A-pattern-v1
```

真实后端交互建议先下载模型：

```powershell
hf auth login

hf download Nacgisac/EmoEduF1-bert-base-chinese `
  --include "manual-A-pattern-v1/*" `
  --local-dir exp/models/f1_safety_gate `
  --revision main
```

下载完成后，本地目录应为：

```text
exp/models/f1_safety_gate/manual-A-pattern-v1/
```

其中至少包含：

```text
hybrid_safety_classifier.pt
feature_scalers.joblib
manual_keywords.json
manual_keywords_grouped.json
model_config.json
summary.json
inference_benchmark.json
manual_keyword_audit.csv
hybrid_test_confusion_matrix.csv
```

对应 `.env`：

```env
F1_SAFETY_MODEL_DIR=exp/models/f1_safety_gate/manual-A-pattern-v1
F1_SAFETY_PRELOAD=true
F1_SAFETY_REQUIRED=false
F1_SAFETY_HF_REPO=Nacgisac/EmoEduF1-bert-base-chinese
F1_SAFETY_HF_REVISION=main
```

`F1_SAFETY_REQUIRED=false` 时，如果本地模型缺失，`/chat` 会安全退回 LLM/mock 安全门，便于研究人员先跑通系统。生产或正式实验复现建议设为：

```env
F1_SAFETY_REQUIRED=true
```

此时模型缺失会直接失败并提示下载命令，避免安全门能力和预期不一致。

### 3. DeepSeek / DashScope API Key

推荐的真实 LLM 交互配置使用 DeepSeek OpenAI 兼容接口。F1 安全门默认使用本地分类器，不依赖 DeepSeek；DeepSeek 主要用于 F2 情境/支持模式、F3 回复生成和后台 F4 critic。

1. 创建 DeepSeek API Key。
2. 确认账户有可用额度。
3. 在 `.env` 中填入：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro
CRITIC_DEEPSEEK_THINKING=enabled
```

`deepseek-v4-flash` 用于在线低延迟回复；`deepseek-v4-pro` 用于后台 F4 critic 和质量评估。旧的 `deepseek-chat` 只适合临时兼容验证，不建议用于正式复现。

真实 LLM 交互使用阿里云百炼 DashScope 兼容 OpenAI 接口：

1. 登录阿里云百炼控制台并开通模型服务。
2. 创建 API Key。
3. 确认所选模型有额度，或关闭“仅使用免费额度”限制。
4. 在 `.env` 中填入：

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3.7-plus
DASHSCOPE_THINKING=disabled
CRITIC_DASHSCOPE_MODEL=qwen3.7-plus
CRITIC_DASHSCOPE_THINKING=disabled
```

如果只想本地跑测试或查看前端 mock，可以保持：

```env
LLM_PROVIDER=mock
```

### 4. Database and Redis

当前默认数据库是 PostgreSQL：

```env
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
```

迁移：

```powershell
alembic upgrade head
```

Redis 用于聊天历史和后台 F4 guidance：

```env
REDIS_URL=redis://localhost:6379/0
```

启动后端：

```powershell
uvicorn app.main:app --reload
```

访问：

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

### 5. Frontend

前端位于 `frontend/`，是 pnpm workspace，包含学生端、研究分析台和 shared API/type 层。

```powershell
pnpm --dir frontend install
```

mock 模式：

```powershell
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
```

连接本地后端 live 模式：

```powershell
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:student
```

常用检查：

```powershell
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

- Student app: http://localhost:5173
- Research console: http://localhost:5174

## Tests

推荐检查顺序：

```powershell
python -m pytest tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

## Data Policy

公开仓库不包含完整 PsyQA-derived labelled data，也不提交 sample JSON 导出。完整实验复现者需要自行准备并放置：

```text
exp/data/psyqa_labelled.json
```

这个文件是 F1/F3/F4 实验和 F3 support-card enrichment 的本地参考数据。文件缺失时，系统和默认测试仍可运行；影响是 F3 的 strategy priors/support cards 为空或退回通用策略，不改变默认数据路径、运行时代码或 API 设计。

## Experiment Entry

算法实验统一放在 `exp/`：

- `exp/README.md`：实验流程、关键结果、问题记录和复现命令。
- `exp/data/README.md`：公开数据边界；完整 `psyqa_labelled.json` 需复现者本地放置，不提交 GitHub。
- `exp/models/f1_safety_gate/manual-A-pattern-v1/`：已迁入生产的 F1 分类器，本地从 HuggingFace 下载，不提交 GitHub。
- `exp/runs/`：F1/F3/F4 各轮实验输出；原始 run 产物体积较大，默认不提交 GitHub，关键指标已整理在 `exp/README.md`。

默认测试只保证 `exp/*.py` 的语法和入口结构。完整实验运行还需要 `requirements-exp.txt`、`.env`、模型文件、API key、本地 `exp/data/psyqa_labelled.json` 和本地 `exp/runs/` 数据。

`exp/artifacts.manifest.json` 记录实验资产如何进入完整体系，并把每项资产标为 `runtime`、`runtime_reference`、`background`、`offline` 或 `archive`。维护口径见 `docs/specs/exp-integration-map.md`：`exp` 是完整体系的一部分，但实验脚本不进入 `/chat` 在线阻塞路径。

## Documentation

- `docs/README.md`：文档结构总览和推荐阅读路径。
- `docs/README_EN.md`：英文文档地图和公开阅读入口。
- `docs/specs/`：F1-F4、F4 pairwise、F9 的实现规格，以及 `README.md` / `exp-integration-map.md` 中的当前集成边界。
- `docs/specs/README_EN.md`：英文规格摘要。
- `docs/plans/`：未完成阶段计划；当前保留 Phase 2B gate。
- `docs/overview/`：项目方案、工程拆分和阶段计划。
- `docs/frontend/`：前端设计、部署和演示说明。
- `docs/corpus/`：旧合成语料、F9 与 pairwise 试点记录。
- `docs/issues/`：开发过程问题记录。
- `docs/figures/`：项目图示 SVG。

## Current Production Principle

不要把所有研究 agent 都放到在线阻塞路径里。在线路径负责“快、安全、能交流”，后台路径负责“准、可评估、可迭代”。F4、pairwise、DPO 和长期 RAG 都应以这个原则接入。

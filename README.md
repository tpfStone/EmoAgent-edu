# EmoEdu MAS

中文 | [English](README_EN.md)

> 面向中国 12-15 岁初中生的安全优先情感教育多智能体系统。

## 项目概览

EmoEdu MAS 支持学生在学业压力、同伴关系和亲子冲突等常见场景中表达情绪，并获得适龄、具体、有社会情感学习价值的回应。系统结合本地安全门、情境感知路由、流式学生回复和后台 critic，把在线交互保持在低延迟路径上，同时为后续研究和质量改进保留可追踪证据。

本项目是教育支持系统，不是诊断、心理治疗、医疗或紧急服务。高风险输入会离开普通生成路径，转向固定的安全转介提示，鼓励学生立即联系可信任成年人和适当公共服务。

## 设计动机

- **安全先于生成：** 每轮对话都先经过 F1 安全门；首轮还经过 F2 二次安全兜底。
- **情境感知支持：** F2 基于场景、支持模式和配置化 CASEL 映射，为首轮回复提供路由依据。
- **学生端低延迟：** F3 在线首轮生成一个路由后的候选并流式返回，不让学生等待完整双候选 critic 链路。
- **后台质量闭环：** F4 在回复后写入质量标签和会话指导；已完成的会话指导可影响后续轮次，但不阻塞当前回复。
- **研究边界清晰：** pairwise selection、F9 人工校准、DPO 和 F6 memory/RAG prompt injection 保持离线、门控或默认关闭，除非代码和验证状态明确改变。

## 当前运行边界

| 层级 | 当前行为 | 对学生端延迟的影响 |
| --- | --- | --- |
| 首轮对话 | F1 本地安全门 -> F2 情境/支持路由和二次安全 -> F3 单候选流式回复 | 在线阻塞快路径 |
| 后续对话 | F1 安全门 -> 最近 Redis 历史 -> 可选已完成 F4 guidance -> 轻量流式生成 | 在线阻塞快路径 |
| 后台质量路径 | F4 pointwise critic -> 质量标签 -> Redis 会话指导 | 不阻塞当前回复 |
| 离线研究 | F3 双取向候选、F4 pairwise 实验、F9 人工校准、DPO 准备 | 不进入默认 `/chat` 阻塞路径 |
| 默认关闭能力 | F6 memory/RAG prompt injection | 需通过独立隐私和质量 gate 后才能启用 |

## 产品界面

### 学生端

学生端提供流式对话、会话连续性、安全转介展示和用户可控的记录处理，不暴露内部智能体轨迹、critic 标签或研究诊断字段。

<p align="center">
  <img src="./docs/screenshots/student-app-empty-state.png" alt="学生端空状态界面" width="900">
</p>

<p align="center"><em>学生端空状态界面</em></p>

### 研究分析台

研究分析台展示风险路由、情境元数据、生成内容和后台 F4 会话指导状态等诊断信息。它用于研究、调试和演示，不面向学生使用。

<p align="center">
  <img src="./docs/screenshots/research-console-single-turn-trace.png" alt="研究分析台单轮追踪界面" width="900">
</p>

<p align="center"><em>研究分析台单轮追踪界面</em></p>

## 架构

三张图分别说明运行边界、当前快慢路径和从理论框架到验证 gate 的证据链。

### 1. 运行边界与验证 gate

<p align="center">
  <img src="./docs/figures/figure-1-runtime-boundary.zh.svg" alt="EmoEdu MAS 运行边界与验证 gate" width="760">
</p>

### 2. 当前 `/chat` 快路径与后台/离线路径

<p align="center">
  <img src="./docs/figures/figure-2-runtime-pipeline.zh.svg" alt="当前 EmoEdu MAS 运行、后台与离线路径" width="760">
</p>

### 3. 理论框架到 pairwise 验证 gate 的证据链

<p align="center">
  <img src="./docs/figures/figure-3-argument-loop.zh.svg" alt="理论框架到 pairwise 验证 gate 的证据链" width="760">
</p>

## 核心能力

| 能力 | 状态 | 说明 |
| --- | --- | --- |
| F1 本地安全分类器 | 已实现 | 本地模型可预加载；`yellow`/`red` 会中断普通生成。 |
| F2 情境和支持路由 | 已实现 | 输出 scenario、配置化 CASEL 维度、support mode 和 secondary safety。 |
| F3 学生端流式回复 | 已实现 | 在线首轮生成一个路由后的候选；双取向候选保留给实验和调试。 |
| F4 后台 critic 会话指导 | 已实现 | 回复后后台运行，不阻塞学生端。 |
| 匿名会话连续性 | 已实现 | 使用 `anonymous_user_id` 和 `session_id` 组织无登录连续体验。 |
| 研究分析台 | 已实现 | 展示内部轨迹和后台 critic 状态。 |
| F4 pairwise selector | 离线 / 门控 | 不是默认在线选择器。 |
| DPO 训练闭环 | 未来 / 门控 | 只能使用通过验证的偏好数据。 |
| F6 memory/RAG prompt injection | 默认关闭 | 需要通过隐私、删除、隔离和质量 gate 后再启用。 |

## 快速启动（默认本地模式）

当前公开配置默认使用 `mock`，用于本地开发、自动化测试和无外部凭据的界面检查。正式演示或证据采集应切换到真实模型提供方，并记录实际模型提供方、模型和配置；如果截图或视频使用 `mock`，需要明确标注。

### 安装

```powershell
# 后端
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env

# 前端
pnpm --dir frontend install
```

### 启动界面

```powershell
# 终端 1 - 后端
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2 - 学生端
pnpm --dir frontend dev:student

# 终端 3 - 研究分析台
pnpm --dir frontend dev:console
```

打开：

- 学生端：<http://localhost:5173>
- 研究分析台：<http://localhost:5174>
- 后端 API：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

## 完整本地配置：真实模型模式

### 1. 配置后端

复制 `.env.example` 到 `.env`，然后按实际提供方配置。不要提交 `.env` 或在演示中暴露 key。

DeepSeek:

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
CRITIC_DEEPSEEK_MODEL=deepseek-v4-pro
CRITIC_DEEPSEEK_THINKING=enabled
```

DashScope:

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3.7-plus
DASHSCOPE_THINKING=disabled
CRITIC_DASHSCOPE_MODEL=qwen3.7-plus
CRITIC_DASHSCOPE_THINKING=disabled
```

### 2. 恢复 F1 安全模型

F1 本地安全模型不提交到 GitHub，需要从 Hugging Face 下载到本地：

```powershell
hf auth login

hf download Nacgisac/EmoEduF1-bert-base-chinese `
  --include "manual-A-pattern-v1/*" `
  --local-dir exp/models/f1_safety_gate `
  --revision main
```

预期目录：

```text
exp/models/f1_safety_gate/manual-A-pattern-v1/
```

`.env.example` 中当前默认：

```env
F1_SAFETY_MODEL_DIR=exp/models/f1_safety_gate/manual-A-pattern-v1
F1_SAFETY_PRELOAD=true
F1_SAFETY_REQUIRED=false
F1_SAFETY_HF_REPO=Nacgisac/EmoEduF1-bert-base-chinese
F1_SAFETY_HF_REVISION=main
```

正式复现或生产演示建议设置：

```env
F1_SAFETY_REQUIRED=true
```

### 3. 启动数据库、Redis 和迁移

默认数据库示例使用 PostgreSQL：

```env
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
```

本地临时开发也可以使用 SQLite：

```env
DATABASE_URL=sqlite+aiosqlite:///./local-dev.sqlite
```

运行迁移：

```powershell
alembic upgrade head
```

Redis 用于聊天历史和后台 F4 会话指导：

```env
REDIS_URL=redis://localhost:6379/0
```

如果本机没有 Redis，可用 Docker 启动：

```powershell
docker run --name emoedu-redis -p 6379:6379 -d redis:7-alpine
```

后续复用同一个容器：

```powershell
docker start emoedu-redis
docker exec emoedu-redis redis-cli ping
```

预期输出：

```text
PONG
```

### 4. 启动真实模型应用

```powershell
# 终端 1 - 后端
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2 - 学生端
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:student

# 终端 3 - 研究分析台
$env:VITE_API_MODE="live"
pnpm --dir frontend dev:console
```

检查后端：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## 配置模式

| 模式 | 用途 | 外部凭据 | 证据用途 |
| --- | --- | --- | --- |
| `mock` | UI 开发、自动化测试、离线流程检查 | 否 | 只能作为明确标注的 mock 证据 |
| `deepseek` | 通过 DeepSeek 兼容配置进行真实模型生成和 critic | 是 | 记录精确模型和配置后可用于证据 |
| `dashscope` | 通过 DashScope OpenAI 兼容配置进行真实模型生成和 critic | 是 | 记录精确模型和配置后可用于证据 |

## API 摘要

| 接口 | 用途 | 运行角色 |
| --- | --- | --- |
| `POST /chat` | 非流式编排回复 | 快路径完整回复 |
| `POST /chat/stream` | SSE 编排回复 | 学生端推荐路径 |
| `POST /api/safety/classifier/evaluate` | F1 本地分类器 | 默认安全门 |
| `POST /api/safety/evaluate` | LLM 安全兼容端点 | 对照和兼容 |
| `POST /api/scenario/evaluate` | F2 情境分析 | 首轮路由和二次安全 |
| `POST /api/generator/generate` | F3 候选生成模块 | 实验和调试 |
| `POST /api/critic/evaluate` | F4 pointwise critic 模块 | 模块同步端点；`/chat` 中作为后台任务使用 |
| `GET /api/critic/guidance/{session_id}` | 后台 F4 状态 | 研究和诊断 |
| `GET /api/memory/status` | F6 状态 | 默认关闭能力 |
| `DELETE /api/memory` | 删除 memory/RAG 数据 | 用户或会话数据控制 |

### 聊天请求示例

```json
{
  "session_id": "browser-session-id",
  "anonymous_user_id": "optional-stable-browser-user-id",
  "current_message": "我最近考试压力很大，晚上睡不着"
}
```

## 测试

推荐检查顺序：

```powershell
python -m pytest tests -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

## 评估与证据

根 README 应避免把历史实验输出写成当前运行保证。带时间戳的方法、指标、限制和复现命令应放在：

- [`exp/README.md`](exp/README.md)：当前算法实验和证据入口。
- [`exp/artifacts.manifest.json`](exp/artifacts.manifest.json)：实验资产的 runtime/background/offline/archive 分级清单。
- [`docs/specs/README.md`](docs/specs/README.md)：实现契约和运行边界。
- [`docs/specs/exp-integration-map.md`](docs/specs/exp-integration-map.md)：运行时、后台、离线、默认关闭能力的资产地图。
- [`docs/overview/emoedu-post-mvp-guide.md`](docs/overview/emoedu-post-mvp-guide.md)：后续验证 gate 和研究路线。

### 声明边界

- F1 本地分类器是第一层安全筛查，不是完整临床风险评估。
- F2 在首轮 LLM 介入路径上提供二次安全检查。
- F4 pointwise 输出用于后台诊断和会话指导。
- Pairwise preference、F9 reliability 和 DPO 在达到人工验证标准前保持门控。
- 历史验证摘要应标注为历史证据，而不是实时在线指标。

## 安全、隐私与数据策略

- 不提交或演示来自未成年人的真实可识别对话。
- 不暴露 API key、数据库凭据、内部 prompt 或敏感日志。
- `yellow`/`red` 安全结果会中断普通生成，并使用固定转介提示。
- 匿名连续性使用配置化标识符；存储、保留、删除和隔离行为应以当前提交代码为准。
- 公开仓库不包含完整 PsyQA-derived labelled data；本地缺失可能降低 support-card enrichment，但不应悄悄改变 API 约定。
- F6 memory/RAG prompt injection 默认关闭，直到隐私和质量 gate 通过。

## 仓库结构

```text
app/                 FastAPI 应用和运行时服务
frontend/            学生端、研究分析台和共享前端层
docs/overview/       项目缘起、路线图和规划记录
docs/specs/          F1-F4/F9 实现契约和运行边界
docs/figures/        架构图和证据链图
exp/                 离线实验、报告和本地模型/数据入口
scripts/             本地工作流使用的工具脚本
tests/               后端、编排、前端和实验冒烟测试
alembic/             数据库迁移文件
```

## 文档

推荐阅读顺序：

1. 本 README - 产品概览和复现入口。
2. [`exp/README.md`](exp/README.md) - 当前实验结论和证据。
3. [`docs/specs/README.md`](docs/specs/README.md) - 当前实现边界。
4. [`docs/specs/exp-integration-map.md`](docs/specs/exp-integration-map.md) - 资产集成地图。
5. [`docs/overview/emoedu-post-mvp-guide.md`](docs/overview/emoedu-post-mvp-guide.md) - 后续验证 gate。

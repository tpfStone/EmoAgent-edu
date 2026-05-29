# GitHub Pages Mock + 本机 Live 演示

## 定位

路线 3 把展示分成两层：

- **公开视频**：GitHub Pages 托管 `student` 和 `console` 的 mock 版，任何人可以打开看 UI 和固定样本流程。
- **真实联调**：本机运行 FastAPI、Postgres、Redis，前端用 `VITE_API_MODE=live` 请求真实 `/chat`。

GitHub Pages 不运行 FastAPI、Postgres、Redis 或 LLM 服务，因此 Pages 版不代表真实后端已上线。

## GitHub Pages Mock

Pages 发布内容由 `frontend/scripts/build-pages.mjs` 生成：

```text
frontend/dist-pages/
├─ index.html
├─ student/
└─ console/
```

构建命令：

```powershell
pnpm.cmd --dir frontend build:pages
```

该命令强制：

```env
VITE_API_MODE=mock
VITE_API_BASE=
VITE_BASE_PATH=./
```

因此发布后的页面不会请求真实 `/chat`。根目录 `index.html` 只提供两个入口：

- `./student/`
- `./console/`

GitHub Actions workflow：`.github/workflows/pages-mock.yml`。

启用方式：

1. 在 GitHub 仓库 Settings -> Pages 中选择 **GitHub Actions** 作为 source。
2. 推送到 `master` / `main`，或手动运行 `Deploy mock frontends to GitHub Pages` workflow。
3. 打开 Pages URL，进入 `/student/` 或 `/console/`。

## 本机 Live

本机 live 用来验收真实 `/chat`：

1. 准备依赖：

```powershell
python -m pip install -r requirements.txt
pnpm.cmd --dir frontend install
```

2. 准备 `.env`：

```powershell
Copy-Item .env.example .env
```

保留：

```env
LLM_PROVIDER=mock
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
REDIS_URL=redis://localhost:6379/0
```

3. 启动本机 Postgres 和 Redis，确保：

```text
Postgres: localhost:5432
Redis: localhost:6379
```

4. 执行迁移：

```powershell
python -m alembic upgrade head
```

5. 启动后端：

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

6. 验证后端：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/chat -ContentType "application/json" -Body '{"session_id":"local-live-1","current_message":"这次月考没考好，心情很差"}'
```

7. 启动 live 前端：

```powershell
$env:VITE_API_MODE="live"
pnpm.cmd --dir frontend dev:student
```

另一个终端：

```powershell
$env:VITE_API_MODE="live"
pnpm.cmd --dir frontend dev:console
```

访问：

- Student: `http://127.0.0.1:5173`
- Console: `http://127.0.0.1:5174`

Vite dev server 会把 `/chat` 代理到 `http://localhost:8000`，本机 live 不需要 CORS。

## 验收清单

- GitHub Pages 根页显示 `学生端` 和 `研究分析台` 两个入口。
- GitHub Pages student/console 可以加载资源，Network 中不出现真实 `/chat` 请求。
- 本机 live 的 student 发送普通消息后命中 `http://127.0.0.1:5173/chat`，由 Vite 转发到 FastAPI。
- 本机 live 的危机表达触发后端风险分级和转介锁。
- 本机 live 的 console 单轮追溯展示真实 `/chat` 返回的 F1-F4 字段。
- 断开后端时，student 使用安全 fallback，且不会把已知风险静默降为 `green`。

## 后续升级到路径 1

路线 3 的 Pages 构建可以复用到路径 1。升级时需要：

- 部署外部 FastAPI 后端。
- 为后端配置 Postgres、Redis、迁移和环境变量。
- 后端增加 CORS，允许 GitHub Pages origin。
- Pages 构建从 `VITE_API_MODE=mock` 改为 `VITE_API_MODE=live`，并设置 `VITE_API_BASE=https://<backend-url>`。

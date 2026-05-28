# EmoEdu F1/F4 FastAPI

面向初中生情感教育多智能体系统的独立后端原型，目前实现两个模块：

- F1 安全门：`POST /api/safety/evaluate`
- F4 EPITOME Critic：`POST /api/critic/evaluate`

当前版本不依赖同级其他项目。默认使用 `LLM_PROVIDER=mock`，测试不会调用外网。

## Quick Start

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest tests -q
uvicorn app.main:app --reload
```

启动后访问：

- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Health: http://127.0.0.1:8000/health

## Database

生产目标数据库是 PostgreSQL，配置项为：

```env
DATABASE_URL=postgresql+asyncpg://emoedu_user:password@localhost:5432/emoedu
```

迁移命令：

```powershell
alembic upgrade head
```

测试使用 SQLite in-memory，不需要本地 PostgreSQL。

## Tests

```powershell
python -m pytest tests/test_services -q
python -m pytest tests/test_handlers -q
python -m pytest tests -q
```

## Frontend

The React frontends live in `frontend/` as a pnpm workspace.

```powershell
pnpm install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

Student app: `http://localhost:5173`  
Research console: `http://localhost:5174`

GitHub Pages mock demo and local live instructions:

- `docs/frontend/github-pages-mock-local-live.md`

## Documents

- 总纲与开发框架：`docs/overview/`
- F1/F4 Codex 规格：`docs/specs/`
- 合成语料：`docs/corpus/`
- 论文配图：`docs/figures/`
- 问题记录：`docs/issues/`


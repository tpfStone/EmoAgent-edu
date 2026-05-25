# EmoEdu F1/F4 FastAPI

面向初中生情感教育多智能体系统的独立后端原型，目前实现两个模块：

- F1 安全门：`POST /api/safety/evaluate`
- F4 EPITOME Critic：`POST /api/critic/evaluate`

当前版本不依赖同级其他项目。默认使用 `LLM_PROVIDER=mock`，测试不会调用外网。

## Quick Start

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

## Documents

- 总纲与开发框架：`docs/overview/`
- F1/F4 Codex 规格：`docs/specs/`
- 合成语料：`docs/corpus/`
- 论文配图：`docs/figures/`
- 问题记录：`docs/issues/`

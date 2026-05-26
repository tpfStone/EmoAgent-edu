# EmoAgent Frontend

This workspace contains two physically separated frontends:

- `student`: public student-facing emotional companion UI.
- `console`: internal research analysis console.
- `shared`: API contracts, mock samples, and fetch wrappers.

## Safety Boundary

The student app must only import `fetchStudentChat` and render `session_id`, `reply_text`, and `risk_level`.
It must not render candidates, scores, weighted totals, failure reasons, or preference pairs.

## Commands

```powershell
pnpm install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

## API Mode

- Mock mode: default.
- Live mode: set `VITE_API_MODE=live`; Vite proxies `/chat` to `http://localhost:8000`.

## GitHub Pages Mock Demo

`pnpm --dir frontend build:pages` builds a static mock demo into `frontend/dist-pages`:

- `student/`: student UI in mock mode.
- `console/`: research console in mock mode.

This artifact is for GitHub Pages only. It does not connect to the real FastAPI backend.
Use local live mode for real `/chat` integration.

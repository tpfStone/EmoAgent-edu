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
```

## API Mode

- Mock mode: default.
- Live mode: set `VITE_API_MODE=live`; Vite proxies `/chat` to `http://localhost:8000`.

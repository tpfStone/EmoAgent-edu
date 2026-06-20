# EmoAgent Frontend

This workspace contains two physically separated frontends:

- `student`: public student-facing emotional companion UI.
- `console`: internal research analysis console.
- `shared`: API contracts, mock samples, and fetch wrappers.

## Safety Boundary

The student app may import only narrowed student-facing shared APIs: `fetchStudentChat`, `fetchStudentChatStream`, `clearAnonymousMemory`, and student-facing request/view types.
It may store `session_id` and `anonymous_user_id` for continuity, and render only the student reply/referral state derived from `reply_text` and `risk_level`.
It must not import or render candidates, scores, weighted totals, trace fields, failure reasons, or preference pairs.

## Commands

Run these from the repository root:

```powershell
pnpm --dir frontend install
pnpm --dir frontend dev:student
pnpm --dir frontend dev:console
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

## API Mode

- Mock mode: default.
- Live mode: set `VITE_API_MODE=live`; Vite proxies `/chat` and `/api/*` to `http://localhost:8000`.
- If you bypass the Vite dev server, set `VITE_API_BASE=http://localhost:8000` so `/api/memory` and `/api/critic/guidance/{session_id}` call the FastAPI backend directly.
- Local live mode expects FastAPI on `127.0.0.1:8000` and Redis on `localhost:6379`. If Redis is unavailable, the backend keeps the student chat usable as a no-history single-turn reply, but multi-turn history and background F4 guidance are disabled.
- The student app opens a fresh empty session on each startup. Browser-local sessions with messages stay in the sidebar so old runs can be reviewed without becoming the active acceptance session.

## Motion Contract

- Student and console apps each own their transition components; nothing visual is shared through `shared`.
- Module switches use CSS Modules plus small React state machines, not a heavy animation runtime.
- Motion is limited to `opacity` and `transform` except tightly scoped composer/referral replacement.
- `prefers-reduced-motion: reduce` must be respected.
- Do not use browser auto-scroll helpers; message lists use container `scrollTop`.

## GitHub Pages Mock Demo

`pnpm --dir frontend build:pages` builds a static mock demo into `frontend/dist-pages`:

- `student/`: student UI in mock mode.
- `console/`: research console in mock mode.

This artifact is for GitHub Pages only. It does not connect to the real FastAPI backend.
Use local live mode for real `/chat` integration.

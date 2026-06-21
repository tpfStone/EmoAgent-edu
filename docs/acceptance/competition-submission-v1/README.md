# Competition Submission v1 Acceptance Record

Date: 2026-06-21
Product name: EmoAgent
Repository: https://github.com/tpfStone/EmoAgent-edu
Target tag: `competition-submission-v1`

## Scope

This record tracks the final competition submission boundary for the current
runtime:

- F1 safety gate with separate `risk_level` and `safety_status`.
- F2 scenario routing with secondary safety unavailable fallback.
- F3 single routed student-facing generation.
- F4 background critic guidance with tracked background tasks.

## Verification Commands

```powershell
$env:PYTHONPATH='.'
pytest tests -q
pytest tests/test_exp/test_exp_smoke.py -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend build:pages
```

## Verification Results

Last local verification: 2026-06-21

| Command | Result |
| --- | --- |
| `PYTHONPATH=. pytest tests -q` | PASS: 214 passed, 1 warning (`jieba` / `pkg_resources` deprecation) |
| `PYTHONPATH=. pytest tests/test_exp/test_exp_smoke.py -q` | PASS: 4 passed |
| `pnpm --dir frontend test` | PASS: shared 8 tests, console 8 tests, student 14 tests |
| `pnpm --dir frontend typecheck` | PASS |
| `pnpm --dir frontend build` | PASS |
| `pnpm --dir frontend build:pages` | PASS |

The commands above mirror the checks in `.github/workflows/ci.yml` for the
backend and frontend jobs.

## CI Status

- Local CI-equivalent verification: PASS on 2026-06-21.
- GitHub Actions CI: PASS on 2026-06-21 for run
  `CI #2 / docs: finalize competition submission record`.
- CI run URL:
  <https://github.com/tpfStone/EmoAgent-edu/actions/runs/27904174192>
- CI commit: `e146527d8add62a2f127f08d22402ef8babec285`
- CI jobs:
  - `backend`: PASS, 2m04s.
  - `frontend`: PASS, 42s.
- CI notes: GitHub reported Node.js 20 deprecation annotations from upstream
  Actions, but the workflow conclusion was success.
- GitHub Release note status: not created from this environment because `gh` is
  not authenticated. If a GitHub Release is created later, copy the final tag
  target and CI result from this record.

## Finalization

The immutable submission tag was published after the verification commands above
passed locally and GitHub Actions CI passed remotely.

Final submission tag:

- Tag: `competition-submission-v1`
- Tag type: annotated
- Final tag target commit: `e146527d8add62a2f127f08d22402ef8babec285`
- Final tag target subject: `docs: finalize competition submission record`

```powershell
git rev-parse competition-submission-v1^{}
git show --no-patch --format=fuller competition-submission-v1
```

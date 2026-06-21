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

## Finalization

Create the immutable submission tag only after the final commit is made and the
verification commands above pass on that commit:

```powershell
git tag -a competition-submission-v1 -m "Competition submission v1"
```

Record the final commit hash and verification output here before publishing the
submission package.

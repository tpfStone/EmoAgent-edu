# F9 Reliability Summary

Metric: quadratically weighted Cohen's κ.

| dimension | n | A vs B κ | consensus vs F4 κ | threshold | pass | F4 distribution |
|---|---:|---:|---:|---:|---|---|
| ER | 40 | 0.041 | 0.000 | 0.400 | no | `{"0": 0, "1": 0, "2": 40}` |
| IP | 40 | -0.032 | 0.000 | 0.400 | no | `{"0": 0, "1": 0, "2": 40}` |
| EX | 40 | 0.477 | 0.199 | 0.600 | no | `{"0": 22, "1": 12, "2": 6}` |

Thresholds: EX >= 0.600; ER/IP >= 0.400.
Human-vs-F4 uses half-up rounded A/B consensus scores.

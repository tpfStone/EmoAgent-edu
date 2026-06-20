# F3 Flash/Pro Sidecar

> **F9 当前边界**：本文件属于 F9、pointwise 或 pairwise 历史实验记录。Pointwise ER/IP/EX 仅作诊断和历史兼容；正式 DPO 与 runtime selector 仍依赖 pairwise/human A/B gate，Phase A rerun 当前为 `inconclusive`。

- purpose: compare F3 candidate quality only; not mixed into Phase A rerun metrics
- compared_pairs: 6
- sample_nos: 6, 7, 2, 3, 1, 11
- flash_model: deepseek-v4-flash disabled
- pro_model: deepseek-v4-pro enabled
- comparison_csv: `docs\corpus\f9\pairwise-selection-pilot\reports\f3-model-sidecar\f3_flash_pro_sidecar_comparison.csv`
- flash_pairs: `docs\corpus\f9\pairwise-selection-pilot\runs\f3-model-sidecar\flash\inputs\phase-a-rerun\f9_pairwise_rerun_pairs.csv`
- pro_pairs: `docs\corpus\f9\pairwise-selection-pilot\runs\f3-model-sidecar\pro\inputs\phase-a-rerun\f9_pairwise_rerun_pairs.csv`

Manual decision field in CSV:
- `flash`: flash candidates are good enough or better
- `pro`: pro candidates are clearly better
- `tie`: no meaningful quality difference

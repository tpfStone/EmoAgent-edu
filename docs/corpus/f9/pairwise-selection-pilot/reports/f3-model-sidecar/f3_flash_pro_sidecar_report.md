# F3 Flash/Pro Sidecar

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

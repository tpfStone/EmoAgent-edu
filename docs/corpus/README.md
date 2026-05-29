# Corpus 文档总览

本目录只保存语料说明、语料样本、F9 实验资产和离线评估产物。代码入口仍在 `scripts/corpus/`，系统规格仍在 `docs/specs/`；这里不作为运行脚本或产品规格的唯一来源。

## 顶层文件

| 路径 | 状态 | 用途 |
|---|---|---|
| `emoedu-corpus-synthesis.md` | 根语料说明 | EmoEdu 合成语料的构造口径、样本结构和使用说明。 |
| `emoedu-corpus-45-samples.json` | 根语料数据 | 45 条语料样本，供生成、评测或文档引用。 |
| `generation_config.json` | 生成配置 | 根语料生成配置，不等同于 F9 validation run 配置。 |
| `production_quota_after_probe_001.json` | 运行记录 | production quota probe 后的记录快照，作为诊断资料保留。 |
| `f9/` | F9 实验资产 | F9 人工信度、pointwise 诊断、validation/stability、pairwise pilot 和模型评测产物。 |

## 边界

- 根语料文件描述“要评估什么样的学生表达与候选回复”。
- `f9/` 描述“如何用 F9 验收 F3/F4，以及当前为什么还不能进入正式人工 F9 或 DPO”。
- `f9/validation*`、`f9/pairwise-selection-pilot/runs`、`f9/validation-stability/model-eval` 是 run/评估产物目录。CSV/JSON 是事实产物，整理文档时不要改动其数据内容。
- 计划和复盘文档统一放在 `f9/plans/` 与 `f9/pointwise-diagnostics/`，避免把 F3/F4/F9 历史计划继续堆在 `f9/` 根部。

## 推荐入口

1. 根语料：先读 `emoedu-corpus-synthesis.md`，再看 `emoedu-corpus-45-samples.json`。
2. F9 当前状态：读 `f9/README.md`。
3. Pointwise 历史计划：读 `f9/plans/README.md` 和 `f9/pointwise-diagnostics/README.md`。
4. Pairwise pilot：读 `f9/pairwise-selection-pilot/README.md`。

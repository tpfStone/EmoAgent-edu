# EmoEdu Exp 实验总览

[English](README_EN.md)

exp目录保存 EmoEdu 在算法侧的主要实验链路，包括 PsyQA 标注数据处理、F1 安全门、F3 双取向生成、F4 critic 评估，以及这些实验如何为生产链路提供可行方案并保留可复现的研究轨迹。

## 当前结论

在线交互链路应保持轻量：首次对话走 `F1 -> F2 -> F3 -> 流式返回`，F4 critic 放到后台异步执行。后续轮次仍先过 F1 安全门，再走轻量 CBT 支持，并在后台 F4 指导已经完成时把建议注入生成 prompt。这样既保留多智能体研究链路的理论支撑，也避免把产品交互拖到不可用。

F1 安全门已经迁入生产侧，使用本地分类器而不是 LLM prompt。当前策略是 BERT 文本特征加人工审查关键词特征，再用 soft rule 和阈值做保守判定。生产侧应在应用启动时预加载 BERT、分类头、scaler 和关键词表，不要每次请求重新加载。

F3 已经验证 PsyQA 标注数据可以作为策略先验和 support card。`c1 共情型` 和 `c2 引导反思型` 的方向在小样本和扩展样本中都能被区分，但完整双候选加 critic 的在线耗时过高，因此生产侧采用“先判断用户支持模式，再生成单候选”的方式。公开仓库不包含完整 `data/psyqa_labelled.json`；缺失时 support-card enrichment 为空或退回通用策略，不改变运行时代码路径。

F4 critic 当前更适合后台质量评估、session guidance 和后续 DPO 候选数据构造，不适合在线强阻塞。模型 judge 在合成控制样本上表现较稳，但 Phase A rerun 仍为 `inconclusive`，且 stable winner 出现 `c1` 偏斜；当前 pairwise 结果不能进入 runtime，也不能直接作为 DPO 训练依据。

## 目录结构

| 路径 | 内容 | 保留原因 |
| --- | --- | --- |
| `data/README.md` | 公开数据边界和本地复现说明 | 完整 PsyQA-derived labelled data 不随公开仓库发布 |
| `data/psyqa_labelled.json` | 已去重整合的 PsyQA 标注数据；本地复现者自行放置 | 后续 F1/F3/F4 的共同数据基础；不提交 GitHub |
| `models/f1_safety_gate/manual-A-pattern-v1/` | F1 安全门模型、scaler、关键词表和指标 | 已迁入生产链路的模型产物；本地从 HuggingFace 下载，不提交 GitHub |
| `runs/` | 每次实验的不可变输出 | 用于本地复现、追踪参数和写论文/报告；原始 run 产物体积较大，默认不提交 GitHub |
| `*.py` | 独立实验脚本 | 每个脚本对应一个实验阶段或评估任务 |

已清理内容：`exp/__pycache__` 属于 Python 运行缓存，已删除；`psyqa_strategy_visual_report.py` 中一个未使用的文本截断函数和未使用 import 已删除。历史 run 数据暂不删除，因为它们承担实验审计和结果追溯作用。

## 公开数据边界

完整 PsyQA-derived labelled data 不随仓库发布，也不提交 sample JSON 导出。需要完整复现时，请把文件本地放到：

```text
exp/data/psyqa_labelled.json
```

文件缺失时，`F3SupportService` 会读到空数据。系统仍可启动和运行默认测试；变化仅限于 F3 strategy priors/support cards 为空或通用化，真实交互质量可能少一些可检索参考，但不是代码路径、API 或设计目标的退化。

## 数据链路

原始 PsyQA 数据先经过 `psyqa_labelled.py` 调用 DashScope/DeepSeek 兼容接口做结构化标注；完整复现者需要在本地生成或补齐 `exp/data/psyqa_labelled.json`。结构化标注输出字段包括：

| 字段 | 用途 |
| --- | --- |
| `use_tier` | 决定样本进入样例库、策略参考、负例还是丢弃 |
| `scenario` | 学业压力、同伴关系、亲子摩擦、其他 |
| `age_stage` | 初中、高中、大学、成人、不明 |
| `minor_suitability` | 是否适合初中生情感教育使用 |
| `safety_level` | green、yellow、red、reject |
| `psyqa_strategy_sequence` | 从原回答中解析的 PsyQA 支持策略序列 |
| `psyqa_strategy_segments` | 策略片段，用于分析回应结构 |
| `quality_label` | good、rewrite、reject |
| `reject_reasons` | 太成人化、过长、说教、诊断、私聊、药物等 |

随后使用 `psyqa_strategy_visual_report.py` 生成策略分布报告。当前主结果来自：

`runs/psyqa_strategy_report/psyqa-strategy-report-20260531/`

关键统计如下：

| 指标 | 结果 |
| --- | --- |
| 总样本 | 4012 |
| `direct_exemplar` | 150 |
| `strategy_reference` | 1336 |
| `negative_example` | 724 |
| `reject` | 1802 |
| 初中样本 | 448 |
| 适合未成年人样本 | 201 |
| `green/yellow/red/reject` | 2289 / 780 / 395 / 548 |
| `direct_exemplar` 场景分布 | 学业压力 40，同伴关系 77，亲子摩擦 21，其他 12 |
| 高频策略 | Interpretation、Direct Guidance、Restatement、Approval and Reassurance |

数据结论：PsyQA 可用，但直接适合初中生教育情境的优质样例较少；大量样本偏成人、过长、说教或不适合未成年人。因此 PsyQA 更适合作为策略先验、support card、critic 负例和偏好数据来源，而不是直接作为线上 RAG 大规模原文库。

## F1 安全门

F1 的目标是在不调用 LLM 的情况下，根据用户原始输入给出 `green/yellow/red` 风险概率，并用 `p_red` 与 `p_yellow + p_red` 做保守判定。

主要实验顺序：

| 脚本 | 作用 | 主要输出 |
| --- | --- | --- |
| `f1_keyword_weight_probe.py` | 比较关键词构造策略、字段权重和关键词长度 | `runs/f1_keyword_weight_probe/` |
| `f1_train_manual_keywords.py` | 使用人工审查后的关键词训练最终 F1 分类器 | `runs/f1_manual_keyword_safety_gate/` 和 `models/f1_safety_gate/` |
| `f1_safety_policy_experiment.py` | 搜索 soft rule、类别权重、temperature 和阈值 | `runs/f1_safety_policy_experiment/` |
| `f1_safety_inference_benchmark.py` | 测试本地推理延迟 | `models/f1_safety_gate/.../inference_benchmark.json` |
| `f1_safety_gate_experiment.py` | 早期关键词+BERT 混合实验，同时提供共享工具类 | 被其它 F1 脚本复用 |

最终模型目录：

`models/f1_safety_gate/manual-A-pattern-v1/`

模型产物已发布到 HuggingFace，研究人员可用以下命令恢复本地模型目录：

```powershell
hf auth login

hf download Nacgisac/EmoEduF1-bert-base-chinese `
  --include "manual-A-pattern-v1/*" `
  --local-dir exp/models/f1_safety_gate `
  --revision main
```

远端目录：

```text
https://huggingface.co/Nacgisac/EmoEduF1-bert-base-chinese/tree/main/manual-A-pattern-v1
```

主要训练结果：

| 指标 | 测试集结果 |
| --- | --- |
| accuracy | 0.7058 |
| balanced accuracy | 0.5844 |
| macro F1 | 0.5800 |
| weighted F1 | 0.7088 |
| green F1 | 0.8441 |
| yellow F1 | 0.4370 |
| red F1 | 0.4590 |

混淆矩阵显示 green 较稳，yellow/red 难度高。red 样本只有 395 条，类别不平衡明显；BERT 最大长度 192 时约 40% 样本被截断。当前工程策略不是追求 argmax 准确率，而是用概率和阈值做安全优先的保守判断。

推理性能：

| 指标 | 结果 |
| --- | --- |
| 模型加载 | 约 11.1 秒 |
| 单条推理平均延迟 | 约 12.4 ms |
| p95 延迟 | 约 16.8 ms |

生产结论：F1 必须在 FastAPI lifespan 中预加载；运行时只做 tokenizer、BERT forward、关键词特征、分类头和阈值判断。

## F3 生成器

F3 的目标是把用户输入、F2 场景/支持模式、PsyQA 策略先验和 support card 合并成结构化 prompt，生成简短、有温度、不显性说 CBT 的回应。

当前有两个方向：

| 方向 | 目标 |
| --- | --- |
| `c1 共情型` | 更强 ER，适合强情绪、需要被接住的首轮对话 |
| `c2 引导反思型` | 更强 IP，适合明确求助、需要低压可执行起点的情况 |

主要实验顺序：

| 脚本 | 作用 | 主要输出 |
| --- | --- | --- |
| `f3_orientation_probe.py` | 初步验证不同模型是否能生成 c1/c2 双取向候选 | `runs/f3_orientation_probe/` |
| `f3_support_probe.py` | 验证 PsyQA support card + 策略先验是否提升生成质量 | `runs/f3_support_probe/` |
| `f3_route_f4_probe.py` | 验证 F2 路由、F3 候选生成、F4 过滤和人工检查模板 | `runs/f3_route_f4_probe/` |

关键结果：

| 实验 | 结果 |
| --- | --- |
| 四模型 c1/c2 小样本 | qwen3.5-plus、qwen3.6/3.7 系列均能基本区分 ER/IP 方向 |
| qwen3.7-plus support 15 样本 | `c1_ER_higher=1.0`，`c2_IP_higher=1.0`，无过早建议，无 support card 照抄 |
| route + F4 9 样本 | 支持模式匹配率 0.8889，首轮无反问率 1.0，候选最终 c1/c2 分布 5/4 |

重要问题：完整双候选生成加 critic 平均耗时过高，`f3_support_probe` 约 56.8 秒，`f3_route_f4_probe` 约 83.7 秒。因此生产链路不再在线生成双候选，而是让 F2 给出 `support_mode`，F3 按一个方向生成单候选，并流式返回。

## F4 Critic

F4 的目标不是替代人工，而是给候选回答做结构化质量判断，主要用于后台质量标签、session guidance、聚合报告和后续 DPO 数据。

F4 判断重点包括：

| 维度 | 说明 |
| --- | --- |
| ER/IP/EX | 情绪反应、解释澄清、探索引导是否适度 |
| 认知澄清 | 是否有适度澄清，但不过早下结论 |
| 过早建议 | 是否在未接住情绪前直接给方案 |
| 边界风险 | 是否诊断、承诺治疗、制造依赖、私聊导流 |
| 首轮体验 | 是否少反问、少模板、简短清晰 |

主要实验顺序：

| 脚本 | 作用 | 主要输出 |
| --- | --- | --- |
| `f4_eval_package_builder.py` | 构造匿名 A/B pair，包括优质对照、负例、边界问题和 tie control | `runs/f4_eval_package/` |
| `f4_pairwise_model_runner.py` | 用多个模型对 blind pairs 做正反顺序判断 | `runs/f4_pairwise_model_probe/` |
| `f4_human_model_agreement.py` | 比较人工偏好和模型 judge 的一致性 | `runs/f4_pairwise_model_probe/.../human_model_agreement_summary.json` |

样本包：

`runs/f4_eval_package/f4-pairwise-package-20260603/`

| 指标 | 结果 |
| --- | --- |
| pair 总数 | 60 |
| pair 类型 | clean orientation、negative vs clean、boundary vs clean、tie duplicate |
| 场景分布 | 学业、同伴、亲子各 20 |
| 需要人工判断 | 15 |

模型对照结果显示，模型 judge 在预设 winner 的合成样本上准确率较高，但和人工偏好的 agreement 不够稳定。人工标注 15 对样本中，`kimi-k2.6` agreement 相对较好，但整体仍不足以直接作为权威偏好模型。

生产结论：F4 放后台。首次回复完成后异步运行 F4，写入质量标签和 session guidance；下一轮如果 guidance 已生成，再注入 F3 或轻量 CBT prompt。若用户交互太快，下一轮可以不等待 F4。

## 当前生产链路

推荐运行路径：

```text
首次对话：
F1 本地安全门
-> F2 LLM 场景/支持模式/风险兜底
-> F3 单候选生成并流式返回
-> 后台 F4 critic

后续对话：
F1 本地安全门
-> 轻量 CBT 生成
-> 注入最近对话上下文
-> 如果后台 F4 guidance 已完成，则注入 guidance
-> 流式返回
```

这样保留论文中 generator-critic、多智能体和离线优化的思想，但把用户等待时间控制在可接受范围内。

## 复现顺序

下面命令默认在 EmoAgent-edu 项目根目录运行。先安装主依赖和实验依赖：

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-exp.txt
```

默认自动测试只检查 `exp/*.py` 的语法和 `__main__` 入口结构：

```powershell
python -m pytest tests/test_exp/test_exp_smoke.py -q
```

完整实验运行还需要 `.env`、模型文件、API key、本地 `exp/data/psyqa_labelled.json`，以及本地 `exp/runs/` 历史产物。调用 DashScope 的脚本需要配置 `DASHSCOPE_API_KEY`。

生成 PsyQA 标注：

```powershell
python exp/psyqa_labelled.py --provider dashscope --model qwen3.7-plus --resume
```

生成 PsyQA 策略统计报告：

```powershell
python exp/psyqa_strategy_visual_report.py --run-id psyqa-strategy-report-YYYYMMDD
```

搜索关键词构造策略：

```powershell
python exp/f1_keyword_weight_probe.py --run-id keyword-probe-YYYYMMDD
```

训练最终 F1：

```powershell
python exp/f1_train_manual_keywords.py --run-id manual-A-pattern-YYYYMMDD
```

搜索 F1 阈值与 soft rule：

```powershell
python exp/f1_safety_policy_experiment.py --run-id policy-grid-YYYYMMDD
```

测试 F1 推理延迟：

```powershell
python exp/f1_safety_inference_benchmark.py --model-dir exp/models/f1_safety_gate/manual-A-pattern-v1
```

验证 F3 support card：

```powershell
python exp/f3_support_probe.py --model qwen3.7-plus --per-scenario 5 --run-id f3-support-YYYYMMDD
```

构造 F4 pairwise 样本包：

```powershell
python exp/f4_eval_package_builder.py
```

运行 F4 模型 judge：

```powershell
python exp/f4_pairwise_model_runner.py --models qwen3.7-plus,kimi-k2.6
```

统计人工和模型一致性：

```powershell
python exp/f4_human_model_agreement.py
```

## 实验问题记录

PsyQA 数据偏成人和咨询问答风格。直接适合初中情感教育的样本只有一小部分，因此不能简单把 PsyQA 原回答全部作为线上检索库。当前解决方式是用 `use_tier` 分层：`direct_exemplar` 进入 support card，`strategy_reference` 用于策略统计，`negative_example` 用于 critic，`reject` 不进入训练和检索。

关键词构造早期存在噪声。`rationale` 最后一句常出现“完全不适合初中生情感教育场景”这类模板句，和真实风险语义无关。后续改为过滤模板句，并由人工审查 A 策略关键词表，再用于 F1 模型。

F1 存在类别不平衡。green 多，red 少，yellow/red 的边界本来就模糊。当前采用类别权重、人工关键词特征、temperature/阈值和 soft rule，但仍应把它视作第一道安全筛，不应让它承担唯一安全责任。

F2 需要承担兜底风险识别。即使 F1 漏判，F2 schema 仍要输出风险兜底字段；如果 F2 发现明显危机或不适合继续普通教育支持，应直接转介或进入安全回复。

F3 双候选生成质量较好但太慢。实验链路可以保留双候选和 critic，产品链路应改为 F2 路由后单候选生成。

F4 模型 judge 有理论价值但不能完全代替人工。它适合做后台质量标签、prompt 迭代、DPO 候选数据生成；如果要用于正式 DPO，仍需要人工校准样本和更高一致性的 judge 标准。

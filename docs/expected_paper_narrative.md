# 为什么结构简单的 Bug 困住 AI Agent？
## 基于当前 HEAD20 证据的 HEAD Bug 实证研究

**Date:** 2026-03 (v15, latest-only narrative)  
**基于:** `docs/bug_annotations_v2.json`（human-easy 标注）、`report/merged_5seed_act_only_baseline.json`（两层分类）、`docs/report/head_20_from_existing.json`（HEAD20 轨迹聚合与 hint study）、`docs/report/head_20_mistral_matched_protocol_strategy.json`（当前 Mistral HEAD20 协议×策略排序）以及 `docs/report/reflexion_mechanism_ablation_head20.json`（Reflexion 机制检验）。

> **核心问题：** 存在一类对人类简单、对 AI 困难的 bug——我们称之为 **HEAD (Human-Easy but AI-Difficult)**。在新的**两层分类**下，第一层区分 **human-easy (44)** 与 **human-difficult (46)**；第二层只在 `human-easy` 内再分出 **Easy (16)**、**Intermediate (8)**、**HEAD (20)**。**为什么 HEAD 会成为 human-easy 内部最反常、最稳定困住 agent 的那一支？**

---

## 研究流程

```
1. 两层分类 → 界定 `human-easy / human-difficult` 与 `Easy / Intermediate / HEAD`
   ↓
2. 根因分析：bug 特征 + agent 行为 + 协议-难度交互
   ↓
3. 因果验证：hint study 确认"双维度困难"
   ↓
4. 策略探索：matched rerun 与 mechanism ablation → 发现干预非线性交互
   ↓
5. 结论与实践指导
```

**论文主线：** 在两层分类下，HEAD 是 `human-easy` 内部最反常的左尾。当前 HEAD20 证据显示，真正决定弱模型成败的不是“换到哪个更聪明的协议”，而是**是否能缩短错误轨迹的持续时间**；最优配置取决于 `(协议 × 策略 × HEAD 子型)` 的组合。

---

## 第一步：初始实验

### 当前证据设计

| 维度 | 设定 |
|------|------|
| **数据集** | QuixBugs (40) + Mini-nightmare (10) + DebugBench (40) = **90 tasks** |
| **模型** | 120B (api-gpt-oss-120b, strong) + Mistral Small (api-mistral-small-3.2-2506, weak) |
| **Protocol** | act_only, react, reflexion |
| **Strategy** | baseline, checklist, early_stop_restart, self_consistency |
| **分类基线** | `human-easy / human-difficult` 标注 + Mistral act_only 5-seed |
| **HEAD20 hint study** | 全 20 覆盖：Mistral `L0/L2/L4`，120B `L0/L2` |
| **Matched rerun** | Mistral HEAD20 `3 protocols × 4 strategies = 240 runs` |
| **Mechanism ablation** | Reflexion / ReAct 相关对照 = `80 runs` |

### 两层分类：先分 human difficulty，再分 AI difficulty

采用**二元人工标注**（`docs/bug_annotations_v2.json`）：

> **human-easy：** 有经验的程序员仅凭代码与测试输出即可识别常见错误模式并修复，无需深入理解算法或复杂推理。  
> **human-difficult：** 需理解算法、追踪复杂逻辑、领域知识或并发/多错误交互。

结果：**44 个 human-easy，46 个 human-difficult**。

### `human-easy` 内部的第二层划分（稳健定义）

为降低单次 run 与 API 漂移的影响，采用 **Mistral act_only 五 seed（42,43,44,45,46）** 的通过率定义难度：

- **Easy**：`human-easy` 且 Mistral 5-seed 通过率 **≥ 60%**（至少 3/5 通过）→ **16 bugs**
- **Intermediate**：`human-easy` 且 Mistral 5-seed 通过率 **= 40%**（2/5 通过）→ **8 bugs**
- **HEAD**：`human-easy` 且 Mistral 5-seed 通过率 **≤ 20%**（最多 1/5 通过）→ **20 bugs**

> **为什么以 act_only 为分类基线：** act_only 无推理、无反思，最接近模型“裸”调试能力；HEAD 的识别基于弱模型在该基线下的稳定失败（多 seed），使“协议/策略是否能恢复能力”成为可检验的干预。

**两层分类概览：**

| 层级 | 类别 | 数量 | 定义 |
|------|------|:----:|------|
| 第一层 | **human-easy** | 44 | 人类可直接凭代码与测试修复 |
| 第一层 | **human-difficult** | 46 | 需更深算法/逻辑/领域推理 |
| 第二层（仅在 human-easy 内） | **Easy** | 16 | Mistral act_only 五 seed 至少 3/5 通过 |
| 第二层（仅在 human-easy 内） | **Intermediate** | 8 | Mistral act_only 五 seed 恰好 2/5 通过 |
| 第二层（仅在 human-easy 内） | **HEAD** | 20 | Mistral act_only 五 seed 至多 1/5 通过 |

> **解释：** `Intermediate` 不是“比 HEAD 更难”的类别，而是 `human-easy` 内部的过渡带。真正的论文对照关系应是：`HEAD` 相对于同样 `human-easy` 的 `Easy / Intermediate` 有何异常，而不是把它与一个混合了 `human-difficult` 的“Hard 桶”并列。

完整 bug 列表可由 `docs/bug_annotations_v2.json` 与 `report/merged_5seed_act_only_baseline.json` 交叉得到。

**成本签名（HEAD）：** 在 HEAD 上，120B 仍可多数修好但成本较高（新 20 上 act_only 约 75% pass，~30K tokens）；Mistral 在 act_only 下仅约 20%（单 seed）且 5-seed 下多数为 0/5 或 1/5——**结构简单却对弱模型稳定困难**。

#### Bug 类型与 HEAD（新 20 的构成）

新 20 HEAD 中：QuixBugs 9、DebugBench 7、Mini-nightmare 4。算法题（QuixBugs）与需系统性探索的任务（部分 Mini-nightmare/DebugBench）在 human-easy 且 Mistral 多 seed 稳定失败时更易落入 HEAD。错误信号越间接，越依赖“修复生成”而非单纯定位，与根因分析中的双维度困难一致。

---

## 第二步：为什么 HEAD 困住 AI Agent？

> HEAD bug 结构简单，人类能轻松修复，但 AI agent 要么代价极高，要么彻底失败。下面从协议-难度交互、agent 行为、Reflexion 机制和因果实验四个维度分析根因。

### 2a. 协议-难度交互（Protocol-Difficulty Interaction）

#### 当前 HEAD20 协议证据：Mistral matched rerun

| Protocol | Strategy | Pass Rate | Avg Tokens |
|----------|----------|:---------:|:----------:|
| **react** | **early_stop_restart** | **45%** | ~36.8K |
| **reflexion** | **self_consistency** | **45%** | ~37.3K |
| reflexion | early_stop_restart | 40% | ~39.1K |
| react | self_consistency | 40% | ~42.3K |
| act_only | checklist | 35% | ~38.8K |
| react | baseline | 35% | ~39.1K |
| act_only | early_stop_restart | 35% | ~41.8K |
| reflexion | baseline | 30% | ~39.6K |

**这批 matched 结果给出的当前结论是：** 对 Mistral，HEAD 上最可靠的收益不来自 plain protocol switch，而来自**预算重分配 / 多次尝试**的策略层干预。

> **当前观察到的规律：** 当 act_only 不足（尤其是 HEAD）时，单纯切换到更“重”的协议有时有帮助，但**稳定收益更常来自协议与多尝试策略的联动**；在 Easy 上 act_only 已足够时，额外推理往往只是开销。协议效果取决于 (模型能力 × 任务难度 × 是否能切断错误轨迹)。

> **两层分类下的关键梯度：**
> - 在 `human-easy/Easy` 上，Mistral `act_only = 87.5% (14/16)`，说明这部分 bug 对弱模型也基本是“正常简单”。
> - 在 `human-easy/Intermediate` 上，Mistral `act_only = 25.0% (2/8)`、`reflexion = 50.0% (4/8)`，协议开始真正重要。
> - 到 `HEAD`，当前 matched rerun 表明 `act_only baseline` 明显不足，且这 20 个任务对过程控制非常敏感。
>
> 这说明 `HEAD` 不是“广义 hard”中的一部分，而是 `human-easy` 内部的**极端左尾**：同样对人简单，但弱模型稳定掉队。

#### 机制：推理质量 × 任务需求决定协议效果

> - **模型能力 > 任务需求（human-easy / Easy）：** act_only 已足够，额外推理通常只是预算开销；对 Mistral 而言，`react` 甚至从 `87.5%` 降到 `75.0%`。
> - **模型能力接近任务需求（human-easy / Intermediate）：** 协议开始真正重要；Mistral 从 `act_only 25.0%` 提升到 `reflexion 50.0%`。
> - **模型能力明显不足（HEAD）：** act_only 不足，但不是所有协议切换都稳定有效；当前 matched rerun 里真正占优的是 `react/reflexion` 上的**重启或多尝试策略**，不是 plain reflexion baseline。
> - **human-difficult 是另一条轴：** 它表示人类也需要更深推理，因此不应与 `HEAD` 混成同一个“hard bucket”。
>
> *因此，协议效果并不沿着“越难越需要更多推理”单调变化；真正决定协议收益的，是 bug 在两层分类中的位置，以及该协议生成的推理质量。*

#### 当前最稳的协议结论是什么？

> **当前最稳的协议结论不是 “react 更差”，也不是 “reflexion 更强”，而是 plain protocol switch 本身不够。** 在这次 matched 12-condition rerun 中，Mistral 的三个 baseline 仅为：`act_only = 25%`、`react = 35%`、`reflexion = 30%`。真正排到前面的条件是 `react + early_stop_restart = 45%` 与 `reflexion + self_consistency = 45%`。
>
> **这说明什么？** HEAD 上目前最稳定的收益来源更像是**把预算分成多个更短、更独立的尝试**，而不是仅仅给 agent 增加一层 `Think → Act` 或 `Reflexion` 框架。
>
> **据此可得：** HEAD 对弱模型的挑战首先表现为 `act_only baseline` 明显不足；其次，收益最大的不是“换协议”，而是**协议 × 策略**的联合作用，尤其是能限制单次错误轨迹持续时间的策略。

### 2b. Agent 行为分析：agent 在 HEAD 上做错了什么？

#### 自动化轨迹分析（基础指标）

> *以下为**新 20 HEAD** 轨迹统计，来自 `scripts/head_20_data_from_existing.py` → `docs/report/head_20_from_existing.json`。这一节刻意聚焦 HEAD 本身。需要注意：这里的 `act_only` 轨迹统计来自当前 HEAD20 act_only 聚合，而 `§2a/§3` 的 `25%` 来自 matched rerun baseline；两者用途不同，本节只用于描述轨迹模式。*

| 指标 | 120B HEAD (20) | Mistral HEAD (20) |
|------|:--------------:|:-----------------:|
| Avg edits | 2.9 | **5.4** |
| Avg tests | 2.5 | 3.4 |
| Avg views | 3.5 | 3.1 |
| 1st Edit turn | 5.3 | 5.2 |
| 1st Fix turn | 8.7 | 8.2 |

> *注：这里的 Mistral HEAD act_only 通过率写作 `20%`，因为它对应的是当前 HEAD20 act_only 聚合；`§2a` 的 matched rerun baseline 为 `25%`。`1st Fix` 是成功 run 的平均值。作为两层分类中的对照，Mistral 在 `human-easy/Easy` 上 act_only 已达 `87.5%`，平均 token 仅 `18.1K`，而 HEAD 是 `47.1K`。*

#### Token 消耗曲线

**问题：HEAD 上的 token 消耗是均匀增长还是后期爆炸？**

**关键发现：**
- **Token per turn 线性增长**（每 turn 的 context 累积），不是后期爆炸。HEAD 之所以贵，是因为**run 持续更多 turn**。
- **120B HEAD 20** 上 act_only 75% pass、~30K tokens；大部分成功 run 在有限 turn 内收敛。
- **Mistral HEAD 20** 上 act_only 仅 20%，失败 run 多跑近 budget ceiling（~47K tokens），呈"均匀耗尽"型。
- 在 `human-easy/Easy` 上，两模型 act_only 只需约 `16–18K` tokens 就能稳定收敛；HEAD 的差异首先体现为**持续时间**而不是单步复杂度。

> **洞察：HEAD 成本异常的本质是 "持续时间" 异常——agent 每 turn 的成本是相似的（线性增长），但 HEAD 需要更多 turn 才能（或者永远无法）收敛。**

#### 定位 → 修复差距

**问题：HEAD 的困难在于定位 bug 还是修复 bug？**

> *下表为**新 20 HEAD** 的 Edit→Fix 统计（来自 `docs/report/head_20_from_existing.json`）。和上面的基础指标一样，这里用于描述修复阶段的行为模式，不用于给 protocol 做 matched 排序。*

| Model | Protocol | 1st Edit | 1st Fix | **Edit→Fix Gap** |
|-------|----------|:--------:|:-------:|:----------------:|
| 120B | act_only | 5.3 | 8.7 | **+3.6** |
| 120B | react | 5.5 | 9.1 | **+3.9** |
| 120B | reflexion | 5.5 | 9.7 | **+4.0** |
| Mistral | act_only | 5.2 | 8.2 | +3.0 |
| Mistral | react | 5.3 | 8.0 | —（仅 1 通过） |
| Mistral | reflexion | 5.0 | 8.2 | **+2.4** |

**关键发现：**
- **编辑开始得并不晚：** 两模型都在大约 `turn 5` 开始编辑。HEAD 的问题不是“迟迟不知道该动哪儿”，而是**开始动手后仍很难收敛到正确补丁**。
- **修复阶段拖得更久：** 即使是强模型，HEAD 上的 Edit→Fix gap 也在 `+3.6 ~ +4.0 turn`；弱模型更糟，因为大量 run 根本到不了 first fix。
- **协议切换影响的是修复收敛，而不是首次编辑时点：** 当前 matched rerun 显示 plain baseline 的差距有限，但最佳条件能把通过率拉到 `45%`。这说明真正困难的不是“何时开始编辑”，而是**首次编辑之后如何收敛到正确补丁**。

> **洞察：** HEAD 困难具有**双维度结构**——定位较早，但“给出定位”并不自动转化为修复。全量 HEAD 20 hint study（§2d）显示 Mistral 从 L0 5% 升至 L2 25%、L4 40%；但增益几乎全部来自 QuixBugs（1/9→4/9→7/9），非 QuixBugs 仅 0/11→1/11→1/11。说明**修复生成**仍是更一般的主瓶颈，而精确定位的帮助依赖任务子型。

#### 两种失败模式总结

> **Mistral HEAD 的主要浪费模式是"盲目修补"（blind patching）：**
> - **HEAD 20** 上 act_only 的 avg edits **5.4**，但通过率仅 20%
> - **本质：无足够引导时大量编辑却多数无法修对。**
>
> **120B HEAD 的主要浪费模式是"过度探索"（excess exploration）：**
> - 在 HEAD 20 上 act_only 75% pass、~30K tokens
> - **本质：知道要看反馈，但探索与修复轮次较多。**

### 2c. 多尝试机制：为什么对 HEAD 有效？

**问题：** 对 Mistral HEAD，为什么多尝试/预算重分配比 plain protocol switch 更有效？关键增益来自 `Episode 2`、`Ep1` prompt，还是更一般的错误轨迹管理？

**HEAD 20 上（matched evidence）：** Mistral 的 plain baseline 排序是 `act_only 25%`、`react 35%`、`reflexion 30%`；最佳条件则是 `react + early_stop_restart = 45%` 与 `reflexion + self_consistency = 45%`。这里真正需要解释的是：为什么 HEAD 上最有效的是多尝试/预算重分配策略，而不是 plain protocol switch。

**更严谨的机制检验（2026-03-08 matched ablation，同批 HEAD20 重跑）：**
- `react baseline = 8/20 (40%)`
- `reflexion baseline = 8/20 (40%)`
- `reflexion Ep1-only = 7/20 (35%)`
- `restart-without-reflection = 5/20 (25%)`

完整结果见 `docs/report/reflexion_mechanism_ablation_head20.json` 与 `docs/report/reflexion_mechanism_ablation_head20.md`。

**关键发现：**
- **在这批 matched ablation 中，`react baseline` 与 `reflexion baseline` 没有聚合差距。** 两者都是 `8/20`，家族分布也完全相同：`DebugBench 1/7`、`Mini-nightmare 0/4`、`QuixBugs 7/9`。两者只是在 QuixBugs 上互换了 1 个成功任务。
- **`react` 也没有表现成 “Reflexion Ep1 的严格下界”。** `Ep1-only` 只有 `7/20`，与 `react` 的差距只是 1 个任务；这说明 `react` 不是 `Ep1` 的同义条件，但当前 batch 也不支持 “Ep1 稳定优于 react”。
- **Episode 2 不是稳定增益来源。** baseline 与 restart-without-reflection 都没有出现 `Ep1 fail → Ep2 pass` 的救回样本。
- **clean restart 本身反而是负信号。** `restart-without-reflection = 5/20`，且平均 token 最高，说明“清空上下文再来一次”至少在这批 run 里不是有效解释。

> **当前结论是：** `react` 与 `reflexion baseline` 在 matched ablation 中并列，`Episode 2 restart` 不是稳定增益源，而 HEAD 上目前最有效的条件是**把预算拆成多个更短尝试**的策略族。也就是说，现有证据更支持“错误轨迹持续时间管理”这一更一般机制，而不是某个固定协议的天然优势。

> **为什么还不能把 Ep2 判成“确定无用”？** 因为同一模型、同一 seed、同一任务在 API 后端上仍有明显不稳定性；当前证据足以否定 “Ep2 是稳定主因”，但还不足以把所有 Ep2 价值归零。更准确的解读是：这是**强负证据**，不是最终因果识别。

> **新的 open question：** 下一步更合理的实验顺序是：(1) multi-repeat / multi-seed 的 matched `react / Ep1-only / baseline / restart-without-reflection`；(2) `reflection-without-reset`；(3) 更严格的 budget-matched rerun。

### 2d. 因果验证：Hint Study

**说明：** `2026-03-08` 已补跑完新 20 HEAD 缺失的 **39 runs**（13 tasks × Mistral L2/L4 + 120B L2），现在 **L0/L2/L4（Mistral）与 L0/L2（120B）均覆盖全 20**。下表与分析基于更新后的 `head_20_from_existing.json`；完整报告见 **`docs/report/head_20_hint_study_report.md`**。

| Hint Level | 描述 | Mistral Pass（新 20） | 120B Pass（新 20） |
|:----------:|:----:|:--------------------:|:------------------:|
| L0（无 hint） | react baseline | 1/20 (5%) | 14/20 (70%) |
| L2（函数名） | 函数级定位 | 5/20 (25%) | 20/20 (100%) |
| L4（行号） | 行级定位 | 8/20 (40%) | — |

**Q1 ✓：** 在全 20 上，L0→L2 使 Mistral 通过率 **+20pp**（5%→25%），L4 进一步到 **40%**；L2 使 120B 从 70% 升到 **100%**。说明**定位信息**确实能恢复一部分弱模型能力。

**Q2 ✓ / △：** 全量 20 上 **L4 > L2**（40% vs 25%）；但收益高度集中在 **QuixBugs**：Mistral 在 QuixBugs 上为 **1/9 → 4/9 → 7/9**，而在 **DebugBench** 上仅 **0/7 → 1/7 → 1/7**，在 **Mini-nightmare** 上为 **0/4 → 0/4 → 0/4**。这说明**修复生成困难**仍是更一般的瓶颈，而行级 hint 的收益取决于任务结构：对单行算法 bug 更像“最后一跳”提示，对结构性任务几乎无效。

**Q3：** 120B 在 L0 全 20 为 70%，L2 达 **100%**。强模型多数情况下不必依赖 hint 才能修好，但函数级定位可把剩余失败全部拉平，hint 的主要作用转为**提通过率 + 降探索成本**。

#### 新分析：HEAD 不是单一困难类型，而是两种子型的混合

> **定位敏感型 HEAD（localization-sensitive HEAD）：**
> - 主要对应 **QuixBugs** 这类单行算法 bug
> - Mistral 在 QuixBugs HEAD 上呈现清晰剂量曲线：**1/9 → 4/9 → 7/9**
> - 这类 HEAD 的主要问题是“最后一跳”不稳：一旦给出更精确定位，弱模型可以把相当一部分 run 转化为正确补丁
>
> **结构敏感型 HEAD（structure-sensitive HEAD）：**
> - 主要对应 **DebugBench / Mini-nightmare**
> - Mistral 在 DebugBench 上仅 **0/7 → 1/7 → 1/7**，在 Mini-nightmare 上 **0/4 → 0/4 → 0/4**
> - 这类 HEAD 的困难不是“找不到位置”，而是即使知道位置，也缺乏足够稳定的修复生成与验证能力
>
> **新的 HEAD 视角：** HEAD 不是一个同质的“难 bug 桶”，而是至少由**定位敏感**与**结构敏感**两类任务机制构成。前者更受益于 hint，后者更依赖协议/策略来改善搜索与修复行为。这也解释了为什么在 HEAD 内部，不同干预会在不同子型上显示出完全不同的收益曲线。

---

## 第三步：策略探索——什么配置组合能帮助 HEAD？

### 协议对比与策略重排（HEAD 20）

**Mistral on HEAD (20 bugs, matched rerun):**

| Protocol | Best Matched Strategy | Pass Rate | Avg Tokens | 说明 |
|----------|-----------------------|:---------:|:----------:|------|
| act_only | checklist / early_stop_restart | 35% | ~38.8K / ~41.8K | baseline 不足，但可被过程约束拉起 |
| **react** | **early_stop_restart** | **45%** | **~36.8K** | 当前 matched 最优 |
| reflexion | self_consistency | 45% | ~37.3K | 与 react+early_stop_restart 并列，但 turns 更长 |

### 策略对比：HEAD (20 bugs)

**Mistral HEAD — 跨协议策略一览（matched rerun）：**

| Protocol | Baseline | +Checklist | +Early-stop | +Self-consistency |
|----------|:--------:|:----------:|:-----------:|:-----------------:|
| act_only | 25% | 35% | 35% | 25% |
| react | 35% | 25% | **45%** | 40% |
| reflexion | 30% | 20% | 40% | **45%** |

> *N=20（新定义 HEAD）。以下排序全部来自 `docs/report/head_20_mistral_matched_protocol_strategy.json`。*
>
> **关键发现（新 20 HEAD）：** Mistral 上当前 matched 最优是 **react + early_stop_restart** 与 **reflexion + self_consistency**（均 45%）。其次是 `reflexion + early_stop_restart` 与 `react + self_consistency`（40%）。这表明对当前稳健定义下的 HEAD 20，**决定成败的不是单纯协议切换，而是是否能把预算切成多个更独立的尝试**。

> **但这个“最优”也有明确边界：** 前两名条件的 family breakdown 完全相同，都是 **QuixBugs 7/9、DebugBench 2/7、Mini-nightmare 0/4**。也就是说，当前 matched 最优配置主要救回的是**定位敏感型 HEAD**，对 `DebugBench / Mini-nightmare` 这类更结构敏感的 HEAD 仍然只产生有限收益。

**Mistral HEAD 配置排序（20 bugs，matched rerun）：**

| 配置 | Pass Rate | Δ vs act_only baseline |
|------|:---------:|:----------------------:|
| **react + early_stop_restart** | **45%** | +20pp |
| **reflexion + self_consistency** | **45%** | +20pp |
| reflexion + early_stop_restart | 40% | +15pp |
| react + self_consistency | 40% | +15pp |
| act_only + checklist | 35% | +10pp |
| react + baseline | 35% | +10pp |
| act_only + early_stop_restart | 35% | +10pp |
| reflexion + baseline | 30% | +5pp |

> **实践要点：** 当前 matched 证据支持两条主路线：一是 **react + early_stop_restart**，二是 **reflexion + self_consistency**；若更偏好简单、低 turns 的配置，`act_only + checklist` 是更轻量的选择。与此同时，若任务更像 `DebugBench / Mini-nightmare`，这些最佳配置也只把通过率拉到局部改善，不能被表述成“已经解决 HEAD”。

### 两层分类下的其他切片（简述）

> **human-easy / Easy（16）：** Mistral `act_only = 87.5%`，说明这部分确实是“对人简单、对 agent 也简单”的正常区间。这里最稳妥的选择仍是低成本基线，而不是更复杂的过程控制。
>
> **human-easy / Intermediate（8）：** 它们比 HEAD 更容易，但已经不是“随便就过”。Mistral 从 `act_only 25.0%` 升到 `reflexion 50.0%`，说明这批 bug 更像 `HEAD` 的近邻，而不是应该被并入一个“Hard 桶”。
>
> **human-difficult（46）：** 这是另一条轴。它表示人类也需要更深推理；它与 HEAD 的区别不在“是否更难”，而在**为什么难**：HEAD 是人简单/AI难的反常失配，human-difficult 则是人和 AI 都需要更多结构性推理。

### 效率与核心结论（HEAD 聚焦）

> **Token：** 在新 HEAD 20 上，Mistral 的当前 matched 最佳是 `react + early_stop_restart`（45%，~36.8K）与 `reflexion + self_consistency`（45%，~37.3K）；两者都明显优于 `act_only baseline = 25%`。这说明弱模型的收益来自更合适的 budget slicing，而不是更长的单次轨迹。
>
> **结论要点：** (1) **协议效果随难度变化**这条高层现象仍成立，但在 HEAD 上 plain protocol 的排序并不稳；(2) **策略效果强烈依赖协议**——在当前 matched batch 中，`early_stop_restart` 和 `self_consistency` 反而排到最前；(3) **最佳条件共享同一机制：把预算切成多个更短、更独立的尝试**；(4) 这些最佳条件的增益主要体现在 `QuixBugs 7/9`，对 `DebugBench 2/7`、`Mini-nightmare 0/4` 仍有限。

### 推荐配置（两层分类，HEAD 为重点）

| 层级 / 子类 | 模型 | 推荐协议 | 推荐策略 | 理由 |
|------------|------|---------|---------|------|
| **human-easy / HEAD** | Mistral | **react 或 reflexion** | `early_stop_restart` 优先；`self_consistency` 次选 | 当前 matched 最优为 `react + early_stop_restart = 45%`，`reflexion + self_consistency = 45%` |
| **human-easy / Intermediate** | Mistral | **reflexion** | baseline 起步 | `50%`，明显高于 act_only `25%` |
| **human-easy / Easy** | Mistral | **act_only** | baseline | 已到 `87.5%`，追求最低成本即可 |

> **实践指导：** 先判断 bug 在两层分类中的位置，再选协议。`HEAD` 与 `Intermediate` 都属于 `human-easy`，但 `HEAD` 的当前最优解法不是单纯换协议，而是优先使用**能切断单次错误轨迹的策略**；`human-difficult` 则应被视为另一类需要更深推理的任务，而不是 HEAD 的更高难版本。

---

## 第四步：总结

### 回答核心问题：为什么 HEAD 困住 AI Agent？

> **1. 表面原因——持续时间异常。** HEAD 上 token 消耗高主要因 run 持续更多 turn，而非单 turn 爆炸；Mistral 在 act_only 下常跑满 budget 仍失败。
>
> **2. 根本原因——双维度困难。** 轨迹与全量 hint study 一致：agent 往往较早开始编辑，但能否把定位转化为正确补丁取决于任务结构。对 QuixBugs 这类单行算法 bug，L4 可把 Mistral 从 1/9 拉到 7/9；对 DebugBench / Mini-nightmare，L2/L4 几乎不改变失败率。说明**修复生成**是更一般的主瓶颈，而定位信息的收益具有明显的子型依赖。
>
> **3. 协议-难度交互。** 在 `human-easy` 内部，协议收益呈明显梯度：弱模型在 `Easy` 上 act_only 已够，在 `Intermediate` 上 reflexion 仍是当前最好选择，但在 `HEAD` 上 plain protocol 的排序并不稳定，真正起决定作用的是是否配上能切短错误轨迹的策略。
>
> **4. 两层分类让 HEAD 的角色更清晰。** HEAD 不是笼统的“hard bug”，而是 `human-easy` 内部最反常的左尾。`Intermediate` 说明 human-easy bug 本身就有梯度，而 `human-difficult` 则提醒我们不要把“对人也难”和“对 AI 反常地难”混为一谈。
>
> **5. 策略效果依赖协议与子型。** 在当前 matched HEAD20 上，Mistral 的最佳结果来自 **react + early_stop_restart** 与 **reflexion + self_consistency**（均 45%），但两者都主要修复 `QuixBugs 7/9`，对 `DebugBench` 只到 `2/7`、对 `Mini-nightmare` 仍是 `0/4`。说明 HEAD 所需的不是简单切到某个“更聪明”的协议，而是优先选择能把预算切成多个更短尝试的组合；同时，这类组合目前主要改善**定位敏感型 HEAD**。**最优配置是 (模型 × 协议 × 策略 × HEAD子型) 的函数。**

### HEAD 的本质

> HEAD 是 `human-easy` 内部**最反常**的 bug 子集（新定义：human-easy + Mistral 5-seed act_only 通过率 ≤20%，共 20 个）。它们不是“所有难 bug 的代表”，而是**人类低门槛任务中 AI 能力边界的诊断透镜**：强模型仍可多数修好但成本较高，弱模型在无引导基线下多数失败。一个独立的小模型复核也支持这一点：`api-llama-4-scout` 在同一 HEAD-20 上的 `act_only` 仅为 **8/20 (40%)**，且在 `Mini-nightmare` 上仍是 **0/4**。当前 matched rerun 进一步表明，HEAD 上的关键不是“选对唯一协议”，而是**是否能管理错误轨迹的持续时间**；效果依赖具体子集与协议组合。

### Limitations & Future Work

> **Limitations：** (1) 两层分类依赖 `human-easy` 标注与 Mistral act_only 5-seed；虽然新增的 `Llama-4-Scout` 复核显示同一 HEAD-20 在另一小模型家族上也仅有 `8/20 (40%)`，但这仍不足以把 HEAD 升格为完全模型无关的本体类别；(2) `Intermediate` 只有 8 个、`HEAD` 只有 20 个，策略排序的置信度受限于单 seed 协议×策略数据；(3) 虽然新 20 的 hint study已补齐全量，但目前仍是**单 seed**，且呈现出强烈的任务子型异质性；(4) 当前 matched rerun 与 Reflexion mechanism ablation 仍受 API 不稳定性影响，因此机制识别仍需 multi-repeat / multi-seed；(5) 当前分析已显示 HEAD 内部至少存在两类子型，但缺乏一个自动、可复现的子型划分标准。
>
> **Future Work：** (1) 对新 20 HEAD 做 **multi-seed** hint 与协议×策略验证；(2) 将 hint study 从“通过率”扩展到**成本/turn 降幅**分析；(3) multi-repeat / multi-seed 的 Reflexion mechanism ablation；(4) 解释为什么 L4 收益主要集中在 QuixBugs；(5) 自适应 (协议×策略×hint) 选择。

---

## 论文贡献

| # | 贡献 | 对应叙事 |
|---|------|---------|
| 1 | **HEAD 现象的发现与定义** | §1：基于 `human-easy / human-difficult` + `human-easy` 内部 `Easy / Intermediate / HEAD` 的两层分类；HEAD 定义为 human-easy 且 Mistral act_only 5-seed ≤1/5 |
| 2 | **HEAD 根因的多维度分析** | §2a-2b：协议-难度交互（效果方向随难度反转）、blind patching vs excess exploration（失败模式）、Edit→Fix gap（双维度困难） |
| 3 | **Hint study 因果验证** | §2d：全 20 上 L2 25%、L4 40%、120B L2 100%；收益主要集中于 QuixBugs（1/9→4/9→7/9），说明修复生成为更一般瓶颈且 hint 效果具子型依赖 |
| 4 | **多尝试机制解析** | §2c：matched ablation 显示 `react = 40%`、`reflexion baseline = 40%`、`Ep1-only = 35%`、`restart-without-reflection = 25%`；Episode 2 不是稳定增益源，机制上表现为“错误轨迹持续时间管理” |
| 5 | **干预效果与协议×策略依赖** | §3：matched HEAD20 协议×策略汇总显示 Mistral 最优为 `react + early_stop_restart` 与 `reflexion + self_consistency`（均 45%）；plain reflexion baseline 仅 30%，策略收益强烈依赖协议 |
| 6 | **HEAD 内部子型分析** | §2d：HEAD 由定位敏感型（QuixBugs）与结构敏感型（DebugBench / Mini-nightmare）混合构成，解释了 hint 与策略干预为何呈现强烈异质性 |
| 7 | **推荐配置矩阵** | §3：基于两层分类的 (human difficulty × AI difficulty × 模型能力) → (协议, 策略) 推荐 |

---

## 论文结构

| Section | 内容 | 预计篇幅 |
|---------|------|---------|
| **Abstract** | 核心问题（为什么简单 bug 困住 agent？）+ HEAD 发现 + 根因 + hint study 验证 + 干预非线性交互 | 250 words |
| **1. Introduction** | Motivating example（同一简单 bug：120B 可修但成本高，Mistral 在 HEAD 20 上 act_only 仅 20%，协议/策略选择显著影响弱模型表现） | 1.5p |
| **2. Related Work** | ReAct, Reflexion, debug-gym, DebugBench, QuixBugs, cost-efficiency | 1p |
| **3. Experimental Setup** | POMDP + 90 tasks + 两层分类 + HEAD20 hint study + matched reruns（240 + 80） | 1p |
| **4. HEAD: Discovery** | 4.1 后验发现 + 4.2 操作性定义（act_only baseline）+ 4.3 成本签名 + 4.4 Bug type → HEAD | 1.5p |
| **5. Why HEAD Confounds Agents** | 5.1 协议-难度交互 + 5.2 Agent 行为（Edit→Fix gap, 失败模式）+ 5.3 多尝试机制 + 5.4 Hint study 因果验证 | 3p |
| **6. Strategy Exploration** | 6.1 协议对比 + 6.2 策略效果与非线性交互 + 6.3 推荐矩阵 | 2p |
| **7. Discussion** | HEAD 的本质 + 非线性交互机制 + Limitations + Future Work | 1.5p |
| **8. Conclusion** | 核心回答 + 实践指导 | 0.5p |
| **Total** | | ~12–13p |

---

## 风险与应对

| 风险 | 应对 |
|------|------|
| HEAD 定义依赖特定模型对 | 已有 `Llama-4-Scout` 独立复核（`8/20`），可作为跨模型稳健性的初步证据；仍建议继续补更多小模型 |
| 协议-难度交互可能是 Mistral 特有 | debug-gym [17] 报告类似趋势；承认需更多模型验证 |
| 多尝试机制仍受 API 不稳定性影响 | §2c 已补做 matched ablation；下一步需 multi-repeat / multi-seed |
| 少数非 HEAD 配置有个别缺失 | 不影响 HEAD 方向性结论（HEAD 全覆盖） |

### 论文完整性

全部 **7 项贡献**都建立在当前 active 证据上：两层分类来自 `docs/bug_annotations_v2.json` 与 `report/merged_5seed_act_only_baseline.json`；HEAD20 的过程与 hint 证据来自 `docs/report/head_20_from_existing.json`；协议×策略结论以 `docs/report/head_20_mistral_matched_protocol_strategy.json` 为准；Reflexion 机制结论以 `docs/report/reflexion_mechanism_ablation_head20.json` 为准；跨模型稳健性的补充复核见 `docs/report/head20_llama4scout_recheck.md`。

---

## 投稿定位

| Venue | 适配度 | 理由 |
|-------|:-----:|------|
| **EMNLP / ACL** | ★★★★★ | 协议-难度交互 + 多维度根因分析 + failure taxonomy 适合 analysis track |
| **NeurIPS / ICLR** | ★★★★☆ | 协议-模型-难度交互 + Reflexion 机制解析是 ML 社区关心的 |
| **ICSE / FSE** | ★★★★☆ | 推荐配置表 + wall-time 分析直接指导工具设计 |
| **Workshop** | ★★★★★ | HEAD + 协议-难度交互已可写 full workshop paper |

**推荐路径：** 以当前 HEAD20 active 证据链为主线写作：两层分类 → 轨迹与 hint 分析 → matched protocol×strategy → mechanism ablation。这样行文更干净，也更不容易让读者把不同批次的数据混成一套排序结论。

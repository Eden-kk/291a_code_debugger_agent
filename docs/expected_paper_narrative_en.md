# Why Do Structurally Simple Bugs Trap AI Agents?
## A HEAD-Bug Study Based on the Current HEAD20 Evidence

**Date:** 2026-03 (v15, latest-only narrative)  
**Based on:** `docs/bug_annotations_v2.json` (human-easy annotations), `report/merged_5seed_act_only_baseline.json` (two-layer classification), `docs/report/head_20_from_existing.json` (HEAD20 trajectory aggregates and hint study), `docs/report/head_20_mistral_matched_protocol_strategy.json` (current Mistral HEAD20 protocol×strategy ranking), and `docs/report/reflexion_mechanism_ablation_head20.json` (mechanism test).

> **Core question:** There exists a class of bugs that are easy for humans but difficult for AI agents. We call them **HEAD (Human-Easy but AI-Difficult)**. Under the current **two-layer classification**, we first split bugs into `human-easy (44)` and `human-difficult (46)`, then split `human-easy` into `Easy (16)`, `Intermediate (8)`, and `HEAD (20)`. **Why does HEAD become the most anomalous slice inside human-easy bugs?**

---

## Research Flow

```text
1. Two-layer classification -> define `human-easy / human-difficult` and `Easy / Intermediate / HEAD`
   ↓
2. Root-cause analysis -> bug characteristics + agent behavior + protocol-difficulty interaction
   ↓
3. Causal validation -> hint study confirms a two-dimensional difficulty structure
   ↓
4. Strategy exploration -> matched rerun + mechanism ablation reveal nonlinear intervention effects
   ↓
5. Conclusions and practical guidance
```

**Main thesis:** Under the two-layer classification, HEAD is the anomalous left tail inside `human-easy` bugs. The current HEAD20 evidence suggests that the key question is not “which protocol is inherently smarter,” but **whether the agent can control the duration of a bad trajectory**. The best-performing setup depends on `(protocol × strategy × HEAD subtype)`.

---

## Step 1: Current Setup

### Current Evidence Design

| Dimension | Setting |
|------|------|
| **Dataset** | QuixBugs (40) + Mini-nightmare (10) + DebugBench (40) = **90 tasks** |
| **Models** | 120B (`api-gpt-oss-120b`, strong) + Mistral Small (`api-mistral-small-3.2-2506`, weak) |
| **Protocols** | act_only, react, reflexion |
| **Strategies** | baseline, checklist, early_stop_restart, self_consistency |
| **Classification baseline** | `human-easy / human-difficult` annotation + Mistral act_only 5-seed |
| **HEAD20 hint study** | full coverage: Mistral `L0/L2/L4`, 120B `L0/L2` |
| **Matched rerun** | Mistral HEAD20 `3 protocols × 4 strategies = 240 runs` |
| **Mechanism ablation** | Reflexion / ReAct-related controls = `80 runs` |

### Two-Layer Classification

We use binary human annotation from `docs/bug_annotations_v2.json`:

> **human-easy:** an experienced programmer can identify and repair the bug directly from the code and test output, without deep algorithmic reasoning.  
> **human-difficult:** the bug requires deeper algorithmic, logical, domain-specific, or multi-step reasoning.

Result: **44 human-easy, 46 human-difficult**.

### Second-Layer Split Within `human-easy`

To reduce single-run noise and backend drift, we define AI difficulty using **Mistral act_only with five seeds (42, 43, 44, 45, 46)**:

- **Easy:** `human-easy` and Mistral 5-seed pass rate **>= 60%** -> **16 bugs**
- **Intermediate:** `human-easy` and Mistral 5-seed pass rate **= 40%** -> **8 bugs**
- **HEAD:** `human-easy` and Mistral 5-seed pass rate **<= 20%** -> **20 bugs**

> **Why use act_only as the classification baseline:** act_only is closest to the model's raw debugging capability. HEAD is defined by stable weak-model failure under this minimal baseline, so protocol and strategy become analyzable interventions rather than part of the category definition.

### Two-Layer Overview

| Layer | Category | Count | Definition |
|------|------|:----:|------|
| Layer 1 | **human-easy** | 44 | Easy for humans to repair directly from code and tests |
| Layer 1 | **human-difficult** | 46 | Requires deeper algorithmic/logical/domain reasoning |
| Layer 2 (within human-easy only) | **Easy** | 16 | Mistral act_only passes at least 3/5 seeds |
| Layer 2 (within human-easy only) | **Intermediate** | 8 | Mistral act_only passes exactly 2/5 seeds |
| Layer 2 (within human-easy only) | **HEAD** | 20 | Mistral act_only passes at most 1/5 seeds |

> **Interpretation:** `Intermediate` is not “harder than HEAD.” It is the transition band inside `human-easy`. The right comparison is HEAD versus other `human-easy` bugs, especially `Easy` and `Intermediate`, not HEAD versus a mixed “hard” bucket.

### Cost Signature of HEAD

On HEAD, 120B still solves most tasks but at nontrivial cost (`act_only ≈ 75%`, `~30K` tokens), while Mistral under `act_only` remains around `20%` on a single seed and mostly `0/5` or `1/5` under the 5-seed definition. This is exactly the anomaly of interest: **structurally simple bugs that remain stably difficult for a weak model**.

### Composition of the Current HEAD20

The current HEAD20 contains: QuixBugs `9`, DebugBench `7`, Mini-nightmare `4`. QuixBugs-style algorithmic tasks and system-like debugging tasks in DebugBench/Mini-nightmare both enter HEAD when they are human-easy yet repeatedly fail under weak-model act_only.

---

## Step 2: Why Does HEAD Trap Agents?

> HEAD bugs are structurally simple and easy for humans, yet AI agents either pay unusually high cost or fail outright. We analyze this from four angles: protocol-difficulty interaction, agent behavior, multiple-attempt mechanism, and causal evidence from the hint study.

### 2a. Protocol-Difficulty Interaction

#### Current HEAD20 Protocol Evidence: Mistral Matched Rerun

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

**Current conclusion from this matched batch:** on HEAD, Mistral's most reliable gains do not come from a plain protocol switch, but from **budget redistribution / multiple attempts**.

> **Observed pattern:** when act_only is insufficient, especially on HEAD, switching to a heavier protocol may help, but the more stable gains come from the interaction between protocol and multi-attempt strategy. On Easy, where act_only is already sufficient, extra reasoning is mostly overhead. Protocol effects depend on `(model capability × task difficulty × whether bad trajectories are cut short)`.

> **Key gradient under the two-layer classification:**
> - On `human-easy / Easy`, Mistral `act_only = 87.5% (14/16)`, so this slice is also “normally easy” for the weak model.
> - On `human-easy / Intermediate`, Mistral `act_only = 25.0% (2/8)` and `reflexion = 50.0% (4/8)`, so protocol starts to matter.
> - On `HEAD`, the matched rerun shows that `act_only baseline` is clearly insufficient, and that these 20 tasks are highly sensitive to process control.
>
> This makes HEAD the **extreme left tail inside human-easy bugs** rather than a generic “hard” category.

#### Mechanism: Reasoning Quality × Task Demands

> - **When model capability > task demand (`human-easy / Easy`):** act_only is already enough; extra reasoning is mostly cost. For Mistral, `react` even drops from `87.5%` to `75.0%`.
> - **When model capability is close to task demand (`human-easy / Intermediate`):** protocol starts to matter; Mistral rises from `act_only 25.0%` to `reflexion 50.0%`.
> - **When model capability is clearly insufficient (`HEAD`):** act_only is not enough, but not every protocol change helps. In the matched rerun, the winning conditions are `react/reflexion` combined with **restart or multiple-attempt strategies**, not plain reflexion baseline.
> - **`human-difficult` is a separate axis:** it indicates tasks that are also difficult for humans and should not be mixed with HEAD into the same “hard bucket.”
>
> *Protocol effects are therefore not monotonic with difficulty. What matters is where the bug sits in the two-layer classification and whether the protocol produces useful reasoning for that slice.*

#### What Is the Most Stable Protocol Conclusion?

> **The current stable conclusion is not “react is worse” or “reflexion is better,” but that plain protocol switch is not enough.** In this matched 12-condition rerun, Mistral baseline performance is only `act_only = 25%`, `react = 35%`, `reflexion = 30%`. The leading conditions are `react + early_stop_restart = 45%` and `reflexion + self_consistency = 45%`.
>
> **Implication:** the most stable gains on HEAD come from **splitting the budget into multiple shorter, more independent attempts**, not from simply adding a `Think -> Act` or Reflexion scaffold.
>
> **Therefore:** the main challenge of HEAD for a weak model is first that `act_only baseline` is clearly insufficient, and second that the biggest gains come from **protocol × strategy** interaction, especially strategies that limit how long one incorrect trajectory is allowed to continue.

### 2b. Agent Behavior: What Does the Agent Do Wrong on HEAD?

#### Basic Trajectory Aggregates

> *The following statistics are for the current HEAD20 and come from `scripts/head_20_data_from_existing.py` -> `docs/report/head_20_from_existing.json`. The `act_only` trajectory statistics here come from the current HEAD20 act_only aggregate, whereas the `25%` baseline in `§2a/§3` comes from the matched rerun. They serve different purposes; this section is only about behavior patterns.*

| Metric | 120B HEAD (20) | Mistral HEAD (20) |
|------|:--------------:|:-----------------:|
| Avg edits | 2.9 | **5.4** |
| Avg tests | 2.5 | 3.4 |
| Avg views | 3.5 | 3.1 |
| 1st Edit turn | 5.3 | 5.2 |
| 1st Fix turn | 8.7 | 8.2 |

> *Note: the Mistral act_only pass rate here is written as `20%` because it refers to the current HEAD20 act_only aggregate; the matched-rerun baseline in `§2a` is `25%`. `1st Fix` is averaged over successful runs only. As a contrast, on `human-easy / Easy`, Mistral act_only already reaches `87.5%`, with only `18.1K` average tokens, versus `47.1K` on HEAD.*

#### Token Curve

**Question:** does HEAD consume tokens through a late explosion, or through uniformly prolonged runs?

**Key finding:**
- **Token-per-turn grows linearly** as context accumulates; there is no late-stage explosion.
- **120B on HEAD20** achieves `75%` under act_only at around `30K` tokens, with most successful runs converging in a bounded number of turns.
- **Mistral on HEAD20** under act_only reaches only `20%`; failed runs often consume nearly the full budget (`~47K`), showing a pattern of uniform exhaustion.
- On `human-easy / Easy`, both models often converge within `16–18K` tokens. The main HEAD anomaly is therefore **duration**, not single-step complexity.

> **Insight:** the cost anomaly of HEAD is fundamentally a **duration anomaly**. The per-turn cost looks similar; HEAD becomes expensive because the run lasts much longer, or never converges.

#### Localization -> Repair Gap

**Question:** is HEAD primarily a localization problem or a repair problem?

> *The table below reports HEAD20 Edit->Fix statistics from `docs/report/head_20_from_existing.json`. As above, it is used to describe repair-stage behavior, not to rank protocols in the matched setting.*

| Model | Protocol | 1st Edit | 1st Fix | **Edit->Fix Gap** |
|-------|----------|:--------:|:-------:|:-----------------:|
| 120B | act_only | 5.3 | 8.7 | **+3.6** |
| 120B | react | 5.5 | 9.1 | **+3.9** |
| 120B | reflexion | 5.5 | 9.7 | **+4.0** |
| Mistral | act_only | 5.2 | 8.2 | +3.0 |
| Mistral | react | 5.3 | 8.0 | — (only 1 success) |
| Mistral | reflexion | 5.0 | 8.2 | **+2.4** |

**Key findings:**
- **Editing does not start particularly late:** both models begin editing around `turn 5`. The problem is not “the agent never knows where to touch,” but rather that **editing still fails to converge to the correct patch**.
- **The repair phase is longer:** even for the strong model, the HEAD Edit->Fix gap remains around `+3.6 ~ +4.0 turns`; for the weak model it is worse because many runs never reach a first fix at all.
- **Protocol mainly affects repair convergence rather than the first-edit time:** in the matched rerun, baseline differences are limited, but the best conditions still lift pass rate to `45%`. The real difficulty is therefore not *when* the agent starts editing, but **whether it can converge after editing begins**.

> **Insight:** HEAD has a **two-dimensional difficulty structure**. Localization often happens relatively early, but “having a candidate location” does not automatically translate into a correct fix. The full HEAD20 hint study in `§2d` shows Mistral moving from `L0 5%` to `L2 25%` to `L4 40%`, but almost all of that gain comes from QuixBugs (`1/9 -> 4/9 -> 7/9`), whereas non-QuixBugs moves only from `0/11 -> 1/11 -> 1/11`. This means **repair generation** remains the more general bottleneck, and localization help is strongly subtype-dependent.

#### Two Waste Patterns

> **Mistral's main waste pattern on HEAD is blind patching:**
> - under act_only, it averages **5.4 edits** on HEAD20 but passes only `20%`
> - the core issue is **many edits without enough guidance to make them correct**
>
> **120B's main waste pattern on HEAD is excess exploration:**
> - on HEAD20 under act_only, it reaches `75%` at around `30K` tokens
> - the core issue is **too many exploration-and-repair rounds**, not complete inability

### 2c. Multiple-Attempt Mechanism: Why Does It Help on HEAD?

**Question:** for Mistral on HEAD, why are multi-attempt / budget-redistribution conditions more effective than plain protocol switch? Is the gain coming from Episode 2, from the Ep1 prompt, or from a broader form of trajectory management?

**HEAD20 under matched evidence:** Mistral baseline performance is `act_only 25%`, `react 35%`, `reflexion 30%`, while the best conditions are `react + early_stop_restart = 45%` and `reflexion + self_consistency = 45%`. The mechanism question is therefore: why do multi-attempt strategies dominate plain protocol switch on HEAD?

**More controlled mechanism test (2026-03-08 matched ablation on the same HEAD20 batch):**
- `react baseline = 8/20 (40%)`
- `reflexion baseline = 8/20 (40%)`
- `reflexion Ep1-only = 7/20 (35%)`
- `restart-without-reflection = 5/20 (25%)`

Full results are in `docs/report/reflexion_mechanism_ablation_head20.json` and `docs/report/reflexion_mechanism_ablation_head20.md`.

**Key findings:**
- **In this matched ablation, `react baseline` and `reflexion baseline` show no aggregate gap.** Both are `8/20`, with identical family breakdown: `DebugBench 1/7`, `Mini-nightmare 0/4`, `QuixBugs 7/9`.
- **`react` is also not a strict lower bound of “Reflexion Ep1.”** `Ep1-only` is only `7/20`; the gap is one task.
- **Episode 2 is not a stable gain source.** Neither baseline nor restart-without-reflection shows any `Ep1 fail -> Ep2 pass` rescue case.
- **Clean restart by itself is a negative signal.** `restart-without-reflection = 5/20`, with the highest average token count.

> **Current conclusion:** `react` and `reflexion baseline` are tied in the matched ablation; `Episode 2 restart` is not a stable gain source; and the most effective conditions on HEAD are currently those that **split the budget into shorter attempts**. The evidence therefore points to **trajectory-duration management** rather than to an intrinsic advantage of one fixed protocol.

> **Why not declare Ep2 completely useless?** Because the same model, seed, and task can still vary under API execution. The current evidence is strong negative evidence against “Ep2 as the main cause,” but not a final causal identification.

> **Open question:** the next logical experiments are `(1)` multi-repeat / multi-seed matched runs for `react / Ep1-only / baseline / restart-without-reflection`, `(2)` `reflection-without-reset`, and `(3)` stricter budget-matched reruns.

### 2d. Causal Validation: Hint Study

**Note:** on `2026-03-08`, the missing **39 runs** for the current HEAD20 hint study were completed (`13 tasks × Mistral L2/L4 + 120B L2`). Coverage is now complete for Mistral `L0/L2/L4` and 120B `L0/L2` on all 20 tasks. The updated aggregate is in `docs/report/head_20_from_existing.json`; the full report is `docs/report/head_20_hint_study_report.md`.

| Hint Level | Description | Mistral Pass (HEAD20) | 120B Pass (HEAD20) |
|:----------:|:-----------:|:---------------------:|:------------------:|
| `L0` | no hint / react baseline | 1/20 (5%) | 14/20 (70%) |
| `L2` | function-level localization | 5/20 (25%) | 20/20 (100%) |
| `L4` | line-level localization | 8/20 (40%) | — |

**Q1:** on the full 20 tasks, `L0 -> L2` lifts Mistral by **+20pp** (`5% -> 25%`), and `L4` further reaches **40%**. For 120B, `L2` raises pass rate from `70%` to **100%**. Localization information clearly restores part of the weak-model capability.

**Q2:** on the full 20 tasks, **`L4 > L2`** (`40%` vs `25%`), but the gain is highly concentrated in **QuixBugs**: Mistral moves from **`1/9 -> 4/9 -> 7/9`** there, while **DebugBench** changes only from **`0/7 -> 1/7 -> 1/7`** and **Mini-nightmare** stays at **`0/4 -> 0/4 -> 0/4`**. This means **repair generation** remains the more general bottleneck, and line-level hints behave like a “last-mile” intervention mainly for single-line algorithmic bugs.

**Q3:** for 120B, `L0 = 70%` and `L2 = 100%`. The strong model usually does not need hints in order to solve HEAD, but function-level localization removes the remaining failures entirely. For 120B, the main role of hints becomes **higher pass rate plus lower exploration cost**.

#### New View: HEAD Is a Mixture of At Least Two Subtypes

> **Localization-sensitive HEAD:**
> - mostly QuixBugs-style single-line algorithmic bugs
> - Mistral shows a clear dose-response curve: **`1/9 -> 4/9 -> 7/9`**
> - once localization becomes precise enough, many runs can convert into a correct patch
>
> **Structure-sensitive HEAD:**
> - mostly DebugBench and Mini-nightmare
> - DebugBench moves only **`0/7 -> 1/7 -> 1/7`**, Mini-nightmare stays **`0/4 -> 0/4 -> 0/4`**
> - the main difficulty is not simply “finding the location,” but generating and validating a stable repair even when the location is known
>
> **Updated HEAD perspective:** HEAD is not a homogeneous “hard bucket.” It is at least a mixture of **localization-sensitive** and **structure-sensitive** bugs. This is why different interventions produce sharply different gain curves inside HEAD.

---

## Step 3: Which Configurations Help on HEAD?

### Protocol Reordering on HEAD20

**Mistral on HEAD20 (matched rerun):**

| Protocol | Best Matched Strategy | Pass Rate | Avg Tokens | Notes |
|----------|-----------------------|:---------:|:----------:|------|
| act_only | checklist / early_stop_restart | 35% | ~38.8K / ~41.8K | baseline is insufficient but can be lifted by process constraints |
| **react** | **early_stop_restart** | **45%** | **~36.8K** | current matched best |
| reflexion | self_consistency | 45% | ~37.3K | tied with react+early_stop_restart, but longer in turns |

### Strategy Comparison on HEAD20

**Mistral HEAD — across protocols (matched rerun):**

| Protocol | Baseline | +Checklist | +Early-stop | +Self-consistency |
|----------|:--------:|:----------:|:-----------:|:-----------------:|
| act_only | 25% | 35% | 35% | 25% |
| react | 35% | 25% | **45%** | 40% |
| reflexion | 30% | 20% | 40% | **45%** |

> *`N = 20` (current HEAD definition). All rankings here come from `docs/report/head_20_mistral_matched_protocol_strategy.json`.*
>
> **Key finding:** the current matched best conditions are **react + early_stop_restart** and **reflexion + self_consistency** (both `45%`). The next tier is `reflexion + early_stop_restart` and `react + self_consistency` (both `40%`). This indicates that on the current HEAD20, **success is determined less by protocol identity alone and more by whether the budget is split into more independent attempts**.

> **But the “best” has a clear boundary:** the top two conditions have the same family breakdown: **QuixBugs 7/9, DebugBench 2/7, Mini-nightmare 0/4**. In other words, the matched best setups mainly rescue **localization-sensitive HEAD**, while still providing only limited gains on the more structure-sensitive slice.

### Mistral HEAD Configuration Ranking

| Configuration | Pass Rate | Delta vs act_only baseline |
|------|:---------:|:--------------------------:|
| **react + early_stop_restart** | **45%** | +20pp |
| **reflexion + self_consistency** | **45%** | +20pp |
| reflexion + early_stop_restart | 40% | +15pp |
| react + self_consistency | 40% | +15pp |
| act_only + checklist | 35% | +10pp |
| react + baseline | 35% | +10pp |
| act_only + early_stop_restart | 35% | +10pp |
| reflexion + baseline | 30% | +5pp |

> **Practical takeaway:** the current matched evidence supports two main routes on HEAD: **react + early_stop_restart** and **reflexion + self_consistency**. If a lighter configuration is preferred, `act_only + checklist` is the simplest reasonable fallback. For DebugBench / Mini-nightmare-like tasks, however, even the best current conditions provide only partial gains.

### Other Slices Under the Two-Layer Framing

> **human-easy / Easy (16):** Mistral `act_only = 87.5%`, so the most sensible choice remains a cheap baseline rather than extra process control.
>
> **human-easy / Intermediate (8):** these bugs are easier than HEAD but not trivially so. Mistral rises from `act_only 25.0%` to `reflexion 50.0%`, which makes this slice look like a near-neighbor of HEAD.
>
> **human-difficult (46):** this is a separate axis. It captures bugs that require deeper reasoning for humans as well, not just bugs that are anomalously hard for AI.

### Efficiency and Core Conclusion

> **Token use:** on HEAD20, Mistral's current matched best conditions are `react + early_stop_restart` (`45%`, `~36.8K`) and `reflexion + self_consistency` (`45%`, `~37.3K`), both clearly above `act_only baseline = 25%`. This suggests that the gain comes from better budget slicing rather than longer single trajectories.
>
> **Main conclusion:** `(1)` protocol effects still vary with difficulty, but plain protocol ordering on HEAD is not stable enough to be the main story; `(2)` strategy effects depend strongly on protocol; `(3)` the top-performing conditions share the same mechanism, namely **splitting the budget into shorter, more independent attempts**; `(4)` the gains of these top conditions are concentrated in `QuixBugs 7/9`, while remaining limited on `DebugBench 2/7` and `Mini-nightmare 0/4`.

### Recommended Configuration Matrix

| Slice | Model | Recommended Protocol | Recommended Strategy | Reason |
|------------|------|---------------------|----------------------|------|
| **human-easy / HEAD** | Mistral | **react or reflexion** | prioritize `early_stop_restart`; then `self_consistency` | current matched best is `react + early_stop_restart = 45%`, tied with `reflexion + self_consistency = 45%` |
| **human-easy / Intermediate** | Mistral | **reflexion** | start with baseline | `50%`, clearly above act_only `25%` |
| **human-easy / Easy** | Mistral | **act_only** | baseline | already `87.5%`; lowest-cost default |

> **Practical guidance:** decide first where a bug falls in the two-layer classification, then choose protocol and strategy. `HEAD` and `Intermediate` both belong to `human-easy`, but `HEAD` calls for strategies that **cut off single bad trajectories**, whereas `human-difficult` is a different kind of problem entirely.

---

## Step 4: Summary

### Answer to the Core Question

> **1. Surface cause — abnormal duration.** HEAD becomes expensive mainly because runs last longer, not because each turn is dramatically more expensive. Under act_only, Mistral often consumes most of the budget and still fails.
>
> **2. Deeper cause — two-dimensional difficulty.** The trajectory analysis and the full hint study agree: agents often start editing relatively early, but converting localization into a correct patch depends strongly on task structure. On QuixBugs, `L4` lifts Mistral from `1/9` to `7/9`; on DebugBench and Mini-nightmare, `L2/L4` barely moves failure rates. This means **repair generation** is the more general bottleneck, and localization help is subtype-dependent.
>
> **3. Protocol-difficulty interaction.** Inside `human-easy`, protocol gains show a clear gradient: on `Easy`, act_only is enough; on `Intermediate`, reflexion is currently the best simple choice; on `HEAD`, plain protocol ordering is not stable, and the decisive factor is whether strategy shortens bad trajectories.
>
> **4. The two-layer framing clarifies the role of HEAD.** HEAD is not a generic “hard bug” category. It is the anomalous left tail within `human-easy`. `Intermediate` shows that human-easy bugs themselves already form a gradient, while `human-difficult` reminds us not to collapse “hard for humans” and “anomalously hard for AI” into the same bucket.
>
> **5. Strategy effects depend on protocol and subtype.** On the current matched HEAD20, Mistral's best results come from **react + early_stop_restart** and **reflexion + self_consistency** (both `45%`), but both mainly improve `QuixBugs 7/9`, while reaching only `DebugBench 2/7` and `Mini-nightmare 0/4`. The right intervention is therefore not a universal protocol, but a **model × protocol × strategy × subtype** choice.

### The Nature of HEAD

> HEAD is the **most anomalous** subset inside `human-easy` bugs (current definition: human-easy + Mistral 5-seed act_only pass rate `<= 20%`, `n = 20`). It is not a stand-in for all difficult bugs. Instead, it acts as a **diagnostic lens on the AI capability boundary inside low-barrier human tasks**: strong models still solve many of them at elevated cost, while weak models mostly fail under an unguided baseline. An independent small-model recheck supports this interpretation: `api-llama-4-scout` also reaches only **8/20 (40%)** on the same HEAD20 under `act_only`, with **0/4** on Mini-nightmare. The matched rerun further shows that the key question on HEAD is not “which single protocol is correct,” but **whether bad trajectories are allowed to persist too long**.

### Limitations and Future Work

> **Limitations:** `(1)` the two-layer classification still depends on human-easy annotation and Mistral act_only 5-seed; although the new `Llama-4-Scout` recheck shows that the same HEAD20 remains difficult for another small-model family (`8/20`), this is still not enough to make HEAD a fully model-independent ontology; `(2)` `Intermediate` has only `8` bugs and `HEAD` only `20`, so ranking confidence is still limited by single-seed protocol×strategy data; `(3)` the completed HEAD20 hint study is still single-seed and highly subtype-heterogeneous; `(4)` the matched rerun and Reflexion ablation are still affected by API instability, so mechanism identification still needs multi-repeat / multi-seed validation; `(5)` the current analysis already suggests at least two HEAD subtypes, but there is not yet an automatic and reproducible subtype assignment rule.
>
> **Future work:** `(1)` run multi-seed hint and protocol×strategy validation on the current HEAD20; `(2)` extend the hint study from pass rates to cost/turn reduction; `(3)` run multi-repeat / multi-seed multiple-attempt ablations; `(4)` explain why `L4` gains are concentrated in QuixBugs; `(5)` study adaptive `(protocol × strategy × hint)` selection.

---

## Contributions

| # | Contribution | Narrative role |
|---|-------------|----------------|
| 1 | **HEAD discovery and definition** | §1: a two-layer framing with `human-easy / human-difficult` plus `Easy / Intermediate / HEAD` inside `human-easy`; HEAD is defined as human-easy with Mistral act_only 5-seed `<= 1/5` |
| 2 | **Multi-dimensional root-cause analysis of HEAD** | §2a-2b: protocol-difficulty interaction, blind patching vs excess exploration, and the Edit->Fix gap |
| 3 | **Hint-study causal validation** | §2d: full HEAD20 results of `L2 25%`, `L4 40%`, and `120B L2 100%`; gains are concentrated in QuixBugs, showing that repair generation is the more general bottleneck |
| 4 | **Multiple-attempt mechanism analysis** | §2c: matched ablation gives `react = 40%`, `reflexion baseline = 40%`, `Ep1-only = 35%`, `restart-without-reflection = 25%`; Episode 2 is not a stable gain source, and the mechanism is best described as trajectory-duration management |
| 5 | **Protocol×strategy dependence of interventions** | §3: matched HEAD20 rerun shows that Mistral's best conditions are `react + early_stop_restart` and `reflexion + self_consistency` (both `45%`); strategy gains depend strongly on protocol |
| 6 | **Subtype analysis inside HEAD** | §2d: HEAD is a mixture of localization-sensitive (QuixBugs) and structure-sensitive (DebugBench / Mini-nightmare) tasks |
| 7 | **Configuration guidance** | §3: a practical recommendation matrix derived from the two-layer classification |


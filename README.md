# HEAD20 Debugging-Agent Study

This is a cleaned release of the project focused on the **current HEAD20 paper narrative**.

It keeps the active materials needed for the current write-up:

- the two-layer classification
- the current Chinese and English narratives
- the active report artifacts used by the paper
- the matched Mistral HEAD20 rerun
- the Reflexion mechanism ablation
- the Llama-4-Scout HEAD20 recheck
- the rehydrated local task copies used by active scripts

It intentionally excludes historical or superseded material such as:

- `docs/archive/`
- `scripts/legacy/`
- old broad result dumps not used by the current narrative
- unreadable cloud-placeholder source data under `tasks/` and `external_data/`

## Start Here

- Current Chinese narrative:
  [docs/expected_paper_narrative.md](/Users/yvette/Desktop/UCSD/291a/final_project_release_v1/docs/expected_paper_narrative.md)
- Current English narrative:
  [docs/expected_paper_narrative_en.md](/Users/yvette/Desktop/UCSD/291a/final_project_release_v1/docs/expected_paper_narrative_en.md)
- Docs index:
  [docs/README.md](/Users/yvette/Desktop/UCSD/291a/final_project_release_v1/docs/README.md)
- Report index:
  [docs/report/README.md](/Users/yvette/Desktop/UCSD/291a/final_project_release_v1/docs/report/README.md)

## Repository Layout

```text
agent_local/            active local agent implementation
docs/                   current narratives and report artifacts
results/                active raw result subsets used by the paper
scripts/                active scripts only
tasks_local/            readable local task copies used by active runs
run_experiment.py       main experiment runner
```

## Included Active Reports

- `docs/report/merged_5seed_act_only_baseline.json`
- `docs/report/two_layer_classification.json`
- `docs/report/two_layer_classification.md`
- `docs/report/head_20_from_existing.json`
- `docs/report/head_20_hint_study_report.md`
- `docs/report/head_20_mistral_matched_protocol_strategy.json`
- `docs/report/head_20_mistral_matched_protocol_strategy.md`
- `docs/report/reflexion_mechanism_ablation_head20.json`
- `docs/report/reflexion_mechanism_ablation_head20.md`
- `docs/report/head20_llama4scout_recheck.md`

## Included Active Raw Results

- `results/rerun_head20_mistral_protocol_strategy/`
- `results/ablation_reflexion_mechanism/`
- `results/head20_llama4scout_act_only/`

## Included Active Scripts

- `scripts/aggregate_head_results.py`
- `scripts/analyze_head20_hint_study.py`
- `scripts/head_20_data_from_existing.py`
- `scripts/rehydrate_missing_head20_tasks.py`
- `scripts/run_head20_missing_hints.py`
- `scripts/run_mistral_head20_matched_protocol_strategy.py`
- `scripts/run_reflexion_mechanism_ablation.py`

## Notes

- Active scripts prefer `tasks_local/` and `agent_local/` so that this cleaned release remains usable without the broken cloud-backed originals.
- This release is intended for paper reading, result inspection, and reproduction of the active HEAD20 workflow, not for preserving every historical artifact produced during the project.

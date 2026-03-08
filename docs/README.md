# Docs Guide

This cleaned release keeps only the documentation that supports the **current HEAD20 workflow**.

## Included Files

- `docs/expected_paper_narrative.md`
  Current Chinese paper narrative and source of truth.
- `docs/expected_paper_narrative_en.md`
  Current English narrative synced to the latest active conclusions.
- `docs/bug_annotations_v2.json`
  Human difficulty labels.
- `docs/report/`
  Current generated report artifacts used by the paper.

## Canonical Report Files

- `docs/report/merged_5seed_act_only_baseline.json`
  Canonical 5-seed Mistral act_only aggregate.
- `docs/report/two_layer_classification.json`
- `docs/report/two_layer_classification.md`
  Current two-layer classification outputs.
- `docs/report/head_20_from_existing.json`
  HEAD20 trajectory and hint aggregates.
- `docs/report/head_20_hint_study_report.md`
  HEAD20 hint-study write-up.
- `docs/report/head_20_mistral_matched_protocol_strategy.json`
- `docs/report/head_20_mistral_matched_protocol_strategy.md`
  Matched Mistral HEAD20 protocol×strategy rerun.
- `docs/report/reflexion_mechanism_ablation_head20.json`
- `docs/report/reflexion_mechanism_ablation_head20.md`
  Matched mechanism ablation.
- `docs/report/head20_llama4scout_recheck.md`
  Cross-model recheck with `api-llama-4-scout`.

## Excluded on Purpose

This release does not include historical narrative drafts, old 23-HEAD materials, or archived reports. It is intended to reflect only the current active story.

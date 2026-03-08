# Two-Layer Classification Summary

## Definitions

- Layer 1: `human-easy` vs `human-difficult`, from `docs/bug_annotations_v2.json`.
- Layer 2: within `human-easy`, split by Mistral act_only 5-seed pass count.
- `Easy`: at least 3/5 passes.
- `Intermediate`: exactly 2/5 passes.
- `HEAD`: at most 1/5 passes.

## Counts

| Slice | Count |
|---|---:|
| `human-easy` | 44 |
| `human-difficult` | 46 |
| `human-easy / Easy` | 16 |
| `human-easy / Intermediate` | 8 |
| `human-easy / HEAD` | 20 |

## Canonical Files

- Classification source: `docs/report/merged_5seed_act_only_baseline.json`
- Protocol/strategy summary on HEAD20: `docs/report/head_20_protocol_strategy.json`

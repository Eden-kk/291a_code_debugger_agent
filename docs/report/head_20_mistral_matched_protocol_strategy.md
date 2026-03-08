# Matched Mistral HEAD20 Protocol×Strategy Rerun

## Experimental Design

- Task set: HEAD20 from `merged_5seed_act_only_baseline.json` (20 tasks)
- Model: `api-mistral-small-3.2-2506`
- Seed: `42`
- Budget: `50000` tokens, `25` max turns
- Hint level: `h0`
- Conditions: `3 protocols × 4 strategies = 12`
- Raw results are stored under `results/rerun_head20_mistral_protocol_strategy/` and excluded from canonical aggregates by default.

## Status

- Complete: all 240 condition-task pairs are present.

## Summary Table

| Protocol | Strategy | Pass | Pass % | Avg tokens | Avg turns |
|---|---|---:|---:|---:|---:|
| `react` | `early_stop_restart` | 9/20 | 45.0% | 36770.1 | 15.7 |
| `reflexion` | `self_consistency` | 9/20 | 45.0% | 37287.6 | 19.3 |
| `reflexion` | `early_stop_restart` | 8/20 | 40.0% | 39142.8 | 17.1 |
| `react` | `self_consistency` | 8/20 | 40.0% | 42328.6 | 21.1 |
| `act_only` | `checklist` | 7/20 | 35.0% | 38778.3 | 13.2 |
| `react` | `baseline` | 7/20 | 35.0% | 39140.8 | 12.6 |
| `act_only` | `early_stop_restart` | 7/20 | 35.0% | 41824.8 | 19.3 |
| `reflexion` | `baseline` | 6/20 | 30.0% | 39581.9 | 13.8 |
| `act_only` | `baseline` | 5/20 | 25.0% | 41638.1 | 14.2 |
| `react` | `checklist` | 5/20 | 25.0% | 44034.3 | 13.9 |
| `act_only` | `self_consistency` | 5/20 | 25.0% | 45586.2 | 23.9 |
| `reflexion` | `checklist` | 4/20 | 20.0% | 45406.2 | 15.3 |

## Family Breakdown

| Protocol | Strategy | DebugBench | Mini-nightmare | QuixBugs |
|---|---|---:|---:|---:|
| `react` | `early_stop_restart` | 2/7 | 0/4 | 7/9 |
| `reflexion` | `self_consistency` | 2/7 | 0/4 | 7/9 |
| `reflexion` | `early_stop_restart` | 1/7 | 0/4 | 7/9 |
| `react` | `self_consistency` | 2/7 | 0/4 | 6/9 |
| `act_only` | `checklist` | 0/7 | 1/4 | 6/9 |
| `react` | `baseline` | 1/7 | 0/4 | 6/9 |
| `act_only` | `early_stop_restart` | 2/7 | 0/4 | 5/9 |
| `reflexion` | `baseline` | 1/7 | 0/4 | 5/9 |
| `act_only` | `baseline` | 0/7 | 0/4 | 5/9 |
| `react` | `checklist` | 0/7 | 0/4 | 5/9 |
| `act_only` | `self_consistency` | 0/7 | 0/4 | 5/9 |
| `reflexion` | `checklist` | 0/7 | 0/4 | 4/9 |

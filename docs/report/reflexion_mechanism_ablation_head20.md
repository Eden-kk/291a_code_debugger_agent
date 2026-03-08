# Reflexion Mechanism Ablation on HEAD-20

## Experimental Design

- Task set: current HEAD-20 from `merged_5seed_act_only_baseline.json` (20 tasks)
- Model: `api-mistral-small-3.2-2506`
- Seed: `42`
- Budget: `50000` tokens, `25` max turns per episode
- Hint level: `h0`
- All four conditions were run in the same batch to avoid comparing new ablations against old baselines.

## Conditions

- `react_baseline`: Standard react baseline used as the direct comparison point for Reflexion Ep1.
- `reflexion_baseline`: Current reflexion baseline: Ep1 + generated reflection + clean Ep2 restart.
- `reflexion_ep1_only`: Stop after Episode 1 while keeping the reflexion prompt unchanged.
- `restart_without_reflection`: Run Ep2 after a clean restart, but inject no reflection text.

## Summary

| Condition | Pass | Pass % | Avg tokens |
|---|---:|---:|---:|
| `react_baseline` | 8/20 | 40.0% | 38305.7 |
| `reflexion_ep1_only` | 7/20 | 35.0% | 37813.2 |
| `reflexion_baseline` | 8/20 | 40.0% | 37229.6 |
| `restart_without_reflection` | 5/20 | 25.0% | 46283.6 |

## Mechanism Readout

- Ep1-only minus react baseline: `-5.0 pp`
- Reflexion baseline minus react baseline: `0.0 pp`
- Baseline minus Ep1-only: `5.0 pp`
- Baseline minus restart-without-reflection: `15.0 pp`
- Ep2 rescues in baseline: `0` -> []
- Ep2 rescues in restart-without-reflection: `0` -> []
- Baseline success but restart-without-reflection fail (5): ['debugbench_031_next_greater_element_i', 'quixbugs_find_first_in_sorted', 'quixbugs_find_in_sorted', 'quixbugs_mergesort', 'quixbugs_to_base']
- Restart-without-reflection success but Ep1-only fail (1): ['quixbugs_quicksort']
- Ep1-only success but react fail (1): ['debugbench_012_corporate_flight_bookings']
- React success but Ep1-only fail (2): ['quixbugs_mergesort', 'quixbugs_quicksort']
- Baseline success but react fail (1): ['quixbugs_find_in_sorted']
- React success but baseline fail (1): ['quixbugs_next_palindrome']

## Interpretation

- `react_baseline` and `reflexion_baseline` tie at `8/20`, so this matched batch does not reproduce a reflexion-over-react aggregate advantage.
- `reflexion_ep1_only` lands at `7/20`, only one task below `react_baseline`; the two conditions trade wins rather than showing a stable ordering.
- Neither two-episode condition produces an `Ep1 fail -> Ep2 pass` rescue, so Episode 2 is not a demonstrated positive contributor in this batch.
- `restart_without_reflection` is the weakest condition (`5/20`) and also the most expensive, which argues against clean restart alone as the source of any reflexion gain.
- The only baseline-vs-react differences are task-level swaps inside QuixBugs, not a family-level shift: both solve `1/7` DebugBench, `0/4` Mini-nightmare, and `7/9` QuixBugs.

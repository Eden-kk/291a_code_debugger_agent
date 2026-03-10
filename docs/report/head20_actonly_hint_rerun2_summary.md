# HEAD20 Act-Only Hint Reruns

Fresh complete reruns over the canonical HEAD20 subset under `act_only + baseline`
with hint levels `L0 / L2 / L4`.

## Overall pass counts

| Batch | L0 | L2 | L4 |
|---|---:|---:|---:|
| Mistral rerun 1 | 8/20 | 6/20 | 9/20 |
| Mistral rerun 2 | 5/20 | 6/20 | 6/20 |
| 120B rerun 2 | 19/20 | 18/20 | 20/20 |

## Family breakdown

### Mistral rerun 1

| Family | L0 | L2 | L4 |
|---|---:|---:|---:|
| DebugBench | 2/7 | 0/7 | 1/7 |
| Mini-nightmare | 1/4 | 0/4 | 0/4 |
| QuixBugs | 5/9 | 6/9 | 8/9 |

### Mistral rerun 2

| Family | L0 | L2 | L4 |
|---|---:|---:|---:|
| DebugBench | 0/7 | 0/7 | 0/7 |
| Mini-nightmare | 0/4 | 0/4 | 0/4 |
| QuixBugs | 5/9 | 6/9 | 6/9 |

### 120B rerun 2

| Family | L0 | L2 | L4 |
|---|---:|---:|---:|
| DebugBench | 7/7 | 6/7 | 7/7 |
| Mini-nightmare | 3/4 | 4/4 | 4/4 |
| QuixBugs | 9/9 | 8/9 | 9/9 |

## Interpretation

- The two Mistral reruns are directionally consistent only at a high level:
  QuixBugs benefits most, while DebugBench and Mini-nightmare remain difficult.
- The aggregate Mistral pass counts are unstable across single reruns:
  `8/20, 6/20, 9/20` versus `5/20, 6/20, 6/20`.
- The strongest stable qualitative pattern is therefore family asymmetry, not a
  precise monotonic aggregate gain from `L0` to `L4`.
- The 120B rerun is substantially more stable and near-saturated:
  `19/20, 18/20, 20/20`.

## Result directories

- `results/rerun_head20_mistral_actonly_hints/`
- `results/rerun2_head20_mistral_actonly_hints/`
- `results/rerun2_head20_120b_actonly_hints/`

# HEAD-20 Independent Recheck with Llama-4-Scout

**Date:** 2026-03-08  
**Task set:** current HEAD-20 from `two_layer_classification.json`  
**Model:** `api-llama-4-scout`  
**Protocol / strategy:** `act_only` + `baseline`  
**Seed:** `42`  
**Budget:** `50000` tokens, `25` max turns  
**Output directory:** `results/head20_llama4scout_act_only/`

## Note on compatibility

Initial Scout runs were not usable because the model emitted bracketed pseudo-tool calls such as `[run_tests()]` rather than formal API `tool_calls`.  
On 2026-03-08 the fallback parser in `agent/runner.py` and `agent_local/runner.py` was extended to accept this format. The results below are from the **post-fix rerun** and should be treated as the valid Scout calibration/recheck.

## Summary

| Model | Pass | Pass % | Avg tokens |
|---|---:|---:|---:|
| `api-llama-4-scout` | 8/20 | 40.0% | 36,260.1 |

## Family Breakdown

| Family | Pass | Pass % | Avg tokens |
|---|---:|---:|---:|
| DebugBench | 3/7 | 42.9% | 35,038.1 |
| Mini-nightmare | 0/4 | 0.0% | 53,539.5 |
| QuixBugs | 5/9 | 55.6% | 29,530.7 |

## Successful Tasks

- `debugbench_012_corporate_flight_bookings`
- `debugbench_031_next_greater_element_i`
- `debugbench_037_minimum_bit_flips_to_convert_number`
- `quixbugs_is_valid_parenthesization`
- `quixbugs_mergesort`
- `quixbugs_quicksort`
- `quixbugs_to_base`
- `quixbugs_wrap`

## Interpretation

- **Scout falls inside the HEAD band.** `8/20 = 40%` is far below the strong-model regime and far above the near-collapse behavior seen from overly weak candidates such as `nova-2-lite`.
- **This is an independent recheck, not a redefinition.** HEAD is still defined relative to Mistral Small; Scout is used here only to test whether the same HEAD-20 subset also remains difficult for a different model family.
- **The core pattern reproduces.** Scout is not trivially solving HEAD-20. Its failures are typically long and expensive, with repeated edits/tests rather than immediate termination, which is consistent with genuine debugging difficulty rather than tool-call incompatibility.
- **Mini-nightmare remains the hardest subfamily.** Scout solves `0/4` there while still reaching `42.9%` on DebugBench and `55.6%` on QuixBugs.

## Practical takeaway

For the current paper narrative, Scout can support a restrained cross-model claim:

> The Mistral-defined HEAD-20 subset is not only difficult for Mistral Small. After fixing tool-call compatibility, `api-llama-4-scout` also reaches only `8/20 (40%)` under `act_only`, with complete failure on Mini-nightmare.

This supports **cross-model robustness of the HEAD subset** without changing the canonical Mistral-based definition.

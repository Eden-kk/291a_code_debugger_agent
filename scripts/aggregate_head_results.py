#!/usr/bin/env python3
"""
Build the current classification/report artifacts from existing data.

Outputs:
1. docs/report/two_layer_classification.json
2. docs/report/two_layer_classification.md
3. docs/report/head_20_protocol_strategy.json
"""
import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
MERGED = PROJECT_ROOT / "docs" / "report" / "merged_5seed_act_only_baseline.json"
ANNOTATIONS = PROJECT_ROOT / "docs" / "bug_annotations_v2.json"
OUT_DIR = PROJECT_ROOT / "docs" / "report"


def _annotation_map() -> dict[str, dict]:
    data = json.loads(ANNOTATIONS.read_text())
    return data["annotations"]


def _model_sort_key(model: str) -> tuple[int, str]:
    lower = model.lower()
    if "120b" in lower:
        return (0, model)
    if "mistral" in lower:
        return (1, model)
    return (2, model)


def _is_excluded_result(path: Path) -> bool:
    return any(
        tag in part
        for part in path.parts
        for tag in ("ablation", "rerun", "time_control")
    )


def _write_two_layer_markdown(two_layer: dict) -> None:
    out = OUT_DIR / "two_layer_classification.md"
    lines: list[str] = []
    w = lines.append

    w("# Two-Layer Classification Summary")
    w("")
    w("## Definitions")
    w("")
    w("- Layer 1: `human-easy` vs `human-difficult`, from `docs/bug_annotations_v2.json`.")
    w("- Layer 2: within `human-easy`, split by Mistral act_only 5-seed pass count.")
    w("- `Easy`: at least 3/5 passes.")
    w("- `Intermediate`: exactly 2/5 passes.")
    w("- `HEAD`: at most 1/5 passes.")
    w("")
    w("## Counts")
    w("")
    w("| Slice | Count |")
    w("|---|---:|")
    w(f"| `human-easy` | {two_layer['counts']['human_easy']} |")
    w(f"| `human-difficult` | {two_layer['counts']['human_difficult']} |")
    w(f"| `human-easy / Easy` | {two_layer['counts']['easy']} |")
    w(f"| `human-easy / Intermediate` | {two_layer['counts']['intermediate']} |")
    w(f"| `human-easy / HEAD` | {two_layer['counts']['head']} |")
    w("")
    w("## Canonical Files")
    w("")
    w("- Classification source: `docs/report/merged_5seed_act_only_baseline.json`")
    w("- Protocol/strategy summary on HEAD20: `docs/report/head_20_protocol_strategy.json`")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    merged = json.loads(MERGED.read_text())
    passes_5 = merged["per_task_passes_5seed"]
    head_set = set(merged["head_bugs"])
    ann = _annotation_map()
    human_easy = sorted(k for k, v in ann.items() if v["human_difficulty"] == "human-easy")
    human_difficult = sorted(k for k, v in ann.items() if v["human_difficulty"] == "human-difficult")
    head_bugs = sorted(head_set)

    easy_bugs = sorted(
        task_id for task_id in human_easy
        if passes_5.get(task_id, 0) >= 3
    )
    intermediate_bugs = sorted(
        task_id for task_id in human_easy
        if passes_5.get(task_id, 0) == 2
    )

    two_layer = {
        "metadata": {
            "human_difficulty_source": str(ANNOTATIONS.relative_to(PROJECT_ROOT)),
            "ai_difficulty_source": str(MERGED.relative_to(PROJECT_ROOT)),
            "head_definition": merged["head_definition"],
        },
        "layer1": {
            "human_easy": human_easy,
            "human_difficult": human_difficult,
        },
        "layer2_within_human_easy": {
            "easy": easy_bugs,
            "intermediate": intermediate_bugs,
            "head": head_bugs,
        },
        "counts": {
            "human_easy": len(human_easy),
            "human_difficult": len(human_difficult),
            "easy": len(easy_bugs),
            "intermediate": len(intermediate_bugs),
            "head": len(head_bugs),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "two_layer_classification.json").write_text(
        json.dumps(two_layer, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _write_two_layer_markdown(two_layer)

    latest_results: dict[tuple[str, str, str, str], tuple[str, tuple[str, str, str, str, bool, int]]] = {}
    for jpath in RESULTS.rglob("*__*__*__h0__*.json"):
        if _is_excluded_result(jpath):
            continue
        try:
            d = json.loads(jpath.read_text())
            task_id = d.get("task_id")
            if task_id not in head_set:
                continue
            model = d.get("model", "")
            protocol = d.get("protocol", "")
            strategy = d.get("strategy", "")
            success = d.get("result", {}).get("success", False)
            tokens = d.get("result", {}).get("total_tokens", 0)
            stamp = d.get("timestamp") or jpath.name
            row = (task_id, model, protocol, strategy, success, tokens)
            key = (task_id, model, protocol, strategy)
            prev = latest_results.get(key)
            if prev is None or stamp > prev[0]:
                latest_results[key] = (stamp, row)
        except Exception:
            continue

    agg = defaultdict(lambda: {"pass": 0, "fail": 0, "sum_tokens": 0, "tasks": []})
    for _, (task_id, model, protocol, strategy, success, tokens) in latest_results.values():
        k = (model, protocol, strategy)
        agg[k]["pass" if success else "fail"] += 1
        agg[k]["sum_tokens"] += tokens
        agg[k]["tasks"].append(task_id)

    n_head = len(head_bugs)
    rows = []
    for (model, protocol, strategy), v in sorted(
        agg.items(),
        key=lambda item: (_model_sort_key(item[0][0]), item[0][1], item[0][2]),
    ):
        n = v["pass"] + v["fail"]
        pass_rate = v["pass"] / n * 100 if n else 0
        avg_tok = v["sum_tokens"] / n if n else 0
        rows.append({
            "model": model,
            "protocol": protocol,
            "strategy": strategy,
            "n": n,
            "pass": v["pass"],
            "fail": v["fail"],
            "pass_pct": round(pass_rate, 1),
            "avg_tokens": round(avg_tok, 0),
        })

    head_agg = {
        "head_tasks": head_bugs,
        "n_head": n_head,
        "source": "results/ (seed=42, h0 only)",
        "aggregates": rows,
    }
    (OUT_DIR / "head_20_protocol_strategy.json").write_text(
        json.dumps(head_agg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        "Two-layer counts:",
        two_layer["counts"]["human_easy"], "human-easy,",
        two_layer["counts"]["human_difficult"], "human-difficult,",
        two_layer["counts"]["easy"], "easy,",
        two_layer["counts"]["intermediate"], "intermediate,",
        two_layer["counts"]["head"], "HEAD",
    )
    print("HEAD sample:", head_bugs[:5], "..." if len(head_bugs) > 5 else "")
    print("\nHEAD (20) protocol+strategy aggregates (full coverage only):")
    for r in rows:
        print(f"  {r['model'][:20]:20} {r['protocol']:10} {r['strategy']:20} {r['pass']}/{r['n']} {r['pass_pct']:.1f}%  {r['avg_tokens']:.0f} tok")


if __name__ == "__main__":
    main()

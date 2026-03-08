#!/usr/bin/env python3
"""
Extract all HEAD-20–reproducible data from existing results/:
1. Hint study: L0/L2/L4 (Mistral), L0/L2 (120B) — report pass rates and list tasks missing L2/L4.
2. Reflexion Episode 1 vs 2: per-episode pass/fail for reflexion baseline on HEAD 20.
3. Trajectory / Edit→Fix: first_edit_turn, first_fix_turn, patch_attempt_count for HEAD 20.

Output: docs/report/head_20_from_existing.json + summary to stdout.
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"
OUT_DIR = PROJECT_ROOT / "docs" / "report"
MERGED_5SEED = PROJECT_ROOT / "docs" / "report" / "merged_5seed_act_only_baseline.json"


def _model_short(model: str) -> str:
    if not model:
        return "unknown"
    if "120b" in model.lower():
        return "120B"
    if "mistral" in model.lower():
        return "Mistral"
    return model


def _task_id_from_path(path: Path) -> str | None:
    """e.g. results/debugbench/logic_error/debugbench_004_reverse_bits__react__baseline__h0__*.json -> debugbench_004_reverse_bits"""
    name = path.name
    if "__" not in name:
        return None
    return name.split("__")[0]


def _is_excluded_result(path: Path) -> bool:
    return any(
        tag in part
        for part in path.parts
        for tag in ("ablation", "rerun", "time_control")
    )


def load_head_20() -> set[str]:
    data = json.loads(MERGED_5SEED.read_text())
    return set(data["head_bugs"])


def load_all_runs_for_tasks(task_ids: set[str]) -> list[dict]:
    """Load the latest run per (task_id, model, protocol, strategy, hint_level).

    Some configurations were rerun later. For HEAD-20 analysis we want the most
    recent result file rather than whichever file happens to be encountered
    first during directory traversal.
    """
    latest: dict[tuple, tuple[str, dict]] = {}
    for jpath in RESULTS.rglob("*.json"):
        if _is_excluded_result(jpath):
            continue
        try:
            d = json.loads(jpath.read_text())
        except Exception:
            continue
        tid = d.get("task_id") or _task_id_from_path(jpath)
        if tid not in task_ids:
            continue
        model = d.get("model", "")
        proto = d.get("protocol", "")
        strat = d.get("strategy", "baseline")
        hl = d.get("hint_level", 0)
        key = (tid, model, proto, strat, hl)
        d["_model_short"] = _model_short(model)
        stamp = d.get("timestamp") or jpath.name
        existing = latest.get(key)
        if existing is None or stamp > existing[0]:
            latest[key] = (stamp, d)
    return [item[1] for item in latest.values()]


def hint_on_head_20(runs: list[dict], head: set[str]) -> dict:
    """Hint study: react baseline only. L0/L2/L4 Mistral, L0/L2 120B."""
    react = [r for r in runs if r.get("protocol") == "react" and r.get("strategy") == "baseline"]
    by_key = defaultdict(list)  # (model_short, hint_level) -> list of runs (one per task)
    for r in react:
        if r["task_id"] not in head:
            continue
        k = (r["_model_short"], r.get("hint_level", 0))
        # dedupe by task: keep first
        if not any(x["task_id"] == r["task_id"] for x in by_key[k]):
            by_key[k].append(r)

    summary = {}
    for (model, hl), task_runs in sorted(by_key.items()):
        n = len(task_runs)
        pass_count = sum(1 for r in task_runs if r.get("result", {}).get("success"))
        summary[f"{model}_L{hl}"] = {
            "n": n,
            "pass": pass_count,
            "pass_pct": round(pass_count / n * 100, 1) if n else 0,
            "task_ids": sorted(r["task_id"] for r in task_runs),
        }

    # Which HEAD tasks have L2/L4 for Mistral and L2 for 120B?
    mistral_l0 = {r["task_id"] for r in by_key.get(("Mistral", 0), [])}
    mistral_l2 = {r["task_id"] for r in by_key.get(("Mistral", 2), [])}
    mistral_l4 = {r["task_id"] for r in by_key.get(("Mistral", 4), [])}
    b120_l0 = {r["task_id"] for r in by_key.get(("120B", 0), [])}
    b120_l2 = {r["task_id"] for r in by_key.get(("120B", 2), [])}

    missing_mistral_l2 = head - mistral_l2
    missing_mistral_l4 = head - mistral_l4
    missing_120b_l2 = head - b120_l2

    return {
        "summary": summary,
        "n_head": len(head),
        "coverage": {
            "Mistral_L0": len(mistral_l0),
            "Mistral_L2": len(mistral_l2),
            "Mistral_L4": len(mistral_l4),
            "120B_L0": len(b120_l0),
            "120B_L2": len(b120_l2),
        },
        "missing_hint_runs": {
            "Mistral_L2": sorted(missing_mistral_l2),
            "Mistral_L4": sorted(missing_mistral_l4),
            "120B_L2": sorted(missing_120b_l2),
        },
    }


def reflexion_episodes_on_head_20(runs: list[dict], head: set[str]) -> dict:
    """Reflexion baseline (Mistral): Episode 1 vs Episode 2 pass/fail."""
    reflex = [
        r for r in runs
        if r.get("protocol") == "reflexion" and r.get("strategy") == "baseline"
        and r["_model_short"] == "Mistral" and r.get("task_id") in head
    ]
    # one run per task
    by_task = {}
    for r in reflex:
        tid = r["task_id"]
        if tid in by_task:
            continue
        by_task[tid] = r

    ep1_pass = ep2_pass = ep1_fail_ep2_pass = 0
    per_task = []
    for tid in sorted(by_task.keys()):
        r = by_task[tid]
        eps = r.get("episodes") or []
        e1 = eps[0] if len(eps) > 0 else {}
        e2 = eps[1] if len(eps) > 1 else {}
        s1 = e1.get("success", False)
        s2 = e2.get("success", False)
        per_task.append({"task_id": tid, "ep1_success": s1, "ep2_success": s2})
        if s1:
            ep1_pass += 1
        if s2:
            ep2_pass += 1
        if not s1 and s2:
            ep1_fail_ep2_pass += 1

    n = len(by_task)
    return {
        "n_tasks": n,
        "ep1_pass": ep1_pass,
        "ep2_pass": ep2_pass,
        "ep1_fail_ep2_pass": ep1_fail_ep2_pass,
        "ep1_pass_pct": round(ep1_pass / n * 100, 1) if n else 0,
        "ep2_pass_pct": round(ep2_pass / n * 100, 1) if n else 0,
        "per_task": per_task,
    }


def trajectory_edit_fix_on_head_20(runs: list[dict], head: set[str]) -> dict:
    """Cost metrics: first_edit_turn, first_fix_turn, patch_attempt_count for HEAD 20.
    By (model_short, protocol, strategy); h0 only.
    """
    h0 = [r for r in runs if r.get("hint_level", 0) == 0 and r.get("task_id") in head]
    by_key = defaultdict(list)
    for r in h0:
        k = (r["_model_short"], r.get("protocol"), r.get("strategy"))
        if not any(x["task_id"] == r["task_id"] for x in by_key[k]):
            by_key[k].append(r)

    rows = []
    for (model, protocol, strategy), task_runs in sorted(by_key.items()):
        n = len(task_runs)
        cm_list = [r.get("cost_metrics") or {} for r in task_runs]
        first_edits = [c.get("first_edit_turn") for c in cm_list if c.get("first_edit_turn") is not None]
        first_fixes = [c.get("first_fix_turn") for c in cm_list if c.get("first_fix_turn") is not None]
        patches = [c.get("patch_attempt_count", 0) for c in cm_list]
        tests = [c.get("test_run_count", 0) for c in cm_list]
        views = [c.get("file_view_count", 0) for c in cm_list]
        passes = sum(1 for r in task_runs if r.get("result", {}).get("success"))

        avg_fe = sum(first_edits) / len(first_edits) if first_edits else None
        avg_ff = sum(first_fixes) / len(first_fixes) if first_fixes else None
        avg_patch = sum(patches) / n if n else 0
        avg_tests = sum(tests) / n if n else 0
        avg_views = sum(views) / n if n else 0
        gaps = [first_fixes[i] - first_edits[i] for i in range(len(first_fixes))
                if first_fixes[i] is not None and i < len(first_edits) and first_edits[i] is not None]
        avg_gap = sum(gaps) / len(gaps) if gaps else None

        rows.append({
            "model": model,
            "protocol": protocol,
            "strategy": strategy,
            "n": n,
            "pass": passes,
            "avg_first_edit_turn": round(avg_fe, 1) if avg_fe is not None else None,
            "avg_first_fix_turn": round(avg_ff, 1) if avg_ff is not None else None,
            "avg_edit_fix_gap": round(avg_gap, 1) if avg_gap is not None else None,
            "avg_patch_attempt_count": round(avg_patch, 1),
            "avg_test_run_count": round(avg_tests, 1),
            "avg_file_view_count": round(avg_views, 1),
        })

    return {"by_config": rows}


def main():
    head = load_head_20()
    print(f"HEAD 20 tasks: {len(head)}")
    runs = load_all_runs_for_tasks(head)
    print(f"Loaded {len(runs)} runs for HEAD tasks (deduped per task×model×protocol×strategy×hint)")

    hint_data = hint_on_head_20(runs, head)
    ep_data = reflexion_episodes_on_head_20(runs, head)
    traj_data = trajectory_edit_fix_on_head_20(runs, head)

    out = {
        "head_20_tasks": sorted(head),
        "n_head": len(head),
        "hint_study": hint_data,
        "reflexion_episodes": ep_data,
        "trajectory_edit_fix": traj_data,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "head_20_from_existing.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {out_path}")

    # --- Summary ---
    print("\n--- Hint study (HEAD 20) ---")
    for k, v in hint_data["summary"].items():
        print(f"  {k}: {v['pass']}/{v['n']} ({v['pass_pct']}%)")
    print("  Coverage:", hint_data["coverage"])
    missing = hint_data["missing_hint_runs"]
    if any(missing[k] for k in missing):
        print("  Missing hint runs (need to run):", {k: len(missing[k]) for k in missing})

    print("\n--- Reflexion Episode 1 vs 2 (Mistral baseline, HEAD 20) ---")
    print(f"  Ep1 pass: {ep_data['ep1_pass']}/{ep_data['n_tasks']} ({ep_data['ep1_pass_pct']}%)")
    print(f"  Ep2 pass: {ep_data['ep2_pass']}/{ep_data['n_tasks']} ({ep_data['ep2_pass_pct']}%)")
    print(f"  Ep1 fail → Ep2 pass: {ep_data['ep1_fail_ep2_pass']}")

    print("\n--- Trajectory / Edit→Fix (HEAD 20, h0) ---")
    for row in traj_data["by_config"]:
        fe = row.get("avg_first_edit_turn")
        ff = row.get("avg_first_fix_turn")
        gap = row.get("avg_edit_fix_gap")
        print(f"  {row['model']} {row['protocol']} {row['strategy']}: n={row['n']} pass={row['pass']} "
              f"1st_edit={fe} 1st_fix={ff} gap={gap} avg_patch={row['avg_patch_attempt_count']}")


if __name__ == "__main__":
    main()

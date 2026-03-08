#!/usr/bin/env python3
"""Run a matched Mistral HEAD20 protocol×strategy batch and summarize it.

Purpose
-------
This rerun isolates the HEAD20 Mistral landscape from February-era heterogeneous
results. It evaluates the full 3 protocol × 4 strategy matrix on the current
HEAD20 set under one matched setup:

  - protocols: act_only, react, reflexion
  - strategies: baseline, checklist, early_stop_restart, self_consistency

Outputs
-------
Raw runs:
  results/rerun_head20_mistral_protocol_strategy/

Reports:
  docs/report/head_20_mistral_matched_protocol_strategy.json
  docs/report/head_20_mistral_matched_protocol_strategy.md

The raw-result directory name intentionally contains "rerun" so canonical
aggregate scripts exclude it by default.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_local.runner import AgentRunner
from agent_local.telemetry import save_result


MERGED_5SEED = PROJECT_ROOT / "docs" / "report" / "merged_5seed_act_only_baseline.json"
RESULTS_DIR = PROJECT_ROOT / "results" / "rerun_head20_mistral_protocol_strategy"
REPORT_JSON = PROJECT_ROOT / "docs" / "report" / "head_20_mistral_matched_protocol_strategy.json"
REPORT_MD = PROJECT_ROOT / "docs" / "report" / "head_20_mistral_matched_protocol_strategy.md"

MISTRAL_MODEL = "api-mistral-small-3.2-2506"
DEFAULT_BACKEND = "tritonai"
DEFAULT_SEED = 42
DEFAULT_MAX_TURNS = 25
DEFAULT_MAX_TOKENS = 50_000

PROTOCOLS = ["act_only", "react", "reflexion"]
STRATEGIES = ["baseline", "checklist", "early_stop_restart", "self_consistency"]


def load_head20_tasks() -> list[str]:
    data = json.loads(MERGED_5SEED.read_text())
    return sorted(data["head_bugs"])


def find_task_dir(task_id: str) -> str:
    for root_name in ("tasks_local", "tasks"):
        root = PROJECT_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("metadata.json"):
            if path.parent.name == task_id:
                return str(path.parent)
    raise FileNotFoundError(f"Task not found in tasks_local/ or tasks/: {task_id}")


def family_for_task(task_id: str) -> str:
    if task_id.startswith("debugbench_"):
        return "DebugBench"
    if task_id.startswith("mini_nightmare_"):
        return "Mini-nightmare"
    return "QuixBugs"


def load_existing_runs() -> dict[tuple[str, str, str], dict]:
    latest: dict[tuple[str, str, str], tuple[str, dict]] = {}
    if not RESULTS_DIR.exists():
        return {}
    for path in RESULTS_DIR.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        key = (data.get("task_id", ""), data.get("protocol", ""), data.get("strategy", "baseline"))
        stamp = data.get("timestamp") or path.name
        prev = latest.get(key)
        if prev is None or stamp > prev[0]:
            latest[key] = (stamp, data)
    return {key: val[1] for key, val in latest.items()}


def run_single(task_id: str, protocol: str, strategy: str, model: str, backend: str, seed: int,
               max_turns: int, max_tokens: int) -> dict:
    runner = AgentRunner(
        task_dir=find_task_dir(task_id),
        protocol=protocol,
        model=model,
        temperature=0.0,
        hint_level=0,
        max_turns=max_turns,
        max_total_tokens=max_tokens,
        strategy=strategy,
        seed=seed,
        backend=backend,
    )
    result = runner.run()
    result["matched_batch"] = "mistral_head20_protocol_strategy"
    result["matched_batch_description"] = "Matched Mistral HEAD20 protocol×strategy rerun"
    save_result(result, output_dir=str(RESULTS_DIR))
    return result


def build_report(existing: dict[tuple[str, str, str], dict], task_ids: list[str], model: str,
                 backend: str, seed: int, max_turns: int, max_tokens: int) -> dict:
    summaries = {}
    missing = []
    for protocol in PROTOCOLS:
        for strategy in STRATEGIES:
            rows = []
            for task_id in task_ids:
                run = existing.get((task_id, protocol, strategy))
                if run is None:
                    missing.append({"task_id": task_id, "protocol": protocol, "strategy": strategy})
                    continue
                rows.append(run)

            key = f"{protocol}::{strategy}"
            families = defaultdict(lambda: {"pass": 0, "n": 0})
            total_tokens = 0
            total_turns = 0
            pass_count = 0
            for run in rows:
                success = bool(run.get("result", {}).get("success"))
                task_id = run["task_id"]
                fam = family_for_task(task_id)
                families[fam]["n"] += 1
                families[fam]["pass"] += int(success)
                pass_count += int(success)
                total_tokens += run.get("result", {}).get("total_tokens", 0)
                total_turns += run.get("result", {}).get("total_turns", 0)

            n = len(rows)
            summaries[key] = {
                "protocol": protocol,
                "strategy": strategy,
                "n": n,
                "pass": pass_count,
                "fail": n - pass_count,
                "pass_pct": round(pass_count / n * 100, 1) if n else 0.0,
                "avg_tokens": round(total_tokens / n, 1) if n else 0.0,
                "avg_turns": round(total_turns / n, 1) if n else 0.0,
                "family_breakdown": {
                    fam: {
                        "pass": payload["pass"],
                        "n": payload["n"],
                        "pass_pct": round(payload["pass"] / payload["n"] * 100, 1) if payload["n"] else 0.0,
                    }
                    for fam, payload in sorted(families.items())
                },
            }

    ranking = sorted(
        summaries.values(),
        key=lambda row: (-row["pass_pct"], row["avg_tokens"], row["protocol"], row["strategy"]),
    )
    return {
        "metadata": {
            "task_ids": task_ids,
            "n_tasks": len(task_ids),
            "model": model,
            "backend": backend,
            "seed": seed,
            "max_turns": max_turns,
            "max_total_tokens": max_tokens,
        },
        "summaries": summaries,
        "ranking": ranking,
        "missing": missing,
    }


def write_markdown_report(report: dict) -> None:
    meta = report["metadata"]
    lines: list[str] = []
    w = lines.append

    w("# Matched Mistral HEAD20 Protocol×Strategy Rerun")
    w("")
    w("## Experimental Design")
    w("")
    w(f"- Task set: HEAD20 from `merged_5seed_act_only_baseline.json` ({meta['n_tasks']} tasks)")
    w(f"- Model: `{meta['model']}`")
    w(f"- Seed: `{meta['seed']}`")
    w(f"- Budget: `{meta['max_total_tokens']}` tokens, `{meta['max_turns']}` max turns")
    w("- Hint level: `h0`")
    w("- Conditions: `3 protocols × 4 strategies = 12`")
    w("- Raw results are stored under `results/rerun_head20_mistral_protocol_strategy/` and excluded from canonical aggregates by default.")
    w("")
    if report["missing"]:
        w("## Status")
        w("")
        w(f"- Incomplete: {len(report['missing'])} condition-task pairs still missing.")
        w("")
    else:
        w("## Status")
        w("")
        w("- Complete: all 240 condition-task pairs are present.")
        w("")

    w("## Summary Table")
    w("")
    w("| Protocol | Strategy | Pass | Pass % | Avg tokens | Avg turns |")
    w("|---|---|---:|---:|---:|---:|")
    for row in report["ranking"]:
        w(
            f"| `{row['protocol']}` | `{row['strategy']}` | "
            f"{row['pass']}/{row['n']} | {row['pass_pct']}% | {row['avg_tokens']} | {row['avg_turns']} |"
        )
    w("")
    w("## Family Breakdown")
    w("")
    w("| Protocol | Strategy | DebugBench | Mini-nightmare | QuixBugs |")
    w("|---|---|---:|---:|---:|")
    for row in report["ranking"]:
        fam = row["family_breakdown"]
        dbg = fam.get("DebugBench", {"pass": 0, "n": 0})
        mini = fam.get("Mini-nightmare", {"pass": 0, "n": 0})
        quix = fam.get("QuixBugs", {"pass": 0, "n": 0})
        w(
            f"| `{row['protocol']}` | `{row['strategy']}` | "
            f"{dbg['pass']}/{dbg['n']} | {mini['pass']}/{mini['n']} | {quix['pass']}/{quix['n']} |"
        )
    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run matched Mistral HEAD20 protocol×strategy rerun.")
    parser.add_argument("--protocol", action="append", choices=PROTOCOLS, help="Restrict to one or more protocols.")
    parser.add_argument("--strategy", action="append", choices=STRATEGIES, help="Restrict to one or more strategies.")
    parser.add_argument("--task", action="append", help="Restrict to one or more task ids.")
    parser.add_argument("--model", default=MISTRAL_MODEL)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--max-total-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    task_ids = args.task or load_head20_tasks()
    protocols = args.protocol or PROTOCOLS
    strategies = args.strategy or STRATEGIES
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    existing = load_existing_runs()
    plan = []
    for protocol in protocols:
        for strategy in strategies:
            for task_id in task_ids:
                if (task_id, protocol, strategy) not in existing:
                    plan.append((task_id, protocol, strategy))

    print(f"Matched rerun target: {len(task_ids)} tasks × {len(protocols)} protocols × {len(strategies)} strategies")
    print(f"Missing executions in this scope: {len(plan)}")
    if args.dry_run:
        for task_id, protocol, strategy in plan:
            print(f"  {task_id}  {protocol} + {strategy}")
        return

    t0 = time.time()
    for idx, (task_id, protocol, strategy) in enumerate(plan, 1):
        elapsed = time.time() - t0
        eta = elapsed / max(idx - 1, 1) * (len(plan) - idx + 1)
        print(
            f"[{idx:03d}/{len(plan)}] ({elapsed:.0f}s elapsed, ETA {eta:.0f}s) "
            f"{task_id}  {protocol} + {strategy}"
        )
        sys.stdout.flush()
        result = run_single(
            task_id=task_id,
            protocol=protocol,
            strategy=strategy,
            model=args.model,
            backend=args.backend,
            seed=args.seed,
            max_turns=args.max_turns,
            max_tokens=args.max_total_tokens,
        )
        success = result.get("result", {}).get("success")
        tokens = result.get("result", {}).get("total_tokens")
        turns = result.get("result", {}).get("total_turns")
        print(f"  {'PASS' if success else 'FAIL'}  turns={turns}  tokens={tokens}")
        sys.stdout.flush()

    report = build_report(
        existing=load_existing_runs(),
        task_ids=task_ids,
        model=args.model,
        backend=args.backend,
        seed=args.seed,
        max_turns=args.max_turns,
        max_tokens=args.max_total_tokens,
    )
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_markdown_report(report)
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()

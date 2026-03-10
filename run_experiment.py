#!/usr/bin/env python3
"""Entry point for running debugging-agent experiments.

Usage examples
--------------
# ── TritonAI backend (default) ──
python run_experiment.py --task head_001_off_by_one --protocol react
python run_experiment.py --all --protocol act_only react reflexion

# ── With strategy (Phase 4) ──
python run_experiment.py --all --protocol react --strategy checklist
python run_experiment.py --all --protocol react --strategy early_stop_restart
python run_experiment.py --all --protocol react --strategy self_consistency

# ── Minimal intervention study (Phase 3) ──
python run_experiment.py --task head_001_off_by_one --protocol react --hint-levels 0 1 2 3 4

# ── Multiple repetitions ──
python run_experiment.py --task head_001_off_by_one --protocol react --repeat 3
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict

try:
    from agent.runner import AgentRunner
    from agent.telemetry import save_result
except (ModuleNotFoundError, OSError, TimeoutError):
    from agent_local.runner import AgentRunner
    from agent_local.telemetry import save_result


PROJECT_ROOT = os.path.dirname(__file__)
TASKS_DIR = os.path.join(PROJECT_ROOT, "tasks")
TASKS_LOCAL_DIR = os.path.join(PROJECT_ROOT, "tasks_local")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

_BACKEND_URLS = {
    "tritonai": "https://tritonai-api.ucsd.edu/v1",
    "openai": None,
    "ollama": "http://localhost:11434/v1",
    "local": "http://localhost:8000/v1",
    "deepseek": "https://api.deepseek.com/v1",
}

_BACKEND_DEFAULT_MODELS = {
    "tritonai": "api-gpt-oss-120b",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1:8b",
    "local": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "deepseek": "deepseek-chat",
}


def _fmt_elapsed(seconds: float) -> str:
    """Format elapsed seconds as mm:ss or hh:mm:ss."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _task_roots() -> list[str]:
    roots = []
    if os.path.isdir(TASKS_LOCAL_DIR):
        roots.append(TASKS_LOCAL_DIR)
    roots.append(TASKS_DIR)
    return roots


def discover_tasks(tasks_dirs: list[str]) -> list[str]:
    """Return sorted list of task directory paths that contain metadata.json.

    Recursively walks the nested structure:
      tasks/mock/{head,easy,hard}/<task>/
      tasks/debugbench/{bug_category}/<task>/
    """
    found: list[str] = []
    seen_names: set[str] = set()
    for tasks_dir in tasks_dirs:
        if not os.path.isdir(tasks_dir):
            continue
        for root, dirs, files in os.walk(tasks_dir):
            if "metadata.json" not in files:
                continue
            task_name = os.path.basename(root)
            if task_name in seen_names:
                continue
            seen_names.add(task_name)
            found.append(root)
    return sorted(found)


def run_single(
    task_dir: str,
    protocol: str,
    model: str,
    hint_level: int,
    strategy: str | None,
    max_turns: int,
    max_tokens: int,
    temperature: float,
    seed: int | None,
    backend: str,
    base_url: str | None,
    api_key: str | None,
) -> dict:
    """Run one experiment and return the result dict."""
    runner = AgentRunner(
        task_dir=task_dir,
        protocol=protocol,
        model=model,
        temperature=temperature,
        hint_level=hint_level,
        max_turns=max_turns,
        max_total_tokens=max_tokens,
        strategy=strategy,
        seed=seed,
        backend=backend,
        base_url=base_url,
        api_key=api_key,
    )
    return runner.run()


def main():
    parser = argparse.ArgumentParser(
        description="Run debugging-agent experiments on HEAD benchmark tasks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # ── Task selection ──
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument(
        "--task", type=str,
        help="Task directory name (e.g. head_001_off_by_one).",
    )
    task_group.add_argument(
        "--all", action="store_true",
        help="Run on all tasks discovered in the tasks/ directory.",
    )

    # ── Backend selection ──
    parser.add_argument(
        "--backend", default="tritonai",
        choices=["tritonai", "openai", "ollama", "local", "deepseek"],
        help="LLM backend to use (default: tritonai).",
    )
    parser.add_argument(
        "--base-url", type=str, default=None,
        help="Override the API endpoint URL.",
    )
    parser.add_argument(
        "--api-key", type=str, default=None,
        help="API key (overrides environment variable).",
    )

    # ── Protocol & strategy ──
    parser.add_argument(
        "--protocol", nargs="+", default=["react"],
        choices=["act_only", "react", "reflexion"],
        help="Interaction protocol(s) to test (default: react).",
    )
    parser.add_argument(
        "--strategy", type=str, default=None,
        choices=["baseline", "checklist", "early_stop_restart", "self_consistency"],
        help="Debugging strategy to apply on top of the protocol.",
    )

    # ── Hint levels (Phase 3) ──
    parser.add_argument(
        "--hint-levels", nargs="+", type=int, default=[0],
        help="Hint level(s) for the minimal intervention study (0–4).",
    )

    # ── Model & budget ──
    parser.add_argument("--model", default=None, help="LLM model name.")
    parser.add_argument("--max-turns", type=int, default=25)
    parser.add_argument("--max-tokens", type=int, default=50000)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)

    # ── Repetition & output ──
    parser.add_argument("--repeat", type=int, default=1, help="Repetitions per condition.")
    parser.add_argument("--output-dir", default=RESULTS_DIR, help="Directory to save results.")

    args = parser.parse_args()

    # Resolve model name & base_url
    model = args.model or _BACKEND_DEFAULT_MODELS.get(args.backend, "gpt-4o-mini")
    base_url = args.base_url or _BACKEND_URLS.get(args.backend)

    # Resolve tasks
    task_roots = _task_roots()

    if args.all:
        task_dirs = discover_tasks(task_roots)
        if not task_dirs:
            print(f"No tasks found in {', '.join(task_roots)}.", file=sys.stderr)
            sys.exit(1)
    else:
        matches = []
        for tasks_dir in task_roots:
            td = os.path.join(tasks_dir, args.task)
            if os.path.isdir(td):
                matches.append(td)
                continue
            for root, dirs, files in os.walk(tasks_dir):
                if os.path.basename(root) == args.task and "metadata.json" in files:
                    matches.append(root)
        if not matches:
            print(f"Task not found: {args.task}", file=sys.stderr)
            sys.exit(1)
        if len(matches) > 1:
            matches.sort(key=lambda path: (0 if path.startswith(TASKS_LOCAL_DIR) else 1, path))
            task_dirs = [matches[0]]
        else:
            task_dirs = matches

    strategy = args.strategy or "baseline"

    # ── Build run list ──
    run_list: list[dict] = []
    for task_dir in task_dirs:
        for protocol in args.protocol:
            for hint_level in args.hint_levels:
                for rep in range(1, args.repeat + 1):
                    run_list.append(dict(
                        task_dir=task_dir,
                        protocol=protocol,
                        hint_level=hint_level,
                        rep=rep,
                    ))

    total_runs = len(run_list)

    # ── Print experiment plan ──
    print(f"\n{'='*70}")
    print(f"  EXPERIMENT PLAN — {total_runs} run(s)")
    print(f"{'='*70}")
    print(f"  Tasks:       {len(task_dirs)}")
    print(f"  Protocols:   {', '.join(args.protocol)}")
    print(f"  Strategy:    {strategy}")
    print(f"  Hint levels: {args.hint_levels}")
    print(f"  Repeat:      {args.repeat}x")
    print(f"  Backend:     {args.backend}  |  Model: {model}")
    if base_url:
        print(f"  Endpoint:    {base_url}")
    print(f"  Output:      {args.output_dir}/<category>/")
    print(f"{'='*70}\n")

    # ── Execute runs ──
    all_results: list[dict] = []
    pass_count = 0
    fail_count = 0
    exp_start = time.time()

    for idx, run in enumerate(run_list, 1):
        task_name = os.path.basename(run["task_dir"])
        protocol = run["protocol"]
        hint_level = run["hint_level"]
        rep = run["rep"]

        hint_tag = f"  h={hint_level}" if hint_level else ""
        rep_tag = f"  rep={rep}" if args.repeat > 1 else ""
        strat_tag = f"  strat={strategy}" if strategy != "baseline" else ""

        elapsed = _fmt_elapsed(time.time() - exp_start)
        progress = f"[{idx}/{total_runs}]"
        tally = f"[pass={pass_count} fail={fail_count}]"

        print(f"{progress} {tally} ({elapsed})  {task_name}  |  {protocol}{strat_tag}{hint_tag}{rep_tag}")
        sys.stdout.flush()

        try:
            seed = (args.seed + rep - 1) if args.seed is not None else None
            result = run_single(
                task_dir=run["task_dir"],
                protocol=protocol,
                model=model,
                hint_level=hint_level,
                strategy=args.strategy,
                max_turns=args.max_turns,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                seed=seed,
                backend=args.backend,
                base_url=base_url,
                api_key=args.api_key,
            )
            result["repetition"] = rep

            r = result["result"]
            cm = result.get("cost_metrics", {})
            success = r["success"]
            if success:
                pass_count += 1
                mark = "  ✓ PASS"
            else:
                fail_count += 1
                mark = "  ✗ FAIL"

            # Cost-focused output
            edits = cm.get("patch_attempt_count", "?")
            tests = cm.get("test_run_count", "?")
            print(
                f"{mark}  turns={r['total_turns']}  tokens={r['total_tokens']}  "
                f"edits={edits}  tests={tests}  "
                f"cost=${r['total_cost_usd']:.4f}  time={r['wall_time_sec']:.1f}s"
            )

            path = save_result(result, output_dir=args.output_dir)
            print(f"  → {path}")

            all_results.append(result)

        except Exception as exc:
            fail_count += 1
            print(f"  ✗ ERROR: {exc}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

        print()
        sys.stdout.flush()

    # ── Final summary ──
    total_elapsed = _fmt_elapsed(time.time() - exp_start)
    total_cost = sum(r["result"]["total_cost_usd"] for r in all_results)

    print(f"{'='*70}")
    print(f"  EXPERIMENT COMPLETE  ({total_elapsed})")
    print(f"{'='*70}")
    print(f"  Runs:    {len(all_results)} / {total_runs}")
    print(f"  Pass:    {pass_count}")
    print(f"  Fail:    {fail_count}")
    print(f"  Cost:    ${total_cost:.4f}")
    print(f"  Results: {args.output_dir}/")

    # ── Cost-focused summary table ──
    if all_results:
        _print_cost_summary(all_results)

    print(f"{'='*70}\n")


def _print_cost_summary(results: list[dict]):
    """Print a cost-centric summary table grouped by category and protocol."""
    by_key: dict[tuple, list] = defaultdict(list)
    for r in results:
        cat = r.get("category", "other")
        proto = r["protocol"]
        strat = r.get("strategy", "baseline")
        by_key[(cat, proto, strat)].append(r)

    print(f"\n  {'Category':<28} {'Proto':<10} {'Strat':<18} "
          f"{'Pass':>5} {'Fail':>5} {'Rate':>6} "
          f"{'Avg Tok':>8} {'Avg Turn':>8} {'Avg Edit':>8} {'Avg Test':>8} "
          f"{'Avg Time':>8}")
    print(f"  {'-'*130}")

    for key in sorted(by_key):
        cat, proto, strat = key
        runs = by_key[key]
        n = len(runs)
        p = sum(1 for r in runs if r["result"]["success"])
        f = n - p
        rate = p / n if n else 0

        avg_tok = sum(r["result"]["total_tokens"] for r in runs) / n
        avg_turn = sum(r["result"]["total_turns"] for r in runs) / n
        avg_edit = sum(r.get("cost_metrics", {}).get("patch_attempt_count", 0) for r in runs) / n
        avg_test = sum(r.get("cost_metrics", {}).get("test_run_count", 0) for r in runs) / n
        avg_time = sum(r["result"]["wall_time_sec"] for r in runs) / n

        print(
            f"  {cat:<28} {proto:<10} {strat:<18} "
            f"{p:>5} {f:>5} {rate:>5.0%} "
            f"{avg_tok:>8.0f} {avg_turn:>8.1f} {avg_edit:>8.1f} {avg_test:>8.1f} "
            f"{avg_time:>7.1f}s"
        )


if __name__ == "__main__":
    main()

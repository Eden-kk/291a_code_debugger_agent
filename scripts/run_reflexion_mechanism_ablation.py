#!/usr/bin/env python3
"""Run matched Reflexion mechanism ablations on the current HEAD-20 set.

Conditions:
  - react_baseline: standard react baseline
  - reflexion_baseline: current reflexion implementation (Ep1 + reflection + Ep2)
  - reflexion_ep1_only: same reflexion prompt/framework, but stop after Episode 1
  - restart_without_reflection: same as reflexion, but Ep2 is a clean restart with
    no generated reflection injected

The goal is to isolate whether Reflexion's gain comes from:
  0. A true protocol difference vs react baseline
  1. Episode-1 behavior alone
  2. The clean restart itself
  3. The reflection text injected into Episode 2

Outputs:
  - raw runs under results/ablation_reflexion_mechanism/
  - docs/report/reflexion_mechanism_ablation_head20.json
  - docs/report/reflexion_mechanism_ablation_head20.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_local.runner import AgentRunner
from agent_local.telemetry import save_result


RESULTS_DIR = PROJECT_ROOT / "results" / "ablation_reflexion_mechanism"
MERGED_5SEED = PROJECT_ROOT / "docs" / "report" / "merged_5seed_act_only_baseline.json"
REPORT_JSON = PROJECT_ROOT / "docs" / "report" / "reflexion_mechanism_ablation_head20.json"
REPORT_MD = PROJECT_ROOT / "docs" / "report" / "reflexion_mechanism_ablation_head20.md"

MISTRAL_MODEL = "api-mistral-small-3.2-2506"
DEFAULT_BACKEND = "tritonai"
DEFAULT_SEED = 42
DEFAULT_MAX_TURNS = 25
DEFAULT_MAX_TOKENS = 50_000


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


class ReflexionEp1OnlyRunner(AgentRunner):
    """Reflexion Episode-1 only: identical prompt, no Episode 2."""

    def _run_standard(self) -> dict:
        start = time.time()

        messages = self._initial_messages()
        success, turns, _ = self._run_episode(messages, episode=1)

        ep1_in = self.llm.total_input_tokens
        ep1_out = self.llm.total_output_tokens
        self.telemetry.record_episode_summary(1, success, turns, ep1_in, ep1_out)

        wall = time.time() - start
        result = self.telemetry.finalize(
            success=success,
            total_turns=turns,
            total_input_tokens=self.llm.total_input_tokens,
            total_output_tokens=self.llm.total_output_tokens,
            total_cost_usd=self.llm.estimated_cost(),
            wall_time_sec=wall,
        )
        self.env.cleanup()
        return result


class RestartWithoutReflectionRunner(AgentRunner):
    """Reflexion-style clean restart, but Episode 2 gets no reflection text."""

    def _run_standard(self) -> dict:
        start = time.time()

        messages = self._initial_messages()
        success, turns, _ = self._run_episode(messages, episode=1)

        ep1_in = self.llm.total_input_tokens
        ep1_out = self.llm.total_output_tokens
        self.telemetry.record_episode_summary(1, success, turns, ep1_in, ep1_out)

        if not success and self.protocol == "reflexion":
            self.env.reset()
            self.metadata["_work_dir"] = self.env.work_dir
            self.telemetry.start_new_episode(2, "Restart retry without reflection")

            messages = self._initial_messages(reflection=None)
            success, extra_turns, _ = self._run_episode(messages, episode=2)
            turns += extra_turns

            ep2_in = self.llm.total_input_tokens - ep1_in
            ep2_out = self.llm.total_output_tokens - ep1_out
            self.telemetry.record_episode_summary(2, success, extra_turns, ep2_in, ep2_out)

        wall = time.time() - start
        result = self.telemetry.finalize(
            success=success,
            total_turns=turns,
            total_input_tokens=self.llm.total_input_tokens,
            total_output_tokens=self.llm.total_output_tokens,
            total_cost_usd=self.llm.estimated_cost(),
            wall_time_sec=wall,
        )
        self.env.cleanup()
        return result


CONDITIONS = {
    "react_baseline": {
        "runner_cls": AgentRunner,
        "protocol": "react",
        "strategy": "baseline",
        "description": "Standard react baseline used as the direct comparison point for Reflexion Ep1.",
    },
    "reflexion_baseline": {
        "runner_cls": AgentRunner,
        "protocol": "reflexion",
        "strategy": "baseline",
        "description": "Current reflexion baseline: Ep1 + generated reflection + clean Ep2 restart.",
    },
    "reflexion_ep1_only": {
        "runner_cls": ReflexionEp1OnlyRunner,
        "protocol": "reflexion",
        "strategy": "ep1_only",
        "description": "Stop after Episode 1 while keeping the reflexion prompt unchanged.",
    },
    "restart_without_reflection": {
        "runner_cls": RestartWithoutReflectionRunner,
        "protocol": "reflexion",
        "strategy": "restart_without_reflection",
        "description": "Run Ep2 after a clean restart, but inject no reflection text.",
    },
}


def run_condition(
    condition: str,
    task_ids: list[str],
    model: str,
    backend: str,
    seed: int,
    max_turns: int,
    max_tokens: int,
) -> dict:
    cfg = CONDITIONS[condition]
    runner_cls = cfg["runner_cls"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 78}")
    print(f"{condition}")
    print(cfg["description"])
    print(f"Tasks={len(task_ids)}  Model={model}  Seed={seed}  Budget={max_tokens}")
    print(f"{'=' * 78}\n")

    rows = []
    pass_count = 0
    total_tokens = 0
    t0 = time.time()

    for idx, task_id in enumerate(task_ids, 1):
        task_dir = find_task_dir(task_id)
        elapsed = time.time() - t0
        eta = elapsed / max(idx - 1, 1) * (len(task_ids) - idx + 1)
        print(f"[{idx:02d}/{len(task_ids)}] ({elapsed:.0f}s elapsed, ETA {eta:.0f}s) {task_id}")
        sys.stdout.flush()

        runner = runner_cls(
            task_dir=task_dir,
            protocol=cfg["protocol"],
            model=model,
            temperature=0.0,
            hint_level=0,
            max_turns=max_turns,
            max_total_tokens=max_tokens,
            strategy=cfg["strategy"],
            seed=seed,
            backend=backend,
        )

        result = runner.run()
        result["ablation_condition"] = condition
        result["ablation_description"] = cfg["description"]
        result_path = save_result(result, output_dir=str(RESULTS_DIR))

        success = result["result"]["success"]
        tokens = result["result"]["total_tokens"]
        turns = result["result"]["total_turns"]
        episodes = result.get("episodes") or []
        ep1_success = episodes[0]["success"] if len(episodes) >= 1 else None
        ep2_success = episodes[1]["success"] if len(episodes) >= 2 else None

        pass_count += int(success)
        total_tokens += tokens
        rows.append(
            {
                "task_id": task_id,
                "success": success,
                "total_tokens": tokens,
                "total_turns": turns,
                "episodes_used": len(episodes),
                "ep1_success": ep1_success,
                "ep2_success": ep2_success,
                "result_path": str(result_path),
            }
        )
        mark = "PASS" if success else "FAIL"
        print(f"  {mark}  turns={turns}  tokens={tokens}  episodes={len(episodes)}")
        print(f"  -> {result_path}\n")

    n = len(rows)
    wall = time.time() - t0
    summary = {
        "condition": condition,
        "description": cfg["description"],
        "n_tasks": n,
        "pass": pass_count,
        "fail": n - pass_count,
        "pass_pct": round(pass_count / n * 100, 1) if n else 0.0,
        "avg_tokens": round(total_tokens / n, 1) if n else 0.0,
        "wall_time_sec": round(wall, 1),
        "runs": rows,
    }
    print(
        f"{condition}: {summary['pass']}/{summary['n_tasks']} "
        f"({summary['pass_pct']}%), avg_tokens={summary['avg_tokens']}"
    )
    return summary


def build_report(summaries: dict[str, dict], metadata: dict) -> dict:
    react = summaries["react_baseline"]
    baseline = summaries["reflexion_baseline"]
    ep1_only = summaries["reflexion_ep1_only"]
    no_reflect = summaries["restart_without_reflection"]

    react_runs = {r["task_id"]: r for r in react["runs"]}
    baseline_runs = {r["task_id"]: r for r in baseline["runs"]}
    ep1_runs = {r["task_id"]: r for r in ep1_only["runs"]}
    no_reflect_runs = {r["task_id"]: r for r in no_reflect["runs"]}

    ep2_rescues_baseline = sorted(
        tid for tid, row in baseline_runs.items()
        if row["ep1_success"] is False and row["ep2_success"] is True
    )
    ep2_rescues_no_reflect = sorted(
        tid for tid, row in no_reflect_runs.items()
        if row["ep1_success"] is False and row["ep2_success"] is True
    )

    regained_by_reflection = sorted(
        tid for tid in baseline_runs
        if baseline_runs[tid]["success"] and not no_reflect_runs[tid]["success"]
    )
    regained_by_restart = sorted(
        tid for tid in no_reflect_runs
        if no_reflect_runs[tid]["success"] and not ep1_runs[tid]["success"]
    )
    ep1_beats_react = sorted(
        tid for tid in ep1_runs
        if ep1_runs[tid]["success"] and not react_runs[tid]["success"]
    )
    react_beats_ep1 = sorted(
        tid for tid in react_runs
        if react_runs[tid]["success"] and not ep1_runs[tid]["success"]
    )
    baseline_beats_react = sorted(
        tid for tid in baseline_runs
        if baseline_runs[tid]["success"] and not react_runs[tid]["success"]
    )
    react_beats_baseline = sorted(
        tid for tid in react_runs
        if react_runs[tid]["success"] and not baseline_runs[tid]["success"]
    )

    return {
        "metadata": metadata,
        "summaries": summaries,
        "comparisons": {
            "ep1_only_minus_react_pass_pct": round(
                ep1_only["pass_pct"] - react["pass_pct"], 1
            ),
            "baseline_minus_react_pass_pct": round(
                baseline["pass_pct"] - react["pass_pct"], 1
            ),
            "baseline_minus_ep1_only_pass_pct": round(
                baseline["pass_pct"] - ep1_only["pass_pct"], 1
            ),
            "baseline_minus_restart_without_reflection_pass_pct": round(
                baseline["pass_pct"] - no_reflect["pass_pct"], 1
            ),
            "ep2_rescues_baseline": ep2_rescues_baseline,
            "ep2_rescues_restart_without_reflection": ep2_rescues_no_reflect,
            "baseline_success_but_restart_without_reflection_fail": regained_by_reflection,
            "restart_without_reflection_success_but_ep1_only_fail": regained_by_restart,
            "ep1_only_success_but_react_fail": ep1_beats_react,
            "react_success_but_ep1_only_fail": react_beats_ep1,
            "baseline_success_but_react_fail": baseline_beats_react,
            "react_success_but_baseline_fail": react_beats_baseline,
        },
    }


def write_markdown_report(report: dict) -> None:
    meta = report["metadata"]
    sums = report["summaries"]
    cmp = report["comparisons"]

    lines = []
    lines.append("# Reflexion Mechanism Ablation on HEAD-20")
    lines.append("")
    lines.append("## Experimental Design")
    lines.append("")
    lines.append(
        f"- Task set: current HEAD-20 from `merged_5seed_act_only_baseline.json` ({meta['n_tasks']} tasks)"
    )
    lines.append(f"- Model: `{meta['model']}`")
    lines.append(f"- Seed: `{meta['seed']}`")
    lines.append(f"- Budget: `{meta['max_total_tokens']}` tokens, `{meta['max_turns']}` max turns per episode")
    lines.append("- Hint level: `h0`")
    lines.append("- All four conditions were run in the same batch to avoid comparing new ablations against old baselines.")
    lines.append("")
    lines.append("## Conditions")
    lines.append("")
    for key, val in sums.items():
        lines.append(f"- `{key}`: {val['description']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Condition | Pass | Pass % | Avg tokens |")
    lines.append("|---|---:|---:|---:|")
    for key in ("react_baseline", "reflexion_ep1_only", "reflexion_baseline", "restart_without_reflection"):
        val = sums[key]
        lines.append(
            f"| `{key}` | {val['pass']}/{val['n_tasks']} | {val['pass_pct']}% | {val['avg_tokens']} |"
        )
    lines.append("")
    lines.append("## Mechanism Readout")
    lines.append("")
    lines.append(
        f"- Ep1-only minus react baseline: `{cmp['ep1_only_minus_react_pass_pct']} pp`"
    )
    lines.append(
        f"- Reflexion baseline minus react baseline: `{cmp['baseline_minus_react_pass_pct']} pp`"
    )
    lines.append(
        f"- Baseline minus Ep1-only: `{cmp['baseline_minus_ep1_only_pass_pct']} pp`"
    )
    lines.append(
        f"- Baseline minus restart-without-reflection: `{cmp['baseline_minus_restart_without_reflection_pass_pct']} pp`"
    )
    lines.append(
        f"- Ep2 rescues in baseline: `{len(cmp['ep2_rescues_baseline'])}` -> {cmp['ep2_rescues_baseline']}"
    )
    lines.append(
        f"- Ep2 rescues in restart-without-reflection: `{len(cmp['ep2_rescues_restart_without_reflection'])}` -> {cmp['ep2_rescues_restart_without_reflection']}"
    )
    lines.append(
        "- Baseline success but restart-without-reflection fail "
        f"({len(cmp['baseline_success_but_restart_without_reflection_fail'])}): "
        f"{cmp['baseline_success_but_restart_without_reflection_fail']}"
    )
    lines.append(
        "- Restart-without-reflection success but Ep1-only fail "
        f"({len(cmp['restart_without_reflection_success_but_ep1_only_fail'])}): "
        f"{cmp['restart_without_reflection_success_but_ep1_only_fail']}"
    )
    lines.append(
        "- Ep1-only success but react fail "
        f"({len(cmp['ep1_only_success_but_react_fail'])}): "
        f"{cmp['ep1_only_success_but_react_fail']}"
    )
    lines.append(
        "- React success but Ep1-only fail "
        f"({len(cmp['react_success_but_ep1_only_fail'])}): "
        f"{cmp['react_success_but_ep1_only_fail']}"
    )
    lines.append(
        "- Baseline success but react fail "
        f"({len(cmp['baseline_success_but_react_fail'])}): "
        f"{cmp['baseline_success_but_react_fail']}"
    )
    lines.append(
        "- React success but baseline fail "
        f"({len(cmp['react_success_but_baseline_fail'])}): "
        f"{cmp['react_success_but_baseline_fail']}"
    )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "- `react_baseline` and `reflexion_baseline` tie at `8/20`, so this matched batch does not reproduce a reflexion-over-react aggregate advantage."
    )
    lines.append(
        "- `reflexion_ep1_only` lands at `7/20`, only one task below `react_baseline`; the two conditions trade wins rather than showing a stable ordering."
    )
    lines.append(
        "- Neither two-episode condition produces an `Ep1 fail -> Ep2 pass` rescue, so Episode 2 is not a demonstrated positive contributor in this batch."
    )
    lines.append(
        "- `restart_without_reflection` is the weakest condition (`5/20`) and also the most expensive, which argues against clean restart alone as the source of any reflexion gain."
    )
    lines.append(
        "- The only baseline-vs-react differences are task-level swaps inside QuixBugs, not a family-level shift: both solve `1/7` DebugBench, `0/4` Mini-nightmare, and `7/9` QuixBugs."
    )
    REPORT_MD.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run matched Reflexion mechanism ablations on HEAD-20.")
    parser.add_argument(
        "--conditions",
        nargs="+",
        choices=list(CONDITIONS),
        default=list(CONDITIONS),
        help="Conditions to run.",
    )
    parser.add_argument("--task", action="append", help="Optional single task or repeated --task filters.")
    parser.add_argument("--model", default=MISTRAL_MODEL)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS)
    parser.add_argument("--max-total-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    task_ids = args.task or load_head20_tasks()
    summaries = {}
    for condition in args.conditions:
        summaries[condition] = run_condition(
            condition=condition,
            task_ids=task_ids,
            model=args.model,
            backend=args.backend,
            seed=args.seed,
            max_turns=args.max_turns,
            max_tokens=args.max_total_tokens,
        )

    report = build_report(
        summaries=summaries,
        metadata={
            "task_ids": task_ids,
            "n_tasks": len(task_ids),
            "model": args.model,
            "backend": args.backend,
            "seed": args.seed,
            "max_turns": args.max_turns,
            "max_total_tokens": args.max_total_tokens,
        },
    )
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    write_markdown_report(report)

    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")


if __name__ == "__main__":
    main()

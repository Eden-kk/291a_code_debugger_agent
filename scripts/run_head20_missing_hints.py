#!/usr/bin/env python3
"""
Run missing hint-study runs for HEAD 20: the 13 tasks that have L0 but no L2/L4.
Runs: Mistral react baseline h2, Mistral react baseline h4, 120B react baseline h2.
Total: 13 × 3 = 39 runs. Requires backend (default tritonai) and writes to results/.

TritonAI API key: read from environment variable TRITONAI_API_KEY (see README § Set Up an LLM Backend).
No key is stored in the repo. If you see TimeoutError during import when run from Cursor,
run this script in your local terminal so your shell's env and filesystem are used:
  python scripts/run_head20_missing_hints.py

Usage:
  python scripts/run_head20_missing_hints.py --dry-run   # print commands
  python scripts/run_head20_missing_hints.py             # execute (needs TRITONAI_API_KEY)
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEAD_20_DATA = PROJECT_ROOT / "docs" / "report" / "head_20_from_existing.json"


def main():
    dry = "--dry-run" in sys.argv
    data = json.loads(HEAD_20_DATA.read_text())
    missing = data["hint_study"]["missing_hint_runs"]
    # All three have the same 13 tasks
    tasks_13 = missing["Mistral_L2"]
    assert tasks_13 == missing["Mistral_L4"] == missing["120B_L2"], "same 13 tasks"

    run_experiment = PROJECT_ROOT / "run_experiment.py"
    backend = "tritonai"
    # 13 tasks × (Mistral L2+L4 in one call, 120B L2 in one call) = 26 invocations, 39 runs
    runs = []
    for task in tasks_13:
        runs.append((task, "api-mistral-small-3.2-2506", [2, 4]))  # 2 runs
        runs.append((task, "api-gpt-oss-120b", [2]))                 # 1 run

    total_runs = 13 * 3
    print(f"Planned {len(runs)} invocations ({total_runs} runs: 13×Mistral L2, 13×Mistral L4, 13×120B L2).")
    if dry:
        for task, model, levels in runs:
            print(f"  --task {task} --model {model} --protocol react --hint-levels {' '.join(map(str, levels))} --backend {backend}")
        return

    # TritonAI key from environment (run_experiment.py / agent/llm_client.py use TRITONAI_API_KEY)
    env = os.environ.copy()
    if not env.get("TRITONAI_API_KEY"):
        print("Warning: TRITONAI_API_KEY is not set. Set it in your shell (see README).", file=sys.stderr)
        print("  export TRITONAI_API_KEY='sk-...'", file=sys.stderr)

    for i, (task, model, levels) in enumerate(runs, 1):
        cmd = [
            sys.executable, str(run_experiment),
            "--task", task,
            "--model", model,
            "--protocol", "react",
            "--hint-levels", *[str(x) for x in levels],
            "--backend", backend,
        ]
        print(f"[{i}/{len(runs)}] Running: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    print("Done. Re-run scripts/head_20_data_from_existing.py to refresh head_20_from_existing.json.")


if __name__ == "__main__":
    main()

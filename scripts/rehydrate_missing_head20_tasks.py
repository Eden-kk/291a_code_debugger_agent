#!/usr/bin/env python3
"""Rebuild the 13 HEAD-20 tasks missing hint runs into tasks_local/.

Why this exists:
- The original task files under `tasks/` can be `dataless` iCloud placeholders.
- The missing hint-study runs only need 13 specific tasks.
- We can reconstruct them from public benchmark sources plus existing result
  trajectories already stored under `results/`.

This script creates:
  tasks_local/quixbugs/<task_id>/
  tasks_local/mini_nightmare/<task_id>/
  tasks_local/debugbench/<bug_category>/<task_id>/
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
TASKS_LOCAL_DIR = PROJECT_ROOT / "tasks_local"
SOURCE_CACHE_DIR = PROJECT_ROOT / ".cache" / "rehydration_sources"

QUIXBUGS_REPO = SOURCE_CACHE_DIR / "QuixBugs"
DEBUG_GYM_REPO = SOURCE_CACHE_DIR / "debug-gym"
DEBUGBENCH_REPO = SOURCE_CACHE_DIR / "DebugBench"

QUIXBUGS_TASKS = [
    "quixbugs_find_first_in_sorted",
    "quixbugs_find_in_sorted",
    "quixbugs_is_valid_parenthesization",
    "quixbugs_knapsack",
    "quixbugs_mergesort",
    "quixbugs_next_palindrome",
    "quixbugs_quicksort",
    "quixbugs_to_base",
    "quixbugs_wrap",
]

MINI_TASKS = [
    "mini_nightmare_patcher",
    "mini_nightmare_purr",
    "mini_nightmare_scientific_calculator",
    "mini_nightmare_tomorrow_date",
]

DEBUGBENCH_TASKS = {
    "debugbench_004_reverse_bits": {
        "bug_category": "logic_error",
        "benchmark_file": "python3_operation error.json",
        "slug": "reverse-bits",
    },
    "debugbench_012_corporate_flight_bookings": {
        "bug_category": "reference_error",
        "benchmark_file": "python3_undefined objects.json",
        "slug": "corporate-flight-bookings",
    },
    "debugbench_017_find_mode_in_binary_search_tree": {
        "bug_category": "syntax_error",
        "benchmark_file": "python3_missing colons.json",
        "slug": "find-mode-in-binary-search-tree",
    },
    "debugbench_018_valid_arrangement_of_pairs": {
        "bug_category": "syntax_error",
        "benchmark_file": "python3_unclosed parentheses.json",
        "slug": "valid-arrangement-of-pairs",
    },
    "debugbench_031_next_greater_element_i": {
        "bug_category": "reference_error",
        "benchmark_file": "python3_undefined methods.json",
        "slug": "next-greater-element-i",
    },
    "debugbench_037_minimum_bit_flips_to_convert_number": {
        "bug_category": "syntax_error",
        "benchmark_file": "python3_illegal indentation.json",
        "slug": "minimum-bit-flips-to-convert-number",
    },
    "debugbench_039_grid_game": {
        "bug_category": "syntax_error",
        "benchmark_file": "python3_illegal indentation.json",
        "slug": "grid-game",
    },
}

DEBUGBENCH_IMPORT_BLOCK = "\n".join(
    [
        "from typing import *",
        "from collections import *",
        "from functools import *",
        "import math",
        "import heapq",
        "import bisect",
        "",
        "",
    ]
)


def ensure_repo(url: str, dest: Path) -> None:
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def ensure_init(path: Path) -> None:
    write_text(path / "__init__.py", "")


def unified_diff(buggy_text: str, fixed_text: str, filename: str) -> str:
    return "".join(
        difflib.unified_diff(
            buggy_text.splitlines(keepends=True),
            fixed_text.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )


def first_changed_line(buggy_text: str, fixed_text: str) -> int:
    buggy_lines = buggy_text.splitlines()
    fixed_lines = fixed_text.splitlines()
    limit = min(len(buggy_lines), len(fixed_lines))
    for idx in range(limit):
        if buggy_lines[idx] != fixed_lines[idx]:
            return idx + 1
    return limit + 1


def function_at_line(source_text: str, line_number: int) -> str | None:
    current = None
    for idx, line in enumerate(source_text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("def "):
            current = stripped.split("(")[0].replace("def ", "").strip()
        if idx == line_number:
            return current
    return current


def parse_file_observation(content: str) -> str:
    lines = []
    for line in content.splitlines()[1:]:
        match = re.match(r"^\s*\d+\s+\|\s?(.*)$", line)
        if match:
            lines.append(match.group(1))
    return "\n".join(lines).rstrip() + "\n"


def normalize_quixbugs_json(raw_text: str) -> str:
    try:
        json.loads(raw_text)
        return raw_text if raw_text.endswith("\n") else raw_text + "\n"
    except json.JSONDecodeError:
        items = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
        return json.dumps(items, ensure_ascii=False) + "\n"


def load_result(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError):
        return None


def find_observed_file(task_id: str, rel_path: str) -> str:
    pattern = f"{task_id}__"
    for result_path in sorted(RESULTS_DIR.rglob("*.json")):
        if pattern not in result_path.name:
            continue
        data = load_result(result_path)
        if not data:
            continue
        for item in data.get("trajectory", []):
            content = item.get("content", "")
            if item.get("type") == "observation" and content.startswith(f"File: {rel_path} "):
                return parse_file_observation(content)
    raise FileNotFoundError(f"Could not recover {rel_path} from results for {task_id}.")


def apply_successful_edits(task_id: str, rel_path: str, original_text: str) -> str:
    pattern = f"{task_id}__"
    for result_path in sorted(RESULTS_DIR.rglob("*.json")):
        data = load_result(result_path)
        if not data:
            continue
        if pattern not in result_path.name or not data.get("result", {}).get("success"):
            continue
        current = original_text
        trajectory = data.get("trajectory", [])
        for idx, item in enumerate(trajectory):
            if item.get("type") != "action":
                continue
            try:
                payload = json.loads(item.get("content", ""))
            except json.JSONDecodeError:
                continue
            if payload.get("tool") != "edit_file":
                continue
            args = payload.get("args", {})
            if args.get("path") != rel_path:
                continue
            if idx + 1 >= len(trajectory):
                continue
            next_item = trajectory[idx + 1]
            if next_item.get("type") != "observation":
                continue
            if not next_item.get("content", "").startswith("Successfully edited"):
                continue
            old_text = args.get("old_text", "")
            new_text = args.get("new_text", "")
            if old_text not in current:
                raise ValueError(f"Could not apply stored edit for {task_id}:{rel_path}")
            current = current.replace(old_text, new_text, 1)
        if current != original_text:
            return current
    raise FileNotFoundError(f"Could not derive fixed code from successful results for {task_id}.")


def rehydrate_quixbugs() -> list[dict]:
    programs_dir = QUIXBUGS_REPO / "python_programs"
    correct_dir = QUIXBUGS_REPO / "correct_python_programs"
    tests_dir = QUIXBUGS_REPO / "python_testcases"
    json_dir = QUIXBUGS_REPO / "json_testcases"
    manifest = []

    for task_id in QUIXBUGS_TASKS:
        name = task_id.replace("quixbugs_", "", 1)
        task_dir = TASKS_LOCAL_DIR / "quixbugs" / task_id
        src_dir = task_dir / "src"
        task_tests_dir = task_dir / "tests"
        src_dir.mkdir(parents=True, exist_ok=True)
        task_tests_dir.mkdir(parents=True, exist_ok=True)
        ensure_init(src_dir)
        ensure_init(task_tests_dir)

        buggy_code = (programs_dir / f"{name}.py").read_text(encoding="utf-8")
        fixed_code = (correct_dir / f"{name}.py").read_text(encoding="utf-8")
        test_code = (tests_dir / f"test_{name}.py").read_text(encoding="utf-8")

        adapted_test = test_code
        adapted_test = re.sub(
            r"if pytest\.use_correct:\s*\n\s*from correct_python_programs\.(\w+) import (\w+)\s*\n\s*else:\s*\n\s*from python_programs\.(\w+) import (\w+)",
            r"from src.\3 import \4",
            adapted_test,
        )
        adapted_test = adapted_test.replace("from python_programs.", "from src.")
        adapted_test = adapted_test.replace("from correct_python_programs.", "from src.")

        if "load_testdata" in adapted_test or "load_json_testcases" in adapted_test:
            adapted_test = adapted_test.replace(
                "from load_testdata import load_json_testcases\n",
                "import json\nimport os\n",
            )
            adapted_test = re.sub(
                r"testdata = load_json_testcases\(\w+\.__name__\)",
                '_test_dir = os.path.dirname(os.path.abspath(__file__))\n'
                f'with open(os.path.join(_test_dir, "{name}.json")) as _f:\n'
                "    testdata = json.load(_f)",
                adapted_test,
            )
            raw_json = (json_dir / f"{name}.json").read_text(encoding="utf-8")
            write_text(task_tests_dir / f"{name}.json", normalize_quixbugs_json(raw_json))

        node_src = tests_dir / "node.py"
        if node_src.exists() and ("Node" in buggy_code or "Node" in adapted_test):
            shutil.copy2(node_src, src_dir / "node.py")
            shutil.copy2(node_src, task_tests_dir / "node.py")

        write_text(src_dir / f"{name}.py", buggy_code)
        write_text(task_tests_dir / f"test_{name}.py", adapted_test)
        write_text(task_dir / "patch.diff", unified_diff(buggy_code, fixed_code, f"src/{name}.py"))

        buggy_line = first_changed_line(buggy_code, fixed_code)
        metadata = {
            "task_id": task_id,
            "category": "quixbugs",
            "subcategory": "algorithm_bug",
            "bug_type": "single_line_defect",
            "description": f"QuixBugs task `{name}`.",
            "buggy_file": f"src/{name}.py",
            "buggy_line": buggy_line,
            "hint_function": function_at_line(buggy_code, buggy_line),
            "source": "QuixBugs",
            "source_url": "https://github.com/jkoppel/QuixBugs",
            "difficulty_human": "easy",
            "difficulty_ai": "to_be_calibrated",
            "fix_size_lines": 1,
            "test_command": f"cd tasks_local/quixbugs/{task_id} && python -m pytest tests/ -v",
            "tags": ["quixbugs", "algorithm", "single_line"],
        }
        write_json(task_dir / "metadata.json", metadata)
        manifest.append({"task_id": task_id, "buggy_line": buggy_line})
    return manifest


def rehydrate_mini_nightmare() -> list[dict]:
    raw_base = DEBUG_GYM_REPO / "data" / "mini_nightmare"
    manifest = []

    for task_id in MINI_TASKS:
        name = task_id.replace("mini_nightmare_", "", 1)
        raw_task_dir = raw_base / name
        task_dir = TASKS_LOCAL_DIR / "mini_nightmare" / task_id
        src_dir = task_dir / "src"
        task_tests_dir = task_dir / "tests"
        src_dir.mkdir(parents=True, exist_ok=True)
        task_tests_dir.mkdir(parents=True, exist_ok=True)
        ensure_init(src_dir)
        ensure_init(task_tests_dir)

        buggy_code = (raw_task_dir / f"{name}_code.py").read_text(encoding="utf-8")
        adapted_test = (raw_task_dir / "test.py").read_text(encoding="utf-8")
        adapted_test = adapted_test.replace(
            f"from {name}_code import",
            f"from src.{name} import",
        )
        adapted_test = adapted_test.replace(
            f"import {name}_code",
            f"import src.{name} as {name}_code",
        )

        write_text(src_dir / f"{name}.py", buggy_code)
        write_text(task_tests_dir / f"test_{name}.py", adapted_test)

        for extra in raw_task_dir.iterdir():
            if extra.name in {f"{name}_code.py", "test.py", ".debugignore", ".debugreadonly"}:
                continue
            if extra.is_file():
                shutil.copy2(extra, task_dir / extra.name)

        fixed_code = apply_successful_edits(task_id, f"src/{name}.py", buggy_code)
        patch = unified_diff(buggy_code, fixed_code, f"src/{name}.py")
        write_text(task_dir / "patch.diff", patch)
        buggy_line = first_changed_line(buggy_code, fixed_code)

        metadata = {
            "task_id": task_id,
            "category": "mini_nightmare",
            "subcategory": "debug_gym",
            "bug_type": "multi_line_defect",
            "description": f"mini-nightmare task `{name}` from debug-gym.",
            "buggy_file": f"src/{name}.py",
            "buggy_line": buggy_line,
            "hint_function": function_at_line(buggy_code, buggy_line),
            "source": "debug-gym",
            "source_url": "https://github.com/microsoft/debug-gym",
            "difficulty_human": "easy",
            "difficulty_ai": "to_be_calibrated",
            "test_command": f"cd tasks_local/mini_nightmare/{task_id} && python -m pytest tests/ -v",
            "tags": ["mini_nightmare", "debug_gym"],
        }
        write_json(task_dir / "metadata.json", metadata)
        manifest.append({"task_id": task_id, "buggy_line": buggy_line})
    return manifest


def load_debugbench_row(benchmark_file: str, slug: str) -> dict:
    rows = json.loads((DEBUGBENCH_REPO / "benchmark" / benchmark_file).read_text(encoding="utf-8"))
    for row in rows:
        if row.get("slug") == slug:
            return row
    raise KeyError(f"Could not find DebugBench row {slug} in {benchmark_file}.")


def rehydrate_debugbench() -> list[dict]:
    manifest = []

    for task_id, info in DEBUGBENCH_TASKS.items():
        bug_category = info["bug_category"]
        slug = info["slug"]
        row = load_debugbench_row(info["benchmark_file"], slug)
        task_dir = TASKS_LOCAL_DIR / "debugbench" / bug_category / task_id
        src_dir = task_dir / "src"
        task_tests_dir = task_dir / "tests"
        src_dir.mkdir(parents=True, exist_ok=True)
        task_tests_dir.mkdir(parents=True, exist_ok=True)
        ensure_init(src_dir)
        ensure_init(task_tests_dir)

        buggy_body = row["buggy_code"].lstrip("\n")
        fixed_body = row["oracle_code"].lstrip("\n")
        buggy_code = DEBUGBENCH_IMPORT_BLOCK + buggy_body
        fixed_code = DEBUGBENCH_IMPORT_BLOCK + fixed_body
        test_code = find_observed_file(task_id, "tests/test_solution.py")

        write_text(src_dir / "solution.py", buggy_code)
        write_text(task_tests_dir / "test_solution.py", test_code)
        write_text(task_dir / "patch.diff", unified_diff(buggy_code, fixed_code, "src/solution.py"))

        buggy_line = first_changed_line(buggy_code, fixed_code)
        metadata = {
            "task_id": task_id,
            "category": "debugbench",
            "bug_category": bug_category,
            "subcategory": row.get("subtype", "unknown").replace(" ", "_"),
            "bug_type": row.get("subtype", "unknown").replace(" ", "_"),
            "description": row.get("description", row.get("question", "")),
            "buggy_file": "src/solution.py",
            "buggy_line": buggy_line,
            "hint_function": function_at_line(buggy_code, buggy_line),
            "source": "DebugBench",
            "source_url": "https://github.com/thunlp/DebugBench",
            "difficulty_human": row.get("level", "easy"),
            "difficulty_ai": "to_be_calibrated",
            "test_command": f"cd tasks_local/debugbench/{bug_category}/{task_id} && python -m pytest tests/ -v",
            "tags": ["debugbench", bug_category, row.get("subtype", "unknown").replace(" ", "_")],
        }
        write_json(task_dir / "metadata.json", metadata)
        manifest.append({"task_id": task_id, "buggy_line": buggy_line})
    return manifest


def main() -> None:
    ensure_repo("https://github.com/jkoppel/QuixBugs.git", QUIXBUGS_REPO)
    ensure_repo("https://github.com/microsoft/debug-gym.git", DEBUG_GYM_REPO)
    ensure_repo("https://github.com/thunlp/DebugBench.git", DEBUGBENCH_REPO)

    manifest = {
        "quixbugs": rehydrate_quixbugs(),
        "mini_nightmare": rehydrate_mini_nightmare(),
        "debugbench": rehydrate_debugbench(),
    }
    write_json(TASKS_LOCAL_DIR / "manifest.json", manifest)
    print(f"Wrote rehydrated tasks to {TASKS_LOCAL_DIR}")


if __name__ == "__main__":
    main()

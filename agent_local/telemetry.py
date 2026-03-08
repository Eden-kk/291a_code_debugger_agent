"""Structured telemetry collection for experiment runs.

Tracks cost-centric metrics aligned with the proposal (Section 9):
  - Patch attempt count (edit_file actions)
  - Test run count (run_tests actions)
  - Per-tool usage counts
  - First-edit turn and first-test turn
  - Per-turn token deltas for cost attribution
  - Token waste estimation
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional


def _category_from_task_id(task_id: str) -> str:
    """Infer result sub-path (source/bug_category) from task_id.

    DebugBench       → debugbench/<bug_category>  (looked up from metadata at save time)
    QuixBugs         → quixbugs
    Mini-nightmare   → mini_nightmare
    """
    if task_id.startswith("debugbench"):
        return "debugbench"
    if task_id.startswith("quixbugs"):
        return "quixbugs"
    if task_id.startswith("mini_nightmare"):
        return "mini_nightmare"
    return "other"


def _model_slug(model: str) -> str:
    """Normalize model ids so they are safe and informative in filenames."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", model).strip("-").lower()
    return slug[:48] or "unknown-model"


class Telemetry:
    """Collects turn-level events and produces a structured JSON result.

    Computes cost-centric metrics from the trajectory:
      - patch_attempt_count: number of edit_file tool calls
      - test_run_count: number of run_tests tool calls
      - file_view_count / search_count / list_files_count: exploration effort
      - first_edit_turn: turn of first edit_file call
      - first_test_turn: turn of first run_tests call
      - first_fix_turn: turn at which tests first pass (if ever)
      - per_turn_tokens: list of token deltas per turn
    """

    def __init__(
        self,
        task_id: str,
        protocol: str,
        strategy: str,
        model: str,
        hint_level: int = 0,
        category: Optional[str] = None,
    ):
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        model_slug = _model_slug(model)
        self.run_id = (
            f"{task_id}__{protocol}__{strategy}__{model_slug}"
            f"__h{hint_level}__{ts}"
        )
        self.task_id = task_id
        self.protocol = protocol
        self.strategy = strategy
        self.model = model
        self.hint_level = hint_level
        self.category = category or _category_from_task_id(task_id)
        self.events: list[dict] = []
        self.start_time = datetime.now(timezone.utc).isoformat()

        # ── Cost-centric counters ──
        self.tool_counts: dict[str, int] = {
            "edit_file": 0,
            "run_tests": 0,
            "view_file": 0,
            "search_code": 0,
            "list_files": 0,
        }
        self.first_edit_turn: Optional[int] = None
        self.first_test_turn: Optional[int] = None
        self.first_fix_turn: Optional[int] = None   # turn at which tests pass
        self.per_turn_tokens: list[dict] = []        # [{turn, input, output, total}]

        # ── Multi-episode tracking (for Reflexion / early_stop_restart) ──
        self.episodes: list[dict] = []  # per-episode summary
        self._current_episode = 1

    def add_event(self, turn: int, event_type: str, content: str):
        """Append a turn-level event."""
        self.events.append({
            "turn": turn,
            "type": event_type,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode": self._current_episode,
        })

    def record_tool_use(self, turn: int, tool_name: str):
        """Track tool usage for cost metrics."""
        if tool_name in self.tool_counts:
            self.tool_counts[tool_name] += 1
        if tool_name == "edit_file" and self.first_edit_turn is None:
            self.first_edit_turn = turn
        if tool_name == "run_tests" and self.first_test_turn is None:
            self.first_test_turn = turn

    def record_fix(self, turn: int):
        """Record the turn when tests first pass."""
        if self.first_fix_turn is None:
            self.first_fix_turn = turn

    def record_turn_tokens(self, turn: int, input_tokens: int, output_tokens: int):
        """Record per-turn token consumption."""
        self.per_turn_tokens.append({
            "turn": turn,
            "episode": self._current_episode,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        })

    def start_new_episode(self, episode_num: int, reason: str = ""):
        """Mark the beginning of a new episode (Reflexion retry, restart, etc.)."""
        self._current_episode = episode_num
        self.add_event(0, "system", f"Starting episode {episode_num}. {reason}")

    def record_episode_summary(
        self, episode: int, success: bool, turns: int,
        input_tokens: int, output_tokens: int,
    ):
        """Save summary for a completed episode."""
        self.episodes.append({
            "episode": episode,
            "success": success,
            "turns": turns,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        })

    def _compute_cost_metrics(self, total_turns: int) -> dict:
        """Derive cost-centric metrics from trajectory data."""
        # Count action events to determine tool breakdown
        action_events = [e for e in self.events if e["type"] == "action"]

        # Parse action events to get per-tool token attribution
        # (tokens in turns that contain each tool type)
        edit_turns = set()
        test_turns = set()
        explore_turns = set()  # view_file, search_code, list_files
        for ev in action_events:
            try:
                act = json.loads(ev["content"])
                tool = act.get("tool", "")
                t = ev["turn"]
                if tool == "edit_file":
                    edit_turns.add(t)
                elif tool == "run_tests":
                    test_turns.add(t)
                else:
                    explore_turns.add(t)
            except (json.JSONDecodeError, KeyError):
                pass

        # Token attribution by activity type
        tokens_in_editing = sum(
            tt["total_tokens"] for tt in self.per_turn_tokens
            if tt["turn"] in edit_turns
        )
        tokens_in_testing = sum(
            tt["total_tokens"] for tt in self.per_turn_tokens
            if tt["turn"] in test_turns
        )
        tokens_in_exploring = sum(
            tt["total_tokens"] for tt in self.per_turn_tokens
            if tt["turn"] in explore_turns
        )
        total_tracked = sum(tt["total_tokens"] for tt in self.per_turn_tokens)

        return {
            "patch_attempt_count": self.tool_counts["edit_file"],
            "test_run_count": self.tool_counts["run_tests"],
            "file_view_count": self.tool_counts["view_file"],
            "search_count": self.tool_counts["search_code"],
            "list_files_count": self.tool_counts["list_files"],
            "first_edit_turn": self.first_edit_turn,
            "first_test_turn": self.first_test_turn,
            "first_fix_turn": self.first_fix_turn,
            "total_tool_calls": sum(self.tool_counts.values()),
            "tokens_in_editing": tokens_in_editing,
            "tokens_in_testing": tokens_in_testing,
            "tokens_in_exploring": tokens_in_exploring,
            "token_efficiency": (
                round(tokens_in_editing / total_tracked, 4)
                if total_tracked > 0 else 0
            ),  # fraction of tokens spent on actual patching
            "episodes_used": len(self.episodes) if self.episodes else 1,
        }

    def finalize(
        self,
        success: bool,
        total_turns: int,
        total_input_tokens: int,
        total_output_tokens: int,
        total_cost_usd: float,
        wall_time_sec: float,
    ) -> dict:
        """Return the complete telemetry record as a dict."""
        cost_metrics = self._compute_cost_metrics(total_turns)

        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "category": self.category,
            "protocol": self.protocol,
            "strategy": self.strategy,
            "model": self.model,
            "hint_level": self.hint_level,
            "timestamp": self.start_time,
            "result": {
                "success": success,
                "total_turns": total_turns,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_tokens": total_input_tokens + total_output_tokens,
                "total_cost_usd": round(total_cost_usd, 6),
                "wall_time_sec": round(wall_time_sec, 2),
            },
            "cost_metrics": cost_metrics,
            "episodes": self.episodes if self.episodes else None,
            "per_turn_tokens": self.per_turn_tokens,
            "trajectory": self.events,
        }


def save_result(result: dict, output_dir: str = "results") -> str:
    """Persist a telemetry result to ``output_dir/<source>/<bug_category>/<run_id>.json``.

    Directory structure mirrors the tasks/ layout:
      results/debugbench/{logic_error,reference_error,...}/
      results/quixbugs/
      results/mini_nightmare/

    Returns the path to the written file.
    """
    category = result.get("category", _category_from_task_id(result["task_id"]))
    sub_dir = os.path.join(output_dir, category)
    os.makedirs(sub_dir, exist_ok=True)
    path = os.path.join(sub_dir, f"{result['run_id']}.json")
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    return path

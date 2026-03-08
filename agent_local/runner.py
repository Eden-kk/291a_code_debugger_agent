"""Agent runner — orchestrates a single debugging run end-to-end.

Supports three interaction protocols (act_only, react, reflexion) and
four debugging strategies (baseline, checklist, early_stop_restart,
self_consistency).  Tracks cost-centric metrics throughout.
"""

import ast
import json
import os
import re
import time
import uuid
from typing import Optional

from .hints import get_hint
from .llm_client import LLMClient
from .prompts import build_task_prompt, get_system_prompt
from .telemetry import Telemetry
from .tools import TOOL_SCHEMAS, TaskEnvironment


class AgentRunner:
    """Runs one debugging episode (or multiple for Reflexion / restart strategies)."""

    def __init__(
        self,
        task_dir: str,
        protocol: str = "react",
        model: str = "gpt-4o",
        temperature: float = 0.0,
        hint_level: int = 0,
        max_turns: int = 25,
        max_total_tokens: int = 50_000,
        strategy: Optional[str] = None,
        seed: Optional[int] = 42,
        backend: str = "openai",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.task_dir = task_dir
        self.protocol = protocol
        self.hint_level = hint_level
        self.max_turns = max_turns
        self.max_total_tokens = max_total_tokens
        self.strategy = strategy or "baseline"

        # Load metadata
        meta_path = os.path.join(task_dir, "metadata.json")
        with open(meta_path) as fh:
            self.metadata = json.load(fh)

        self.env = TaskEnvironment(task_dir)
        self.metadata["_work_dir"] = self.env.work_dir

        self.backend = backend
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model
        self.temperature = temperature
        self.seed = seed

        self.llm = LLMClient(
            model=model,
            temperature=temperature,
            seed=seed,
            backend=backend,
            base_url=base_url,
            api_key=api_key,
        )

        # Resolve result category
        task_id = self.metadata["task_id"]
        if task_id.startswith("debugbench"):
            bug_cat = self.metadata.get("bug_category", "other").replace(" ", "_")
            result_category = f"debugbench/{bug_cat}"
        elif task_id.startswith("quixbugs"):
            result_category = "quixbugs"
        elif task_id.startswith("mini_nightmare"):
            result_category = "mini_nightmare"
        else:
            result_category = "other"

        self.telemetry = Telemetry(
            task_id=task_id,
            protocol=protocol,
            strategy=self.strategy,
            model=model,
            hint_level=hint_level,
            category=result_category,
        )

    # --------------------------------------------------------------------- #
    #  Public entry point                                                     #
    # --------------------------------------------------------------------- #

    def run(self) -> dict:
        """Execute the full experiment and return the telemetry dict."""
        if self.strategy == "self_consistency":
            return self._run_self_consistency()
        if self.strategy == "early_stop_restart":
            return self._run_early_stop_restart()
        return self._run_standard()

    # --------------------------------------------------------------------- #
    #  Standard run (baseline, checklist, early_stop)                         #
    # --------------------------------------------------------------------- #

    def _run_standard(self) -> dict:
        """Standard single-episode (or Reflexion two-episode) run."""
        start = time.time()

        messages = self._initial_messages()
        success, turns, messages = self._run_episode(messages, episode=1)

        ep1_in = self.llm.total_input_tokens
        ep1_out = self.llm.total_output_tokens
        self.telemetry.record_episode_summary(1, success, turns, ep1_in, ep1_out)

        # Reflexion: one reflection + retry on failure
        if not success and self.protocol == "reflexion":
            self.telemetry.add_event(0, "system", "Episode 1 failed. Generating reflection …")
            reflection = self._generate_reflection(messages)
            self.telemetry.add_event(0, "reflection", reflection)

            self.env.reset()
            self.metadata["_work_dir"] = self.env.work_dir
            self.telemetry.start_new_episode(2, "Reflexion retry with reflection")

            messages = self._initial_messages(reflection=reflection)
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

    # --------------------------------------------------------------------- #
    #  Early-stop with restart strategy                                       #
    # --------------------------------------------------------------------- #

    def _run_early_stop_restart(self) -> dict:
        """Fixed-budget early stopping with restart.

        Strategy: allocate half the token budget per attempt.  If the first
        attempt exhausts its budget without success, reset the environment
        and try again with a fresh context.  Max 2 attempts.
        """
        start = time.time()
        per_attempt_budget = self.max_total_tokens // 2
        per_attempt_turns = self.max_turns // 2 + 2  # slight padding
        total_turns = 0
        success = False

        for attempt in range(1, 3):  # max 2 attempts
            if attempt > 1:
                # Reset environment and LLM context
                self.env.reset()
                self.metadata["_work_dir"] = self.env.work_dir
                self.telemetry.start_new_episode(attempt, "Budget exhausted — restarting with fresh context")

            tokens_before = self.llm.total_tokens
            messages = self._initial_messages()
            success, ep_turns, _ = self._run_episode(
                messages, episode=attempt,
                turn_limit=per_attempt_turns,
                token_limit=tokens_before + per_attempt_budget,
            )
            total_turns += ep_turns

            ep_in = self.llm.total_input_tokens - (
                sum(e["input_tokens"] for e in self.telemetry.episodes)
            )
            ep_out = self.llm.total_output_tokens - (
                sum(e["output_tokens"] for e in self.telemetry.episodes)
            )
            self.telemetry.record_episode_summary(attempt, success, ep_turns, ep_in, ep_out)

            if success:
                break

        wall = time.time() - start
        result = self.telemetry.finalize(
            success=success,
            total_turns=total_turns,
            total_input_tokens=self.llm.total_input_tokens,
            total_output_tokens=self.llm.total_output_tokens,
            total_cost_usd=self.llm.estimated_cost(),
            wall_time_sec=wall,
        )
        self.env.cleanup()
        return result

    # --------------------------------------------------------------------- #
    #  Self-consistency voting strategy                                        #
    # --------------------------------------------------------------------- #

    def _run_self_consistency(self, n_attempts: int = 3) -> dict:
        """Self-consistency voting: N independent short-budget attempts.

        Generate N independent patch attempts with varied seeds.  If any
        succeeds, report success with the cost of all attempts combined.
        Budget split: each attempt gets 1/N of tokens but at least 12 turns
        to allow a full diagnose-edit-test cycle.
        """
        start = time.time()
        per_attempt_budget = self.max_total_tokens // n_attempts
        # At least 12 turns per attempt — a minimal debugging cycle needs
        # ~6 turns (test→view→view→edit→test→done), plus margin for harder bugs
        per_attempt_turns = max(self.max_turns // n_attempts, 12)
        total_turns = 0
        any_success = False

        for attempt_idx in range(1, n_attempts + 1):
            if attempt_idx > 1:
                self.env.reset()
                self.metadata["_work_dir"] = self.env.work_dir
                self.telemetry.start_new_episode(
                    attempt_idx, f"Self-consistency attempt {attempt_idx}/{n_attempts}"
                )
                # Vary seed for diversity
                if self.seed is not None:
                    self.llm.seed = self.seed + attempt_idx - 1
                    self.llm.temperature = max(0.3, self.temperature)

            tokens_before = self.llm.total_tokens
            messages = self._initial_messages()
            success, ep_turns, _ = self._run_episode(
                messages, episode=attempt_idx,
                turn_limit=per_attempt_turns,
                token_limit=tokens_before + per_attempt_budget,
            )
            total_turns += ep_turns

            ep_in = self.llm.total_input_tokens - sum(
                e["input_tokens"] for e in self.telemetry.episodes
            )
            ep_out = self.llm.total_output_tokens - sum(
                e["output_tokens"] for e in self.telemetry.episodes
            )
            self.telemetry.record_episode_summary(
                attempt_idx, success, ep_turns, ep_in, ep_out
            )

            if success:
                any_success = True
                # Don't break — we want to know cost of all attempts
                # But for efficiency, break early
                break

        wall = time.time() - start
        result = self.telemetry.finalize(
            success=any_success,
            total_turns=total_turns,
            total_input_tokens=self.llm.total_input_tokens,
            total_output_tokens=self.llm.total_output_tokens,
            total_cost_usd=self.llm.estimated_cost(),
            wall_time_sec=wall,
        )
        self.env.cleanup()
        return result

    # --------------------------------------------------------------------- #
    #  Internal helpers                                                       #
    # --------------------------------------------------------------------- #

    def _initial_messages(self, reflection: Optional[str] = None) -> list[dict]:
        if getattr(self, '_system_prompt_override', None):
            sys_prompt = self._system_prompt_override
        else:
            sys_prompt = get_system_prompt(self.protocol, self.strategy)
        task_prompt = build_task_prompt(self.metadata, self.hint_level)
        msgs: list[dict] = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": task_prompt},
        ]
        if reflection:
            msgs.append({
                "role": "user",
                "content": (
                    "[REFLECTION FROM PREVIOUS ATTEMPT]\n"
                    f"{reflection}\n\n"
                    "Please try a DIFFERENT approach this time."
                ),
            })
        return msgs

    # -- Fallback text-based tool call parser --------------------------------

    @staticmethod
    def _parse_tool_call_from_text(text: str) -> Optional[dict]:
        """Try to extract a tool call from text content.

        Some local models (Ollama, etc.) output tool calls as JSON in their
        text response instead of using the formal ``tool_calls`` mechanism.
        Some hosted models also emit bracketed pseudo-calls like
        ``[search_code(query="find")]``.
        """
        if not text:
            return None

        valid_tools = {"view_file", "search_code", "edit_file", "run_tests", "list_files"}

        for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text):
            try:
                obj = json.loads(match.group())
            except json.JSONDecodeError:
                continue

            name = obj.get("name")
            args = obj.get("arguments") or obj.get("parameters") or {}

            if name in valid_tools:
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                return {"name": name, "arguments": args}

        for match in re.finditer(r"\[([A-Za-z_][A-Za-z0-9_]*)\((.*?)\)\]", text, re.DOTALL):
            name = match.group(1)
            if name not in valid_tools:
                continue

            arg_text = match.group(2).strip()
            if not arg_text:
                return {"name": name, "arguments": {}}

            try:
                call = ast.parse(f"_tool({arg_text})", mode="eval").body
            except SyntaxError:
                continue

            if not isinstance(call, ast.Call):
                continue

            if call.args:
                continue

            try:
                args = {
                    kw.arg: ast.literal_eval(kw.value)
                    for kw in call.keywords
                    if kw.arg is not None
                }
            except (ValueError, SyntaxError):
                continue

            return {"name": name, "arguments": args}

        return None

    # -- Execute a single parsed tool call and update state -------------------

    def _execute_and_record(
        self, turn: int, fn_name: str, fn_args: dict, messages: list[dict],
        tool_call_id: Optional[str] = None,
    ) -> bool:
        """Execute a tool call, record telemetry, append to messages.

        Returns True if the bug was fixed (all tests pass after run_tests).
        """
        # Track tool usage for cost metrics
        self.telemetry.record_tool_use(turn, fn_name)

        self.telemetry.add_event(
            turn, "action",
            json.dumps({"tool": fn_name, "args": fn_args}),
        )

        result_str = self.env.execute_tool(fn_name, fn_args)

        # Truncate very long observations
        truncated = result_str[:5000]
        if len(result_str) > 5000:
            truncated += f"\n… (truncated, {len(result_str)} chars total)"

        self.telemetry.add_event(turn, "observation", truncated)

        if tool_call_id:
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": truncated,
            })
        else:
            messages.append({
                "role": "user",
                "content": f"[Tool result for {fn_name}]\n{truncated}",
            })

        if fn_name == "run_tests" and self.env.all_tests_passed:
            self.telemetry.record_fix(turn)
            self.telemetry.add_event(turn, "system", "All tests passed — bug fixed!")
            return True
        return False

    def _no_tool_retry_limit(self) -> int:
        """Return how many empty/non-tool turns to tolerate before stopping."""
        if self.model_name.startswith("moonshotai.kimi"):
            return 5
        return 3

    def _no_tool_retry_prompt(self, no_tool_streak: int) -> str:
        """Return the follow-up prompt after a non-tool response."""
        if self.model_name.startswith("moonshotai.kimi"):
            return (
                "Your previous response did not include a tool call. "
                "Do not explain. Call exactly one available tool next."
            )
        return "Please use the available tools to continue debugging."

    # -- Main agent loop ------------------------------------------------------

    def _run_episode(
        self,
        messages: list[dict],
        episode: int = 1,
        turn_limit: Optional[int] = None,
        token_limit: Optional[int] = None,
    ) -> tuple[bool, int, list[dict]]:
        """Run the agent loop for one episode.

        Parameters
        ----------
        turn_limit : int, optional
            Override max_turns for this episode (used by strategies).
        token_limit : int, optional
            Absolute token ceiling (used by strategies). Defaults to
            self.max_total_tokens.

        Returns (success, turns_used, messages).
        """
        effective_max_turns = turn_limit or self.max_turns
        effective_token_limit = token_limit or self.max_total_tokens

        no_tool_streak = 0
        turns_used = 0

        for turn in range(1, effective_max_turns + 1):
            turns_used = turn

            # Budget guard
            if self.llm.total_tokens > effective_token_limit:
                self.telemetry.add_event(turn, "system", "Token budget exhausted.")
                break

            # Track tokens before this call
            tokens_before_in = self.llm.total_input_tokens
            tokens_before_out = self.llm.total_output_tokens

            # LLM call
            try:
                response = self.llm.chat(messages, tools=TOOL_SCHEMAS)
            except Exception as exc:
                self.telemetry.add_event(turn, "error", f"LLM error: {exc}")
                break

            # Record per-turn token delta
            turn_in = self.llm.total_input_tokens - tokens_before_in
            turn_out = self.llm.total_output_tokens - tokens_before_out
            self.telemetry.record_turn_tokens(turn, turn_in, turn_out)

            msg = response.choices[0].message

            # --- Record thought (text content) ---
            if msg.content:
                self.telemetry.add_event(turn, "thought", msg.content)

            # --- Path A: Formal tool_calls from the API ---
            if msg.tool_calls:
                no_tool_streak = 0
                messages.append(msg)

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    success = self._execute_and_record(
                        turn, fn_name, fn_args, messages,
                        tool_call_id=tc.id,
                    )
                    if success:
                        return True, turns_used, messages
                continue

            # --- Path B: Fallback — try to parse tool call from text ---
            parsed = self._parse_tool_call_from_text(msg.content)
            if parsed:
                no_tool_streak = 0
                messages.append({"role": "assistant", "content": msg.content})

                success = self._execute_and_record(
                    turn, parsed["name"], parsed["arguments"], messages,
                    tool_call_id=None,
                )
                if success:
                    return True, turns_used, messages
                continue

            # --- Path C: No tool call at all ---
            no_tool_streak += 1
            messages.append({"role": "assistant", "content": msg.content or ""})

            if no_tool_streak >= self._no_tool_retry_limit():
                self.telemetry.add_event(
                    turn, "system",
                    (
                        f"{self._no_tool_retry_limit()} consecutive responses "
                        "without tool calls — terminating."
                    ),
                )
                break

            messages.append({
                "role": "user",
                "content": self._no_tool_retry_prompt(no_tool_streak),
            })

        return False, turns_used, messages

    def _generate_reflection(self, messages: list[dict]) -> str:
        """Ask the model to reflect on a failed episode."""
        prompt = (
            "Your previous debugging attempt FAILED. "
            "Reflect briefly (3–5 sentences):\n"
            "1. What hypotheses did you try?\n"
            "2. What went wrong?\n"
            "3. What would you do differently next time?"
        )
        reflection_msgs = messages + [{"role": "user", "content": prompt}]
        try:
            resp = self.llm.chat(reflection_msgs, tools=None)
            return resp.choices[0].message.content or "No reflection generated."
        except Exception:
            return "Reflection generation failed."

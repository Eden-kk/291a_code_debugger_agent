"""Minimal-intervention hint system for Phase 3 experiments.

Hint levels
-----------
  L0 — No hint (baseline)
  L1 — Buggy file name
  L2 — Buggy function name (derived from source + buggy_line)
  L3 — Bug type category (semantic, non-localization hint)
  L4 — Buggy line number
"""

import os
from typing import Optional


def _find_function_at_line(filepath: str, line_number: int) -> Optional[str]:
    """Return the name of the function that contains *line_number* (1-indexed)."""
    if not os.path.isfile(filepath):
        return None
    with open(filepath, "r") as fh:
        current_func: Optional[str] = None
        for idx, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith("def "):
                name = stripped.split("(")[0].replace("def ", "").strip()
                current_func = name
            if idx == line_number:
                return current_func
    return None


# Human-readable labels for bug_type values
_BUG_TYPE_LABELS = {
    "off_by_one": "an off-by-one error (e.g., wrong loop bound)",
    "boolean_condition": "a boolean logic error (e.g., and vs or)",
    "operator": "a wrong operator (e.g., + instead of −)",
    "none_handling": "a missing None/null check",
    "type_mismatch": "a type mismatch error",
    "mutable_default": "a mutable default argument bug",
    "argument_order": "a swapped or wrong argument order",
    "return_value_ignored": "a return value that is not captured",
    "wrong_method": "a call to the wrong method",
    "empty_input": "a missing edge-case check for empty input",
    "boundary_value": "a boundary-value / edge-case error",
    "unicode_encoding": "a unicode / encoding handling error",
}


def get_hint(metadata: dict, level: int) -> Optional[str]:
    """Return the hint string for the given level, or *None* for L0."""
    if level <= 0:
        return None

    if level == 1:
        buggy_file = metadata.get("buggy_file", "unknown")
        return f"The bug is in the file `{buggy_file}`."

    if level == 2:
        buggy_file = metadata.get("buggy_file", "")
        buggy_line = metadata.get("buggy_line")
        if buggy_file and buggy_line:
            # Try to resolve the function name from a source file path.
            # During experiments the file lives in the task work-dir, so we
            # accept an optional base_dir via metadata; otherwise we return a
            # generic hint.
            base = metadata.get("_work_dir", "")
            full_path = os.path.join(base, buggy_file) if base else buggy_file
            func = _find_function_at_line(full_path, buggy_line)
            if func:
                return f"The bug is in the function `{func}` in `{buggy_file}`."
        return f"The bug is in `{metadata.get('buggy_file', 'unknown')}`."

    if level == 3:
        bug_type = metadata.get("bug_type", "unknown")
        label = _BUG_TYPE_LABELS.get(bug_type, f"a {bug_type.replace('_', ' ')} error")
        return f"This is {label}."

    if level >= 4:
        buggy_file = metadata.get("buggy_file", "unknown")
        buggy_line = metadata.get("buggy_line", "unknown")
        return f"The bug is on line {buggy_line} of `{buggy_file}`."

    return None

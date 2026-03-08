"""Agent-Computer Interface (ACI) tools for the debugging environment.

Provides a TaskEnvironment that manages an isolated copy of a debugging task
and exposes structured tools (view_file, search_code, edit_file, run_tests,
list_files) for the agent to interact with the codebase.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


# ---------------------------------------------------------------------------
# OpenAI function-calling tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "view_file",
            "description": "View the contents of a file. Optionally specify a line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from the project root.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed, inclusive). Optional.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (1-indexed, inclusive). Optional.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for a text pattern across all Python files in the project. Returns matching lines with file paths and line numbers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text string to search for (case-insensitive).",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing an exact text string with a new string. The old_text must match exactly (including whitespace and indentation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to edit.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "The exact text to find and replace.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "The replacement text.",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Run the pytest test suite and return the results. Use this to check if the bug has been fixed.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the specified directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Relative path to the directory. Defaults to the project root.",
                        "default": ".",
                    }
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Task Environment
# ---------------------------------------------------------------------------


class TaskEnvironment:
    """Manages an isolated copy of a debugging task and executes tools."""

    def __init__(self, task_dir: str):
        self.original_dir = os.path.abspath(task_dir)
        self.temp_root = tempfile.mkdtemp(prefix="debug_agent_")
        self.work_dir = os.path.join(self.temp_root, "task")
        shutil.copytree(self.original_dir, self.work_dir)

        self.all_tests_passed = False
        self.last_test_output: Optional[str] = None

    # -- public API ----------------------------------------------------------

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Dispatch a tool call and return the result string."""
        dispatch = {
            "view_file": self._view_file,
            "search_code": self._search_code,
            "edit_file": self._edit_file,
            "run_tests": self._run_tests,
            "list_files": self._list_files,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return f"Error: Unknown tool '{tool_name}'."
        try:
            return handler(**arguments)
        except Exception as exc:
            return f"Error executing {tool_name}: {exc}"

    def reset(self):
        """Reset the working copy to the original (clean) state."""
        if os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir)
        shutil.copytree(self.original_dir, self.work_dir)
        self.all_tests_passed = False
        self.last_test_output = None

    def cleanup(self):
        """Remove the entire temporary directory."""
        if os.path.exists(self.temp_root):
            shutil.rmtree(self.temp_root)

    # -- tool implementations ------------------------------------------------

    def _view_file(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> str:
        full_path = os.path.join(self.work_dir, path)
        if not os.path.isfile(full_path):
            return f"Error: File '{path}' not found."

        with open(full_path, "r") as fh:
            lines = fh.readlines()

        total = len(lines)
        if start_line is not None or end_line is not None:
            s = max(0, (start_line or 1) - 1)
            e = min(total, end_line or total)
            selected = lines[s:e]
            offset = s
            header = f"File: {path} (lines {s+1}–{e} of {total})\n"
        else:
            selected = lines
            offset = 0
            header = f"File: {path} ({total} lines)\n"

        numbered = "".join(
            f"{offset + i + 1:4d} | {line}" for i, line in enumerate(selected)
        )
        return header + numbered

    def _search_code(self, query: str) -> str:
        results: list[str] = []
        for root, dirs, files in os.walk(self.work_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, self.work_dir)
                with open(fpath, "r") as fh:
                    for i, line in enumerate(fh, 1):
                        if query.lower() in line.lower():
                            results.append(f"{rel}:{i}: {line.rstrip()}")
        if not results:
            return f"No results found for '{query}'."
        return f"Found {len(results)} match(es):\n" + "\n".join(results[:50])

    def _edit_file(self, path: str, old_text: str, new_text: str) -> str:
        full_path = os.path.join(self.work_dir, path)
        if not os.path.isfile(full_path):
            return f"Error: File '{path}' not found."

        with open(full_path, "r") as fh:
            content = fh.read()

        if old_text not in content:
            return (
                f"Error: old_text not found in '{path}'. "
                "Make sure it matches exactly (including whitespace)."
            )

        new_content = content.replace(old_text, new_text, 1)
        with open(full_path, "w") as fh:
            fh.write(new_content)
        return f"Successfully edited '{path}'."

    def _run_tests(self, **_kwargs) -> str:
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=self.work_dir,
                timeout=30,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            self.all_tests_passed = result.returncode == 0
            self.last_test_output = output
            tag = "ALL TESTS PASSED" if self.all_tests_passed else "SOME TESTS FAILED"
            return f"[{tag}]\n{output}"
        except subprocess.TimeoutExpired:
            self.all_tests_passed = False
            return "Error: Test execution timed out (30 s)."

    def _list_files(self, directory: str = ".") -> str:
        full_path = os.path.join(self.work_dir, directory)
        if not os.path.isdir(full_path):
            return f"Error: Directory '{directory}' not found."

        entries: list[str] = []
        for item in sorted(os.listdir(full_path)):
            if item.startswith(".") or item == "__pycache__":
                continue
            item_path = os.path.join(full_path, item)
            suffix = "/" if os.path.isdir(item_path) else ""
            entries.append(f"  {item}{suffix}")
        return f"Contents of '{directory}':\n" + "\n".join(entries)

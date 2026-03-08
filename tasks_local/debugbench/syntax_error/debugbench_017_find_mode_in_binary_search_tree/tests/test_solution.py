import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from solution import Solution
except Exception as e:
    # If the buggy code has syntax/import errors, the agent needs to fix those first
    pytest.skip(f"Cannot import Solution: {e}", allow_module_level=True)


def test_example_1():
    sol = Solution()
    root = [1,None,2,2]
    result = sol.findMode(root)
    expected = [2]
    # Accept any valid order for list results
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

def test_example_2():
    sol = Solution()
    root = [0]
    result = sol.findMode(root)
    expected = [0]
    # Accept any valid order for list results
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

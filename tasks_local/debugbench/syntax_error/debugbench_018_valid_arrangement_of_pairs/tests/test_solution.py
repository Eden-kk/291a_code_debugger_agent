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
    pairs = [[5,1],[4,5],[11,9],[9,4]]
    result = sol.validArrangement(pairs)
    expected = [[11,9],[9,4],[4,5],[5,1]]
    assert result == expected

def test_example_2():
    sol = Solution()
    pairs = [[1,3],[3,2],[2,1]]
    result = sol.validArrangement(pairs)
    expected = [[1,3],[3,2],[2,1]]
    assert result == expected

def test_example_3():
    sol = Solution()
    pairs = [[1,2],[1,3],[2,1]]
    result = sol.validArrangement(pairs)
    expected = [[1,2],[2,1],[1,3]]
    assert result == expected

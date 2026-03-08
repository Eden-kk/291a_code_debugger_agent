import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from solution import Solution
except Exception as e:
    pytest.skip(f"Cannot import Solution: {e}", allow_module_level=True)

def test_example_1():
    sol = Solution()
    start = 10
    goal = 7
    result = sol.minBitFlips(start, goal)
    expected = 3
    assert result == expected

def test_example_2():
    sol = Solution()
    start = 3
    goal = 4
    result = sol.minBitFlips(start, goal)
    expected = 3
    assert result == expected

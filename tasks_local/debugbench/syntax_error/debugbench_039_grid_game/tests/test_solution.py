import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from solution import Solution
except Exception as e:
    pytest.skip(f"Cannot import Solution: {e}", allow_module_level=True)

def test_example_1():
    sol = Solution()
    grid = [[2,5,4],[1,5,1]]
    result = sol.gridGame(grid)
    expected = 4
    assert result == expected

def test_example_2():
    sol = Solution()
    grid = [[3,3,1],[8,5,2]]
    result = sol.gridGame(grid)
    expected = 4
    assert result == expected

def test_example_3():
    sol = Solution()
    grid = [[1,3,1,15],[1,3,3,1]]
    result = sol.gridGame(grid)
    expected = 7
    assert result == expected

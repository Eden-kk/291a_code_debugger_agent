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
    n = "00000010100101000001111010011100"  # binary/octal literal — convert as needed
    result = sol.f(n)
    expected = 964176192 (00111001011110000010100101000000)
    assert result == expected

def test_example_2():
    sol = Solution()
    n = 11111111111111111111111111111101
    result = sol.f(n)
    expected = 3221225471 (10111111111111111111111111111111)
    assert result == expected

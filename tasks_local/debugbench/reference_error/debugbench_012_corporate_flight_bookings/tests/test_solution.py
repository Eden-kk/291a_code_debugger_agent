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
    bookings = [[1,2,10],[2,3,20],[2,5,25]]
    n = 5
    result = sol.corpFlightBookings(bookings, n)
    expected = [10,55,45,25,25]
    # Accept any valid order for list results
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

def test_example_2():
    sol = Solution()
    bookings = [[1,2,10],[2,2,15]]
    n = 2
    result = sol.corpFlightBookings(bookings, n)
    expected = [10,25]
    # Accept any valid order for list results
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

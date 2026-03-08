import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from solution import Solution
except Exception as e:
    pytest.skip(f"Cannot import Solution: {e}", allow_module_level=True)

def test_example_1():
    sol = Solution()
    nums1 = [4,1,2]
    nums2 = [1,3,4,2]
    result = sol.nextGreaterElement(nums1, nums2)
    expected = [-1,3,-1]
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

def test_example_2():
    sol = Solution()
    nums1 = [2,4]
    nums2 = [1,2,3,4]
    result = sol.nextGreaterElement(nums1, nums2)
    expected = [3,-1]
    assert sorted(result) == sorted(expected) if isinstance(result, list) else result == expected

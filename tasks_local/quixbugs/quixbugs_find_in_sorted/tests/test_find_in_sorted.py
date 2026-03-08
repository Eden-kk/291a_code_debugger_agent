import pytest
import json
import os

from src.find_in_sorted import find_in_sorted


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "find_in_sorted.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_find_in_sorted(input_data, expected):
    assert find_in_sorted(*input_data) == expected

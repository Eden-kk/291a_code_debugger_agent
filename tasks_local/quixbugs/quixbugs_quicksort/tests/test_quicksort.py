import pytest
import json
import os

from src.quicksort import quicksort


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "quicksort.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_quicksort(input_data, expected):
    assert quicksort(*input_data) == expected

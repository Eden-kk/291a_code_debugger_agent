import pytest
import json
import os

from src.mergesort import mergesort


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "mergesort.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_mergesort(input_data, expected):
    assert mergesort(*input_data) == expected

import pytest
import json
import os

from src.wrap import wrap


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "wrap.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_wrap(input_data, expected):
    assert wrap(*input_data) == expected

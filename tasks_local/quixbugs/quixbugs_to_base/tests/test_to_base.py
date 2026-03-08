import pytest
import json
import os

from src.to_base import to_base


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "to_base.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_to_base(input_data, expected):
    assert to_base(*input_data) == expected

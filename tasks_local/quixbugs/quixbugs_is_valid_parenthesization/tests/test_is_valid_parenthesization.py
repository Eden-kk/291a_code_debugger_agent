import pytest
import json
import os

from src.is_valid_parenthesization import is_valid_parenthesization


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "is_valid_parenthesization.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_is_valid_parenthesization(input_data, expected):
    assert is_valid_parenthesization(*input_data) == expected

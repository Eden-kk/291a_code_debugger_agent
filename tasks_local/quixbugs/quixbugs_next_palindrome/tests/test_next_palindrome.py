import pytest
import json
import os

from src.next_palindrome import next_palindrome


_test_dir = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_test_dir, "next_palindrome.json")) as _f:
    testdata = json.load(_f)


@pytest.mark.parametrize("input_data,expected", testdata)
def test_next_palindrome(input_data, expected):
    assert next_palindrome(*input_data) == expected

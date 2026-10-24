import pytest
from calculator import divide


def test_normal_division():
    assert divide(10, 2) == 5


def test_division_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)

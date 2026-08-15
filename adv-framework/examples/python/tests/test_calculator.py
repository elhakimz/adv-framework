import pytest

from calculator import add, divide, multiply, subtract


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


def test_subtract_returns_difference() -> None:
    assert subtract(5, 3) == 2


def test_multiply_returns_product() -> None:
    assert multiply(4, 3) == 12


def test_divide_returns_quotient() -> None:
    assert divide(10, 2) == 5.0


def test_divide_by_zero_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        divide(10, 0)

"""Property tests for the calculator module — see tests/test_calculator.py for
the unit tests these complement. Marked `property` so the local pre-push
hook's Unit stage (`-m "not property and not regression"`) skips these and
the Property stage (`-m property`) runs only these."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from calculator import add, divide, multiply


@pytest.mark.property
@given(a=st.integers(), b=st.integers())
def test_add_is_commutative(a: int, b: int) -> None:
    assert add(a, b) == add(b, a)


@pytest.mark.property
@given(a=st.integers(), b=st.integers())
def test_multiply_is_commutative(a: int, b: int) -> None:
    assert multiply(a, b) == multiply(b, a)


@pytest.mark.property
@given(a=st.integers(), b=st.integers().filter(lambda x: x != 0))
def test_divide_never_raises_for_nonzero_divisor(a: int, b: int) -> None:
    divide(a, b)


@pytest.mark.property
@given(a=st.integers())
def test_divide_by_zero_always_raises_zero_division_error(a: int) -> None:
    with pytest.raises(ZeroDivisionError):
        divide(a, 0)

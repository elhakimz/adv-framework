"""Complexity-bound tests for calculator.search.

Marked `property` so ADV's Property gate (#4) runs them: these are
properties over input size, and the existing `-m property` stage picks
them up with no pipeline change.

The harness is imported from the shipped asset by path, not copied, so
this example exercises the real artifact.
"""
import importlib.util
import sys
from pathlib import Path

import pytest

from calculator.search import contains, has_duplicates

# adv-framework/examples/python/tests/ -> parents[3] == adv-framework/
_HARNESS = (Path(__file__).resolve().parents[3]
            / "assets" / "python" / "bigo_harness.py")
_spec = importlib.util.spec_from_file_location("bigo_harness", _HARNESS)
bh = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = bh
_spec.loader.exec_module(bh)

SIZES = [16, 64, 256, 1024]          # 64x span, satisfies MIN_SPAN


@pytest.mark.property
def test_contains_is_linear():
    """Worst case: the needle is absent, so the whole list is scanned."""
    bh.assert_complexity_bound(
        lambda data: contains(data, -1), "O(n)", SIZES)


@pytest.mark.property
def test_has_duplicates_is_quadratic():
    bh.assert_complexity_bound(
        lambda data: has_duplicates(data), "O(n^2)", SIZES)


@pytest.mark.property
def test_the_gate_actually_fires_on_a_wrong_declaration():
    """Proves the gate is not vacuous.

    Declaring O(n) for a quadratic routine MUST fail. Without this, a
    harness that silently passed everything would look identical to a
    working one in this suite.
    """
    with pytest.raises(AssertionError, match=r"bound exceeded"):
        bh.assert_complexity_bound(
            lambda data: has_duplicates(data), "O(n)", SIZES)

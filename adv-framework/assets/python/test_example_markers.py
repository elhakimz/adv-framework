"""
Example showing how the three test categories are distinguished so the
CI pipeline's -m "property" / -m "regression" / -m "not property and not regression"
filters actually work. Adapt the import paths to your real module structure.
"""

import pytest
from hypothesis import given, strategies as st

# from src.mymodule import calculate_something


# ---------------------------------------------------------------------------
# UNIT TEST — no marker, picked up by the default `unit-test` CI job
# ---------------------------------------------------------------------------

def test_calculate_something_known_case():
    # result = calculate_something(10, 5)
    # assert result == 15
    pass


# ---------------------------------------------------------------------------
# PROPERTY TEST — marked, only runs in the `property-test` CI job.
# Hypothesis generates hundreds of inputs automatically and shrinks any
# failure down to the smallest reproducing example.
# ---------------------------------------------------------------------------

@pytest.mark.property
@given(a=st.integers(), b=st.integers())
def test_calculate_something_is_commutative(a, b):
    # assert calculate_something(a, b) == calculate_something(b, a)
    pass


@pytest.mark.property
@given(values=st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1))
def test_output_never_negative(values):
    # result = calculate_something(*values)
    # assert result >= 0
    pass


# ---------------------------------------------------------------------------
# REGRESSION TEST — marked, only runs in the `golden-file-regression` CI job.
# syrupy compares against a committed snapshot file; first run creates it,
# subsequent runs diff against it. Use `pytest --snapshot-update` to
# intentionally update a snapshot after a verified behavior change.
# ---------------------------------------------------------------------------

@pytest.mark.regression
def test_report_output_matches_snapshot(snapshot):
    # result = generate_report(sample_input)
    # assert result == snapshot
    pass

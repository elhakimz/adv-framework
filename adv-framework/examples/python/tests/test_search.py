from calculator.search import contains, has_duplicates


def test_contains_finds_present_value() -> None:
    assert contains([1, 2, 3], 2) is True


def test_contains_reports_absent_value() -> None:
    assert contains([1, 2, 3], 4) is False


def test_contains_on_empty_list_is_false() -> None:
    assert contains([], 1) is False


def test_has_duplicates_true_when_present() -> None:
    assert has_duplicates([1, 2, 3, 2]) is True


def test_has_duplicates_false_when_absent() -> None:
    assert has_duplicates([1, 2, 3]) is False


def test_has_duplicates_on_empty_list_is_false() -> None:
    assert has_duplicates([]) is False

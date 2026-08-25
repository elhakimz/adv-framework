"""Collection routines with deliberately different complexity classes.

These exist so the complexity-bound harness has something meaningful to
verify. The calculator module itself is scalar arithmetic, which has no
interesting asymptotic behaviour.
"""


def contains(haystack: list[int], needle: int) -> bool:
    """Linear scan. O(n).

    Deliberately does NOT use `needle in haystack` -- that would be one
    __contains__ call, which the harness charges as len(haystack) in a
    single step. The explicit loop is what makes the growth observable
    per element.
    """
    return any(item == needle for item in haystack)


def has_duplicates(values: list[int]) -> bool:
    """Naive pairwise comparison. O(n^2).

    A hash-set implementation would be O(n); this is the deliberately
    quadratic version, so the example can demonstrate both a bound that
    holds and a declaration that is wrong.
    """
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            if values[i] == values[j]:
                return True
    return False

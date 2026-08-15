"""Simple calculator functions used to demonstrate the ADV local pre-push hook."""


def add(a: int, b: int) -> int:
    """Return the sum of a and b."""
    return a + b


def subtract(a: int, b: int) -> int:
    """Return a minus b."""
    return a - b


def multiply(a: int, b: int) -> int:
    """Return the product of a and b."""
    return a * b


def divide(a: int, b: int) -> float:
    """Return a divided by b.

    Raises:
        ZeroDivisionError: if b is 0.
    """
    if b == 0:
        raise ZeroDivisionError("b must not be zero")
    return a / b

from datetime import date

import pytest

from dq import patterns


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-25", date(2026, 10, 25)),
        ("25/10/2026", date(2026, 10, 25)),
        ("2026/10/25", date(2026, 10, 25)),
        ("2026-02-30", None),
        ("31/04/2026", None),
        ("hier", None),
    ],
)
def test_parse_date(value, expected):
    assert patterns.parse_date(value) == expected


@pytest.mark.parametrize(
    ("dtype", "value", "expected"),
    [
        ("courriel", "a@example.com", True),
        ("courriel", "a@example", False),
        ("code_postal", "H2X 1Y4", True),
        ("code_postal", "D2X 1Y4", False),
        ("telephone", "+1 514 555 0101", True),
        ("telephone", "155-555-0101", False),
        ("nombre", "1 234,56", True),
        ("nombre", "12a", False),
        ("texte", "n'importe quoi", True),
    ],
)
def test_is_valid(dtype, value, expected):
    assert patterns.is_valid(dtype, value) is expected


@pytest.mark.parametrize(
    ("dtype", "value", "expected"),
    [
        ("date", "25/10/2026", "%d/%m/%Y"),
        ("telephone", "(514) 555-0101", "(999) 999-9999"),
        ("code_postal", "h2x1y4", "A9A9A9"),
        ("nombre", "12,50", "décimale « , »"),
        ("nombre", "12", None),
        ("texte", "abc", None),
    ],
)
def test_shape(dtype, value, expected):
    assert patterns.shape(dtype, value) == expected

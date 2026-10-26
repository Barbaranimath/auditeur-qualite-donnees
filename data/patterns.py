"""Regular expressions for the value formats the auditor recognises."""

import re
from datetime import date, datetime

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# Canadian postal code: letters D, F, I, O, Q, U never appear; W and Z never start a code.
POSTAL_CODE_CA = re.compile(
    r"^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d$", re.IGNORECASE
)

# North American number: area code and exchange both start with 2-9.
PHONE_NANP = re.compile(r"^(?:\+?1[ .-]?)?\(?([2-9]\d{2})\)?[ .-]?([2-9]\d{2})[ .-]?(\d{4})$")

# A phone written with visible formatting (separators or parentheses), not a bare digit run.
PHONE_FORMATTED = re.compile(r"[ .()\-+]")

# Nine digits in three groups (the Canadian SIN layout). An identifier, not a quantity.
SIN_LAYOUT = re.compile(r"^\d{3}[ -]\d{3}[ -]\d{3}$")

NUMBER = re.compile(r"^-?(?:\d{1,3}(?:[ \N{NO-BREAK SPACE}]\d{3})+|\d+)(?:[.,]\d+)?$")

DATE_PATTERNS: dict[str, re.Pattern[str]] = {
    "%Y-%m-%d": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "%d/%m/%Y": re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    "%Y/%m/%d": re.compile(r"^\d{4}/\d{2}/\d{2}$"),
}


def date_format_of(value: str) -> str | None:
    """Return the strftime format a date string is written in, or None if it is not a date."""
    for fmt, pattern in DATE_PATTERNS.items():
        if pattern.match(value):
            return fmt
    return None


def parse_date(value: str) -> date | None:
    """Return the calendar date a string names, or None if it is malformed or impossible."""
    fmt = date_format_of(value)
    if fmt is None:
        return None
    try:
        return datetime.strptime(value, fmt).date()
    except ValueError:  # e.g. 2026-02-30
        return None


def is_valid(dtype: str, value: str) -> bool:
    """Return True when a value is a well-formed instance of the detected column type."""
    checks = {
        "courriel": lambda v: EMAIL.match(v),
        "code_postal": lambda v: POSTAL_CODE_CA.match(v),
        "telephone": lambda v: PHONE_NANP.match(v),
        "date": parse_date,
        "nombre": lambda v: NUMBER.match(v),
    }
    return bool(checks[dtype](value)) if dtype in checks else True


def shape(dtype: str, value: str) -> str | None:
    """Return the written layout of a value (e.g. "999-999-9999"), or None when layout is moot."""
    if dtype == "date":
        return date_format_of(value)
    if dtype in ("telephone", "code_postal"):
        return re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", value))
    if dtype == "nombre":
        match = re.search(r"[.,](?=\d+$)", value)
        return f"décimale « {match.group()} »" if match else None
    return None

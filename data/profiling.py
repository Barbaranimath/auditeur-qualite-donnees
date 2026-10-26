"""Detect what kind of values each column holds."""

import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from dq import patterns

MATCH_THRESHOLD = 0.80  # A column gets a type when at least 80 % of its filled values fit it.
PHONE_NAME_HINTS = ("tel", "phone", "cell", "mobile")

TYPES = ("courriel", "code_postal", "telephone", "date", "nombre", "texte")


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    dtype: str
    filled: int
    match_rate: float  # Share of filled values that fit the detected type (1.0 for texte).


def name_tokens(name: str) -> set[str]:
    """Split a column name into unaccented lowercase words: "Numéro_Client" -> numero, client."""
    plain = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return set(re.split(r"[^a-z0-9]+", plain)) - {""}


def filled_values(series: pd.Series) -> pd.Series:
    """Return the non-null, non-blank values of a column, stripped, as strings."""
    values = series.dropna().astype(str).str.strip()
    return values[values != ""]


def _share(values: pd.Series, predicate) -> float:
    return float(values.map(lambda v: bool(predicate(v))).mean())


def _looks_like_phone(name: str, values: pd.Series) -> float:
    """Phone match rate, or 0 when the column could just as well be a plain number."""
    rate = _share(values, patterns.PHONE_NANP.match)
    has_hint = any(hint in name.lower() for hint in PHONE_NAME_HINTS)
    formatted = _share(values, patterns.PHONE_FORMATTED.search) >= 0.5
    return rate if (has_hint or formatted) else 0.0


def detect_type(name: str, series: pd.Series) -> tuple[str, float]:
    """Return the detected type of a column and the share of values that fit it."""
    values = filled_values(series)
    if values.empty:
        return "texte", 1.0

    if _share(values, patterns.SIN_LAYOUT.match) >= MATCH_THRESHOLD:
        return "texte", 1.0  # "123 456 789" would otherwise read as a French-formatted number.

    candidates = [
        ("courriel", _share(values, patterns.EMAIL.match)),
        ("code_postal", _share(values, patterns.POSTAL_CODE_CA.match)),
        ("telephone", _looks_like_phone(name, values)),
        ("date", _share(values, patterns.date_format_of)),
        ("nombre", _share(values, patterns.NUMBER.match)),
    ]
    for dtype, rate in candidates:
        if rate >= MATCH_THRESHOLD:
            return dtype, round(rate, 4)
    return "texte", 1.0


def profile(df: pd.DataFrame) -> dict[str, ColumnProfile]:
    """Profile every column of a DataFrame."""
    result = {}
    for col in df.columns:
        dtype, rate = detect_type(col, df[col])
        result[col] = ColumnProfile(col, dtype, len(filled_values(df[col])), rate)
    return result

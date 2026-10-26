"""Quality dimension scores, each from 0 (worst) to 100 (best)."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from dq import patterns
from dq.profiling import ColumnProfile, filled_values, name_tokens


def is_filled(series: pd.Series) -> pd.Series:
    """Return a boolean mask: True where the cell holds a non-null, non-blank value."""
    return series.notna() & (series.astype(str).str.strip() != "")


def completeness(series: pd.Series) -> float:
    """Return the share of non-null, non-blank values, from 0 to 100."""
    if series.empty:
        return 100.0
    return round(float(is_filled(series).mean()) * 100, 1)


def completeness_by_column(df: pd.DataFrame) -> pd.Series:
    """Return the completeness score of every column, lowest first."""
    scores = pd.Series({col: completeness(df[col]) for col in df.columns}, dtype=float)
    return scores.sort_values(kind="stable")


def completeness_score(df: pd.DataFrame) -> float:
    """Return the share of filled cells across the whole table, from 0 to 100."""
    if df.empty:
        return 100.0
    filled = sum(int(is_filled(df[col]).sum()) for col in df.columns)
    return round(filled / df.size * 100, 1)


# --- Uniqueness -----------------------------------------------------------------------------

KEY_NAME_TOKENS = {"id", "identifiant", "code", "matricule", "numero", "num", "no"}
NOT_KEY_TYPES = {"code_postal", "telephone", "courriel", "date"}
MIN_KEY_UNIQUENESS = 0.90


def detect_key_column(df: pd.DataFrame, profiles: dict[str, ColumnProfile]) -> str | None:
    """Pick the column that identifies a record: a key-like name and the most distinct values.

    Ties go to the leftmost column. Returns None when no column qualifies, in which case
    duplicates are judged on whole rows.
    """
    best, best_ratio = None, MIN_KEY_UNIQUENESS
    for col in df.columns:
        if profiles[col].dtype in NOT_KEY_TYPES or not (name_tokens(col) & KEY_NAME_TOKENS):
            continue
        values = df[col][is_filled(df[col])]
        if values.empty:
            continue
        ratio = values.nunique() / len(df)
        if ratio > best_ratio or (best is None and ratio >= best_ratio):
            best, best_ratio = col, ratio
    return best


@dataclass(frozen=True)
class UniquenessResult:
    score: float
    key: str | None  # None means whole rows were compared
    duplicates_on_key: int
    duplicate_rows: int


def uniqueness(df: pd.DataFrame, key: str | None) -> UniquenessResult:
    """Return the share of records that are not repeats, judged on the key or on whole rows."""
    duplicate_rows = int(df.duplicated().sum())
    if key is None:
        on_key = duplicate_rows
    else:
        filled = df[key][is_filled(df[key])].astype(str).str.strip()
        on_key = int(filled.duplicated().sum())
    score = 100.0 if df.empty else round((1 - on_key / len(df)) * 100, 1)
    return UniquenessResult(score, key, on_key, duplicate_rows)


# --- Validity -------------------------------------------------------------------------------

CHECKED_TYPES = ("courriel", "code_postal", "telephone", "date", "nombre")


@dataclass(frozen=True)
class ColumnCount:
    """How many filled values of a column were checked and how many passed."""

    checked: int
    passed: int

    @property
    def score(self) -> float:
        return 100.0 if self.checked == 0 else round(self.passed / self.checked * 100, 1)


def _weighted_score(counts: dict[str, ColumnCount]) -> float | None:
    checked = sum(c.checked for c in counts.values())
    if checked == 0:
        return None
    return round(sum(c.passed for c in counts.values()) / checked * 100, 1)


def validity(
    df: pd.DataFrame, profiles: dict[str, ColumnProfile]
) -> tuple[float | None, dict[str, ColumnCount]]:
    """Score how many filled values are well-formed for their column type.

    Free-text columns have no format to check and are left out. Returns None when no
    column has a checkable type.
    """
    counts = {}
    for col, prof in profiles.items():
        if prof.dtype not in CHECKED_TYPES:
            continue
        values = filled_values(df[col])
        passed = int(values.map(lambda v, t=prof.dtype: patterns.is_valid(t, v)).sum())
        counts[col] = ColumnCount(len(values), passed)
    return _weighted_score(counts), counts


# --- Consistency ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ConsistencyDetail:
    count: ColumnCount  # passed = values written in the column's dominant layout
    layouts: dict[str, int]  # every layout seen, most common first


def consistency(
    df: pd.DataFrame, profiles: dict[str, ColumnProfile]
) -> tuple[float | None, dict[str, ConsistencyDetail]]:
    """Score how many valid values follow their column's most common written layout."""
    details = {}
    for col, prof in profiles.items():
        values = filled_values(df[col])
        valid = values[values.map(lambda v, t=prof.dtype: patterns.is_valid(t, v))]
        layouts = valid.map(lambda v, t=prof.dtype: patterns.shape(t, v)).dropna()
        if layouts.empty:
            continue
        counts = layouts.value_counts()
        details[col] = ConsistencyDetail(
            ColumnCount(len(layouts), int(counts.iloc[0])), {k: int(v) for k, v in counts.items()}
        )
    return _weighted_score({c: d.count for c, d in details.items()}), details


# --- Freshness ------------------------------------------------------------------------------

FRESH_DAYS = 30  # Full marks when the latest record is at most a month old...
STALE_DAYS = 365  # ...and zero once it is a year old, falling linearly in between.


@dataclass(frozen=True)
class FreshnessResult:
    score: float
    column: str
    latest: date
    age_days: int


def freshness(
    df: pd.DataFrame, profiles: dict[str, ColumnProfile], today: date
) -> FreshnessResult | None:
    """Score how recent the newest date in the table is. None when there is no date column.

    Dates after `today` are ignored: they are typos or planned events, not activity.
    """
    newest: tuple[date, str] | None = None
    for col, prof in profiles.items():
        if prof.dtype != "date":
            continue
        dates = [d for d in filled_values(df[col]).map(patterns.parse_date) if d and d <= today]
        if dates and (newest is None or max(dates) > newest[0]):
            newest = (max(dates), col)
    if newest is None:
        return None
    latest, column = newest
    age = (today - latest).days
    share = (STALE_DAYS - age) / (STALE_DAYS - FRESH_DAYS)
    score = round(min(1.0, max(0.0, share)) * 100, 1)
    return FreshnessResult(score, column, latest, age)

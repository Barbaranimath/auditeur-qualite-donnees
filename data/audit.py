"""Run every quality check on a table and combine them into one result."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from dq import dimensions as dim
from dq.pii import PiiFinding, scan
from dq.profiling import ColumnProfile, profile

DIMENSION_NAMES = ("Complétude", "Unicité", "Validité", "Cohérence", "Fraîcheur")


@dataclass(frozen=True)
class AuditResult:
    rows: int
    profiles: dict[str, ColumnProfile]
    scores: dict[str, float | None]  # None = dimension not applicable to this table
    overall: float
    completeness_by_column: pd.Series
    uniqueness: dim.UniquenessResult
    validity_by_column: dict[str, dim.ColumnCount]
    consistency_by_column: dict[str, dim.ConsistencyDetail]
    freshness: dim.FreshnessResult | None
    personal_data: list[PiiFinding]  # compliance finding, not part of the quality score


def audit(df: pd.DataFrame, today: date | None = None) -> AuditResult:
    """Score a table on the five dimensions; the overall score averages the applicable ones."""
    today = today or date.today()
    profiles = profile(df)
    uniqueness = dim.uniqueness(df, dim.detect_key_column(df, profiles))
    validity_score, validity_cols = dim.validity(df, profiles)
    consistency_score, consistency_cols = dim.consistency(df, profiles)
    fresh = dim.freshness(df, profiles, today)

    scores = dict(
        zip(
            DIMENSION_NAMES,
            (
                dim.completeness_score(df),
                uniqueness.score,
                validity_score,
                consistency_score,
                fresh.score if fresh else None,
            ),
            strict=True,
        )
    )
    applicable = [s for s in scores.values() if s is not None]
    return AuditResult(
        rows=len(df),
        profiles=profiles,
        scores=scores,
        overall=round(sum(applicable) / len(applicable), 1),
        completeness_by_column=dim.completeness_by_column(df),
        uniqueness=uniqueness,
        validity_by_column=validity_cols,
        consistency_by_column=consistency_cols,
        freshness=fresh,
        personal_data=scan(df, profiles),
    )

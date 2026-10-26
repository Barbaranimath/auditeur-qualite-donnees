from datetime import date

import pandas as pd

from dq.audit import DIMENSION_NAMES, audit
from dq.io import load_table


def test_demo_audit_finds_every_injected_error():
    result = audit(load_table("data/demo_clients.csv"), today=date(2026, 10, 20))
    assert result.scores == {
        "Complétude": 99.4,
        "Unicité": 97.0,
        "Validité": 99.4,
        "Cohérence": 95.0,
        "Fraîcheur": 100.0,
    }
    assert result.overall == 98.2
    assert result.rows == 5000
    assert result.uniqueness.key == "client_id"


def test_overall_averages_only_applicable_dimensions():
    df = pd.DataFrame({"note": ["a", None, "a"]})  # no typed column, no date
    result = audit(df, today=date(2026, 10, 25))
    assert result.scores["Validité"] is None
    assert result.scores["Cohérence"] is None
    assert result.scores["Fraîcheur"] is None
    assert result.freshness is None
    # Row 3 repeats row 1, and one cell of three is blank.
    assert result.scores["Complétude"] == 66.7
    assert result.scores["Unicité"] == 66.7
    assert result.overall == 66.7


def test_dimension_order_is_stable():
    result = audit(pd.DataFrame({"a": ["x"]}), today=date(2026, 10, 25))
    assert tuple(result.scores) == DIMENSION_NAMES


def test_defaults_to_today():
    result = audit(pd.DataFrame({"maj": [date.today().isoformat()]}))
    assert result.freshness.age_days == 0

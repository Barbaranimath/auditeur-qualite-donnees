from datetime import date

import pandas as pd
import pytest

from dq import dimensions as dim
from dq.dimensions import completeness, completeness_by_column, completeness_score, is_filled
from dq.io import load_table
from dq.profiling import profile


def test_completeness_counts_nulls_and_blanks_as_missing():
    assert completeness(pd.Series(["a", None, "", "   ", "b"], dtype="object")) == 40.0


def test_completeness_empty_column_is_100():
    assert completeness(pd.Series([], dtype="object")) == 100.0


def test_completeness_all_null_column_is_0():
    assert completeness(pd.Series([None, None, None], dtype="object")) == 0.0


def test_completeness_full_column_is_100():
    assert completeness(pd.Series(["Montréal", "Québec"])) == 100.0


def test_completeness_single_row():
    assert completeness(pd.Series([None], dtype="object")) == 0.0


def test_completeness_zero_and_false_are_values():
    assert completeness(pd.Series([0, False, "0"], dtype="object")) == 100.0


def test_is_filled_mask():
    mask = is_filled(pd.Series(["x", None, " "], dtype="object"))
    assert list(mask) == [True, False, False]


def test_by_column_sorted_lowest_first():
    df = pd.DataFrame({"plein": ["a", "b"], "moitie": ["a", None], "vide": [None, None]})
    scores = completeness_by_column(df)
    assert list(scores.index) == ["vide", "moitie", "plein"]
    assert list(scores) == [0.0, 50.0, 100.0]


def test_global_score_is_share_of_filled_cells():
    df = pd.DataFrame({"a": ["x", None, "x", "x"], "b": ["y", "y", "", "y"]})
    assert completeness_score(df) == 75.0


def test_global_score_empty_table_is_100():
    assert completeness_score(pd.DataFrame()) == 100.0
    assert completeness_score(pd.DataFrame({"a": []})) == 100.0


@pytest.fixture(scope="module")
def demo() -> pd.DataFrame:
    return load_table("data/demo_clients.csv")


def test_demo_finds_the_400_injected_blank_emails(demo):
    scores = completeness_by_column(demo)
    assert scores["courriel"] == 92.0  # 400 / 5000 = 8 % missing
    assert (scores.drop("courriel") == 100.0).all()
    assert scores.index[0] == "courriel"


def test_demo_global_score(demo):
    # 400 missing cells out of 5000 x 14 = 70 000
    assert completeness_score(demo) == round((70_000 - 400) / 70_000 * 100, 1) == 99.4


# --- Uniqueness -----------------------------------------------------------------------------


def key_of(df: pd.DataFrame) -> str | None:
    return dim.detect_key_column(df, profile(df))


def test_key_prefers_key_like_name():
    df = pd.DataFrame({"nom": ["a", "b", "c"], "client_id": ["1", "2", "3"]})
    assert key_of(df) == "client_id"


def test_key_ignores_postal_codes_even_if_named_code():
    df = pd.DataFrame({"code_postal": ["H2X 1Y4", "G9A 5H7"], "x": ["a", "b"]})
    assert key_of(df) is None


def test_key_name_matching_uses_whole_words():
    # "valide" contains "id" but is not an identifier
    assert key_of(pd.DataFrame({"valide": ["oui", "non", "peut-être"]})) is None


def test_key_accepts_accented_names():
    assert key_of(pd.DataFrame({"Numéro": ["A1", "A2"]})) == "Numéro"


def test_key_ties_go_to_leftmost():
    df = pd.DataFrame({"client_id": ["1", "2"], "numero_commande": ["9", "8"]})
    assert key_of(df) == "client_id"


def test_key_needs_90_percent_distinct_values():
    df = pd.DataFrame({"categorie_id": ["A", "A", "B", "B"]})
    assert key_of(df) is None


def test_key_picks_the_most_distinct_candidate():
    df = pd.DataFrame({"code": [str(i % 9) for i in range(10)], "id": [str(i) for i in range(10)]})
    assert key_of(df) == "id"


def test_key_skips_empty_candidates():
    assert key_of(pd.DataFrame({"id": [None, None], "x": ["a", "b"]})) is None


def test_uniqueness_on_key_catches_conflicting_records():
    df = pd.DataFrame({"id": ["1", "1", "2", "3"], "nom": ["Roy", "Côté", "Morin", "Fortin"]})
    result = dim.uniqueness(df, "id")
    assert (result.score, result.duplicates_on_key, result.duplicate_rows) == (75.0, 1, 0)


def test_uniqueness_on_whole_rows_without_key():
    df = pd.DataFrame({"a": ["x", "x", "y"], "b": ["1", "1", "1"]})
    result = dim.uniqueness(df, None)
    assert (result.score, result.key, result.duplicates_on_key) == (66.7, None, 1)


def test_uniqueness_blank_keys_are_not_duplicates():
    df = pd.DataFrame({"id": ["1", None, None]})
    assert dim.uniqueness(df, "id").duplicates_on_key == 0


def test_uniqueness_empty_table():
    assert dim.uniqueness(pd.DataFrame({"a": []}), None).score == 100.0


def test_demo_uniqueness(demo):
    result = dim.uniqueness(demo, key_of(demo))
    assert (result.key, result.duplicates_on_key, result.score) == ("client_id", 150, 97.0)


# --- Validity -------------------------------------------------------------------------------


def validity_of(df: pd.DataFrame):
    return dim.validity(df, profile(df))


def test_validity_counts_bad_values_in_typed_columns():
    df = pd.DataFrame({"telephone": ["514-555-0101"] * 9 + ["155-555-0101"]})
    score, cols = validity_of(df)
    assert score == 90.0
    assert (cols["telephone"].checked, cols["telephone"].passed) == (10, 9)


def test_validity_rejects_impossible_dates():
    df = pd.DataFrame({"date": ["2026-02-28"] * 9 + ["2026-02-30"]})
    assert validity_of(df)[0] == 90.0


def test_validity_ignores_blanks_and_free_text():
    df = pd.DataFrame({"courriel": ["a@example.com", None, ""], "note": ["?", "!", "x"]})
    score, cols = validity_of(df)
    assert score == 100.0
    assert list(cols) == ["courriel"]
    assert cols["courriel"].checked == 1


def test_validity_not_applicable_without_typed_columns():
    assert validity_of(pd.DataFrame({"note": ["a", "b"]})) == (None, {})


def test_validity_weights_by_number_of_values():
    df = pd.DataFrame(
        {
            "courriel": ["a@example.com"] * 10,
            "telephone": ["514-555-0101"] * 8 + ["inconnu", "000-000-0000"],
        }
    )
    assert validity_of(df)[0] == 90.0  # 18 of 20


def test_demo_validity_finds_the_250_bad_phones(demo):
    score, cols = validity_of(demo)
    assert cols["telephone"].checked - cols["telephone"].passed == 250
    assert cols["telephone"].score == 95.0
    assert all(c.score == 100.0 for name, c in cols.items() if name != "telephone")
    assert score == 99.4


# --- Consistency ----------------------------------------------------------------------------


def consistency_of(df: pd.DataFrame):
    return dim.consistency(df, profile(df))


def test_consistency_flags_mixed_date_formats():
    df = pd.DataFrame({"date": ["2026-10-25"] * 3 + ["25/10/2026"]})
    score, cols = consistency_of(df)
    assert score == 75.0
    assert cols["date"].layouts == {"%Y-%m-%d": 3, "%d/%m/%Y": 1}


def test_consistency_flags_mixed_phone_layouts():
    df = pd.DataFrame({"tel": ["514-555-0101", "514-555-0102", "(514) 555-0103"]})
    assert consistency_of(df)[0] == 66.7


def test_consistency_flags_postal_codes_without_space():
    df = pd.DataFrame({"cp": ["H2X 1Y4", "H2X1Y4"]})
    assert consistency_of(df)[0] == 50.0


def test_consistency_flags_mixed_decimal_separators():
    df = pd.DataFrame({"montant": ["1.50", "2.75", "3,10", "12"]})
    score, cols = consistency_of(df)
    assert score == 66.7  # the integer has no decimal mark to compare
    assert cols["montant"].layouts == {"décimale « . »": 2, "décimale « , »": 1}


def test_consistency_ignores_invalid_values_and_text():
    df = pd.DataFrame({"tel": ["514-555-0101"] * 9 + ["inconnu"], "note": ["a"] * 10})
    score, cols = consistency_of(df)
    assert (score, list(cols)) == (100.0, ["tel"])


def test_consistency_not_applicable_without_layouts():
    assert consistency_of(pd.DataFrame({"note": ["a"], "n": ["12"]})) == (None, {})


def test_demo_consistency_finds_the_1500_day_first_dates(demo):
    score, cols = consistency_of(demo)
    assert cols["date_inscription"].layouts == {"%Y-%m-%d": 3500, "%d/%m/%Y": 1500}
    assert cols["date_inscription"].count.score == 70.0
    assert score == 95.0


# --- Freshness ------------------------------------------------------------------------------

TODAY = date(2026, 10, 25)


def freshness_of(df: pd.DataFrame, today: date = TODAY):
    return dim.freshness(df, profile(df), today)


@pytest.mark.parametrize(
    ("latest", "expected"),
    [("2026-10-25", 100.0), ("2026-09-25", 100.0), ("2025-10-25", 0.0), ("2020-01-01", 0.0)],
)
def test_freshness_scale(latest, expected):
    assert freshness_of(pd.DataFrame({"date": ["2020-01-01", latest]})).score == expected


def test_freshness_falls_linearly_between_30_and_365_days():
    # 197.5 days old is halfway between 30 and 365
    result = freshness_of(pd.DataFrame({"d": ["2026-04-10"]}))
    assert result.age_days == 198
    assert result.score == 49.9


def test_freshness_uses_the_newest_date_column():
    df = pd.DataFrame({"naissance": ["1990-01-01"], "maj": ["25/10/2026"]})
    result = freshness_of(df)
    assert (result.column, result.latest, result.age_days) == ("maj", TODAY, 0)


def test_freshness_ignores_future_dates():
    df = pd.DataFrame({"date": ["2026-10-01", "2099-01-01"]})
    assert freshness_of(df).latest == date(2026, 10, 1)


def test_freshness_not_applicable_without_dates():
    assert freshness_of(pd.DataFrame({"note": ["a"]})) is None
    assert freshness_of(pd.DataFrame({"date": ["2099-01-01"]})) is None


def test_demo_freshness_on_reference_date(demo):
    result = freshness_of(demo, date(2026, 10, 20))
    assert (result.column, result.age_days, result.score) == ("derniere_commande", 0, 100.0)

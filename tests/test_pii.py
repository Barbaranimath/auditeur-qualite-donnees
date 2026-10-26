import json
from datetime import date

import pandas as pd
import pytest

from dq.audit import audit
from dq.io import load_table
from dq.pii import CATEGORIES, mask, scan
from dq.profiling import profile


def findings(df: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """column -> (category, detected_by)"""
    return {f.column: (f.category, f.detected_by) for f in scan(df, profile(df))}


@pytest.fixture(scope="module")
def demo() -> pd.DataFrame:
    return load_table("data/demo_clients.csv")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(open("data/demo_manifest.json", encoding="utf-8").read())


# --- Success criterion: at least 90 % of the demo's personal columns are flagged -----------


def test_demo_flags_every_personal_column(demo, manifest):
    flagged = set(findings(demo))
    expected = set(manifest["pii_columns"])
    assert len(flagged & expected) / len(expected) >= 0.9
    assert flagged == expected  # in fact all 8


def test_demo_flags_nothing_that_is_not_personal(demo, manifest):
    assert not set(findings(demo)) & set(manifest["not_pii_columns"])


def test_demo_categories_and_risk_order(demo):
    result = scan(demo, profile(demo))
    assert [(f.column, f.category) for f in result][:1] == [("nas", "nas")]
    assert [f.risk for f in result] == sorted(
        (f.risk for f in result), key=["Élevé", "Moyen", "Faible"].index
    )
    assert {f.column: f.category for f in result}["prenom"] == "nom"


# --- Detection by values, without a helpful column name ----------------------------------


@pytest.mark.parametrize(
    ("values", "category"),
    [
        (["a@example.com", "b@example.org"], "courriel"),
        (["514-555-0101", "(819) 555-0199"], "telephone"),
        (["H2X 1Y4", "G9A 5H7"], "code_postal"),
        (["046 454 286", "123-456-789"], "nas"),
        (["12 rue des Forges", "4500, boul. Saint-Laurent", "9 avenue du Parc"], "adresse"),
    ],
)
def test_detects_by_value_format_under_a_neutral_name(values, category):
    assert findings(pd.DataFrame({"colonne_7": values})) == {"colonne_7": (category, "format")}


# --- Detection by name ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("Prénom", "nom"),
        ("last_name", "nom"),
        ("Date de naissance", "date_naissance"),
        ("DOB", "date_naissance"),
        ("no_assurance_sociale", "nas"),
        ("email", "courriel"),
        ("tel_maison", "telephone"),
    ],
)
def test_detects_by_name(name, category):
    assert findings(pd.DataFrame({name: ["x", "y"]}))[name][0] == category


@pytest.mark.parametrize(
    "name",
    ["nom_produit", "nom_entreprise", "ville", "numero_commande", "client_id", "nombre_articles"],
)
def test_business_columns_are_not_personal(name):
    assert findings(pd.DataFrame({name: ["A1", "B2"]})) == {}


def test_order_numbers_that_look_like_phones_are_not_flagged():
    assert findings(pd.DataFrame({"numero_commande": ["5145550101", "4185550123"]})) == {}


def test_birth_name_on_a_numeric_column_is_not_a_birth_date():
    assert findings(pd.DataFrame({"annee_naissance_nb": ["12", "15"]})) == {}


def test_empty_column_is_skipped():
    assert findings(pd.DataFrame({"courriel": [None, None]})) == {}


def test_every_category_has_risk_and_recommendation():
    for category in CATEGORIES.values():
        assert category.risk in {"Élevé", "Moyen", "Faible"}
        assert category.recommendation


# --- Masking: no raw personal value is ever shown --------------------------------------


@pytest.mark.parametrize(
    ("category", "value", "masked"),
    [
        ("courriel", "therese.dossou409@example.com", "t•••@example.com"),
        ("telephone", "514-555-0188", "•••-•••-••••"),
        ("nas", "810 728 905", "•••"),
        ("date_naissance", "1957-01-17", "1957 (jour et mois masqués)"),
        ("date_naissance", "inconnue", "•••"),
        ("code_postal", "h7k 9w7", "H7K •••"),
        ("adresse", "1014 rue Principale", "••• rue Principale"),
        ("adresse", "inconnue", "•••"),
        ("nom", "Dossou", "D•••"),
        ("courriel", "pas-un-courriel", "•••"),
    ],
)
def test_mask(category, value, masked):
    assert mask(category, value) == masked


def test_demo_examples_never_contain_raw_values(demo):
    for finding in scan(demo, profile(demo)):
        shown = finding.example
        for raw in demo[finding.column].dropna().astype(str):
            if finding.category in ("code_postal", "nom"):
                assert shown != raw
            else:
                assert raw not in shown
    nas = next(f for f in scan(demo, profile(demo)) if f.category == "nas")
    assert not any(ch.isdigit() for ch in nas.example)


def test_audit_includes_personal_data_without_changing_the_score(demo):
    result = audit(demo, today=date(2026, 10, 20))
    assert len(result.personal_data) == 8
    assert result.overall == 98.2


def test_reports_how_each_column_was_detected(demo):
    found = findings(demo)
    assert found["courriel"] == ("courriel", "nom et format")
    assert found["code_postal"] == ("code_postal", "format")
    assert found["prenom"] == ("nom", "nom")

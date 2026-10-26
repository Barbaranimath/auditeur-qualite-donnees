import pandas as pd
import pytest

from dq.profiling import detect_type, filled_values, profile


def s(*values) -> pd.Series:
    return pd.Series(values, dtype="object")


@pytest.mark.parametrize(
    ("name", "values", "expected"),
    [
        ("courriel", s("a@example.com", "b.c@example.org"), "courriel"),
        ("cp", s("H2X 1Y4", "g9a5h7", "J1H 2B3"), "code_postal"),
        ("telephone", s("514-555-0101", "(819) 555-0199", "+1 418 555 0123"), "telephone"),
        ("date", s("2026-10-25", "25/10/2026", "2026/01/31"), "date"),
        ("montant", s("12.50", "1 234,56", "-3", "1000"), "nombre"),
        ("commentaire", s("Très bien", "À revoir", "ça va"), "texte"),
    ],
)
def test_detects_each_type(name, values, expected):
    assert detect_type(name, values)[0] == expected


def test_bare_ten_digits_is_a_number_not_a_phone():
    order_numbers = s("5145550101", "4185550123", "8195550199")
    assert detect_type("numero_commande", order_numbers)[0] == "nombre"


def test_bare_ten_digits_is_a_phone_when_the_name_says_so():
    assert detect_type("tel_cellulaire", s("5145550101", "4185550123"))[0] == "telephone"


def test_sin_layout_is_not_read_as_a_number():
    assert detect_type("nas", s("123 456 789", "987 654 321"))[0] == "texte"


def test_threshold_tolerates_a_few_bad_values():
    values = s(*["514-555-0101"] * 9, "inconnu")
    dtype, rate = detect_type("telephone", values)
    assert (dtype, rate) == ("telephone", 0.9)


def test_below_threshold_falls_back_to_text():
    values = s(*["a@example.com"] * 7, "x", "y", "z")
    assert detect_type("contact", values)[0] == "texte"


def test_empty_and_all_null_columns_are_text():
    assert detect_type("vide", s()) == ("texte", 1.0)
    assert detect_type("nulle", s(None, None, "  ")) == ("texte", 1.0)


def test_filled_values_drops_nulls_and_blanks():
    assert list(filled_values(s(" a ", None, "", "   ", "b"))) == ["a", "b"]


def test_single_row():
    assert detect_type("courriel", s("solo@example.net"))[0] == "courriel"


def test_profile_reports_every_column():
    df = pd.DataFrame({"courriel": ["a@example.com", None], "ville": ["Montréal", "Québec"]})
    result = profile(df)
    assert result["courriel"].dtype == "courriel"
    assert result["courriel"].filled == 1
    assert result["ville"].dtype == "texte"


def test_demo_dataset_types():
    from dq.io import load_table

    types = {c: p.dtype for c, p in profile(load_table("data/demo_clients.csv")).items()}
    assert types == {
        "client_id": "texte",
        "prenom": "texte",
        "nom": "texte",
        "courriel": "courriel",
        "telephone": "telephone",
        "adresse": "texte",
        "ville": "texte",
        "code_postal": "code_postal",
        "date_naissance": "date",
        "nas": "texte",
        "date_inscription": "date",
        "derniere_commande": "date",
        "numero_commande": "nombre",
        "montant_total": "nombre",
    }

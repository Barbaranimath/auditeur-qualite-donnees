from datetime import date

import pandas as pd

from dq.audit import audit
from dq.fmt import fr_int, fr_pct, layout_label, plural
from dq.io import load_table
from dq.issues import list_issues


def test_french_formats():
    assert fr_int(200000) == "200 000"
    assert fr_pct(99.44) == "99,4 %"
    assert layout_label("%d/%m/%Y") == "JJ/MM/AAAA"
    assert layout_label("A9A 9A9") == "A9A 9A9"
    assert plural(1, "valeur", "valeurs") == "1 valeur"
    assert plural(0, "valeur", "valeurs") == "0 valeur"
    assert plural(1500, "valeur", "valeurs") == "1 500 valeurs"


def test_demo_issues_ranked_by_records_affected():
    result = audit(load_table("data/demo_clients.csv"), today=date(2026, 10, 20))
    issues = list_issues(result)
    assert [(i.dimension, i.column, i.count) for i in issues] == [
        ("Cohérence", "date_inscription", 1500),
        ("Complétude", "courriel", 400),
        ("Validité", "telephone", 250),
        ("Unicité", "client_id", 150),
    ]
    assert issues[0].message == (
        "2 formats différents : 1 500 valeurs en JJ/MM/AAAA au lieu de AAAA-MM-JJ."
    )
    assert issues[3].message == (
        "150 enregistrements en double sur la clé « client_id » dont 150 lignes identiques."
    )
    assert all(i.advice for i in issues)


def test_clean_table_has_no_issues():
    df = pd.DataFrame({"id": ["1", "2"], "maj": ["2026-10-20", "2026-10-21"]})
    assert list_issues(audit(df, today=date(2026, 10, 25))) == []


def test_whole_row_duplicates_and_stale_data():
    df = pd.DataFrame({"note": ["a", "a"], "maj": ["2025-01-01", "2025-01-01"]})
    issues = {i.dimension: i for i in list_issues(audit(df, today=date(2026, 10, 25)))}
    assert issues["Unicité"].message == "1 enregistrement en double sur des lignes entières."
    assert issues["Fraîcheur"].message == (
        "La donnée la plus récente date du 01/01/2025, il y a 662 jours."
    )


def test_key_duplicates_that_are_not_identical_rows():
    # 9 distinct ids out of 10 rows: enough to be recognised as the key (90 %)
    df = pd.DataFrame({"id": ["1", *map(str, range(1, 10))], "nom": ["Roy", *["Côté"] * 9]})
    issue = list_issues(audit(df, today=date(2026, 10, 25)))[0]
    assert issue.message == "1 enregistrement en double sur la clé « id »."

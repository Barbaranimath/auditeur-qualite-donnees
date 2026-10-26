import json
from pathlib import Path

import pandas as pd
import pytest

from dq import patterns
from dq.io import load_table
from scripts.generate_demo_data import generate

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def demo() -> pd.DataFrame:
    return load_table(DATA / "demo_clients.csv")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads((DATA / "demo_manifest.json").read_text(encoding="utf-8"))


def test_row_count(demo, manifest):
    assert len(demo) == manifest["rows"] == 5000


def test_exact_duplicate_rows(demo, manifest):
    assert demo.duplicated().sum() == manifest["duplicate_rows"] == 150


def test_blank_emails(demo, manifest):
    assert demo["courriel"].isna().sum() == manifest["blank_emails"] == 400


def test_invalid_phones(demo, manifest):
    valid = demo["telephone"].map(lambda v: bool(patterns.PHONE_NANP.match(v)))
    assert (~valid).sum() == manifest["invalid_phones"] == 250


def test_two_signup_date_formats(demo, manifest):
    formats = demo["date_inscription"].map(patterns.date_format_of).value_counts()
    assert formats["%d/%m/%Y"] == manifest["dmy_signup_dates"] == 1500
    assert formats["%Y-%m-%d"] == 3500


def test_key_column_unique_except_duplicates(demo):
    assert demo["client_id"].duplicated().sum() == 150


def test_only_fictional_contact_data(demo):
    domains = demo["courriel"].dropna().str.split("@").str[1]
    assert set(domains) <= {"example.com", "example.org", "example.net"}
    valid = demo["telephone"][demo["telephone"].map(lambda v: bool(patterns.PHONE_NANP.match(v)))]
    assert valid.str.match(r"^\d{3}-555-01\d{2}$").all()  # fictional 555-01XX range only


def test_committed_file_matches_generator(demo):
    df, _ = generate(rows=5000, seed=42)
    regenerated = df.replace("", pd.NA)
    pd.testing.assert_frame_equal(demo, regenerated, check_dtype=False)


def test_generator_is_deterministic():
    a, _ = generate(rows=200, seed=7)
    b, _ = generate(rows=200, seed=7)
    pd.testing.assert_frame_equal(a, b)

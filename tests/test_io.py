import io

import pandas as pd
import pytest

from dq import io as dq_io
from dq.io import TooManyRowsError, load_table


def upload(content: bytes, name: str = "fichier.csv") -> io.BytesIO:
    buffer = io.BytesIO(content)
    buffer.name = name
    return buffer


def test_utf8_accents():
    df = load_table(upload("ville\nMontréal\nTrois-Rivières\n".encode()))
    assert list(df["ville"]) == ["Montréal", "Trois-Rivières"]


def test_utf8_with_bom_from_excel():
    df = load_table(upload("﻿nom\nCôté\n".encode()))
    assert list(df.columns) == ["nom"]


def test_latin1_file_from_quebec_excel():
    df = load_table(upload("ville;prénom\nQuébec;Françoise\n".encode("cp1252")))
    assert df.loc[0, "ville"] == "Québec"
    assert df.loc[0, "prénom"] == "Françoise"


def test_semicolon_delimiter():
    df = load_table(upload(b"a;b\n1;2\n"))
    assert df.to_dict("list") == {"a": ["1"], "b": ["2"]}


def test_single_column_is_not_split():
    df = load_table(upload(b"nom\nAnna\nBoris\n"))
    assert df.to_dict("list") == {"nom": ["Anna", "Boris"]}


def test_quoted_commas_survive():
    df = load_table(upload(b'adresse,ville\n"12, rue X",Laval\n'))
    assert df.loc[0, "adresse"] == "12, rue X"


def test_values_stay_text():
    df = load_table(upload(b"code,montant\n00123,1.50\n"))
    assert df.loc[0, "code"] == "00123"  # leading zeros kept


def test_excel_file(tmp_path):
    path = tmp_path / "clients.xlsx"
    pd.DataFrame({"code": ["007"], "ville": ["Gatineau"]}).to_excel(path, index=False)
    df = load_table(path)
    assert df.to_dict("list") == {"code": ["007"], "ville": ["Gatineau"]}


def test_column_names_are_trimmed():
    assert list(load_table(upload(b" nom , ville \nA,B\n")).columns) == ["nom", "ville"]


def test_row_limit(monkeypatch):
    monkeypatch.setattr(dq_io, "MAX_ROWS", 2)
    with pytest.raises(TooManyRowsError):
        load_table(upload(b"x\n1\n2\n3\n"))


def test_delimiter_defaults_to_comma_when_undetectable():
    assert dq_io._sniff_delimiter("nom\nAnna\nBoris") == ","

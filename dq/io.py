"""Load uploaded CSV or Excel files into a DataFrame of strings."""

import csv
import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

MAX_ROWS = 200_000
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # Excel in Québec often saves as cp1252.
DELIMITERS = ",;\t|"


class TooManyRowsError(ValueError):
    """Raised when a file exceeds the row limit set in the spec."""


def load_table(source: str | Path | BinaryIO, filename: str | None = None) -> pd.DataFrame:
    """Read a CSV or XLSX file with every cell kept as text, so nothing is silently converted."""
    name = (filename or str(getattr(source, "name", source))).lower()
    raw = Path(source).read_bytes() if isinstance(source, (str, Path)) else source.read()

    if name.endswith((".xlsx", ".xlsm")):
        df = pd.read_excel(io.BytesIO(raw), dtype=str)
    else:
        df = _read_csv_any_encoding(raw)

    if len(df) > MAX_ROWS:
        raise TooManyRowsError(f"Le fichier contient {len(df)} lignes (maximum {MAX_ROWS}).")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _read_csv_any_encoding(raw: bytes) -> pd.DataFrame:
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        return pd.read_csv(io.StringIO(text), dtype=str, sep=_sniff_delimiter(text))
    raise ValueError("Encodage du fichier non reconnu.")  # pragma: no cover (latin-1 decodes all)


def _sniff_delimiter(text: str) -> str:
    """Pick the delimiter among the usual ones (French Excel exports use ";"), default ","."""
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters=DELIMITERS).delimiter
    except csv.Error:
        return ","

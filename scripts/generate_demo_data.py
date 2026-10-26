"""Generate a fully fictional customer dataset with known, injected quality problems.

Every person, email, phone and SIN is invented: emails use reserved example.* domains,
phones use the fictional 555-01XX range. A manifest records exactly which errors were
injected so tests can check that the auditor finds them.
"""

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

REFERENCE_DATE = date(2026, 10, 20)  # Fixed so the dataset is reproducible.

DUPLICATE_RATE = 0.03
BLANK_EMAIL_RATE = 0.08
INVALID_PHONE_RATE = 0.05
DMY_DATE_RATE = 0.30  # Share of signup dates written as DD/MM/YYYY instead of ISO.

FIRST_NAMES = [
    "Amélie",
    "Benoît",
    "Chloé",
    "Denis",
    "Élodie",
    "François",
    "Geneviève",
    "Hugo",
    "Inès",
    "Jérôme",
    "Karine",
    "Léa",
    "Mathieu",
    "Noémie",
    "Olivier",
    "Patrice",
    "Pascale",
    "Rachel",
    "Sébastien",
    "Thérèse",
    "Ulrich",
    "Valérie",
    "William",
    "Yasmine",
    "Zoé",
    "Aïcha",
    "Koffi",
    "Mariam",
    "Moussa",
    "Nadège",
]
LAST_NAMES = [
    "Tremblay",
    "Gagnon",
    "Roy",
    "Côté",
    "Bouchard",
    "Gauthier",
    "Morin",
    "Lavoie",
    "Fortin",
    "Gagné",
    "Ouellet",
    "Pelletier",
    "Bélanger",
    "Lévesque",
    "Bergeron",
    "Leblanc",
    "Paquette",
    "Girard",
    "Simard",
    "Boucher",
    "Adjovi",
    "Dossou",
    "Houngbo",
]
# City -> (postal code first letter, area codes)
CITIES = {
    "Montréal": ("H", ["514", "438"]),
    "Laval": ("H", ["450", "579"]),
    "Québec": ("G", ["418", "581"]),
    "Trois-Rivières": ("G", ["819", "873"]),
    "Sherbrooke": ("J", ["819", "873"]),
    "Gatineau": ("J", ["819", "873"]),
}
STREETS = [
    "rue Sainte-Catherine",
    "boulevard Saint-Laurent",
    "rue des Forges",
    "avenue du Parc",
    "rue King Ouest",
    "chemin de la Côte",
    "rue Principale",
]
DOMAINS = ["example.com", "example.org", "example.net"]
POSTAL_LETTERS = "ABCEGHJKLMNPRSTVWXYZ"


def _postal_code(rng: random.Random, first: str) -> str:
    d = lambda: str(rng.randint(0, 9))  # noqa: E731
    letter = lambda: rng.choice(POSTAL_LETTERS)  # noqa: E731
    return f"{first}{d()}{letter()} {d()}{letter()}{d()}"


def _random_date(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _strip_accents(text: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüçÀÂÉÈÊÎÔÙÛÇ", "aaaeeeeiioouuucAAEEEIOUUC")
    return text.translate(table)


def _clean_row(rng: random.Random, index: int) -> dict[str, str]:
    first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    city = rng.choice(list(CITIES))
    postal_letter, area_codes = CITIES[city]
    signup = _random_date(rng, date(2019, 1, 1), REFERENCE_DATE - timedelta(days=30))
    last_order = _random_date(rng, signup, REFERENCE_DATE)
    return {
        "client_id": f"CL-{index:05d}",
        "prenom": first,
        "nom": last,
        "courriel": f"{_strip_accents(first).lower()}.{_strip_accents(last).lower()}"
        f"{rng.randint(1, 999)}@{rng.choice(DOMAINS)}",
        "telephone": f"{rng.choice(area_codes)}-555-01{rng.randint(0, 99):02d}",
        "adresse": f"{rng.randint(1, 9999)} {rng.choice(STREETS)}",
        "ville": city,
        "code_postal": _postal_code(rng, postal_letter),
        "date_naissance": _random_date(rng, date(1950, 1, 1), date(2005, 12, 31)).isoformat(),
        "nas": f"{rng.randint(100, 999)} {rng.randint(100, 999)} {rng.randint(100, 999)}",
        "date_inscription": signup.isoformat(),
        "derniere_commande": last_order.isoformat(),
        # Ten bare digits on purpose: looks like a phone, must NOT be flagged as one.
        "numero_commande": str(rng.randint(2_000_000_000, 9_999_999_999)),
        "montant_total": f"{rng.uniform(10, 5000):.2f}",
    }


def _invalid_phone(rng: random.Random) -> str:
    return rng.choice(
        [
            f"155-555-01{rng.randint(0, 99):02d}",  # area code cannot start with 1
            f"514-555-{rng.randint(0, 99):02d}",  # too short
            "000-000-0000",
            "inconnu",
        ]
    )


def generate(rows: int = 5000, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    """Build the demo dataset and a manifest of every injected error."""
    rng = random.Random(seed)
    n_dup = round(rows * DUPLICATE_RATE)
    n_base = rows - n_dup
    base = [_clean_row(rng, i + 1) for i in range(n_base)]

    # Duplicate sources stay clean, so each copy is an exact duplicate row.
    indices = list(range(n_base))
    rng.shuffle(indices)
    dup_sources, others = indices[:n_dup], indices[n_dup:]

    blank_email = rng.sample(others, round(rows * BLANK_EMAIL_RATE))
    bad_phone = rng.sample(others, round(rows * INVALID_PHONE_RATE))
    dmy_dates = rng.sample(others, round(rows * DMY_DATE_RATE))

    for i in blank_email:
        base[i]["courriel"] = ""
    for i in bad_phone:
        base[i]["telephone"] = _invalid_phone(rng)
    for i in dmy_dates:
        base[i]["date_inscription"] = date.fromisoformat(base[i]["date_inscription"]).strftime(
            "%d/%m/%Y"
        )

    records = base + [dict(base[i]) for i in dup_sources]
    rng.shuffle(records)
    df = pd.DataFrame(records)

    manifest = {
        "seed": seed,
        "rows": rows,
        "reference_date": REFERENCE_DATE.isoformat(),
        "duplicate_rows": n_dup,
        "blank_emails": len(blank_email),
        "invalid_phones": len(bad_phone),
        "dmy_signup_dates": len(dmy_dates),
        "key_column": "client_id",
        "pii_columns": [
            "prenom",
            "nom",
            "courriel",
            "telephone",
            "adresse",
            "code_postal",
            "date_naissance",
            "nas",
        ],
        "not_pii_columns": [
            "client_id",
            "ville",
            "date_inscription",
            "derniere_commande",
            "numero_commande",
            "montant_total",
        ],
    }
    return df, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("data"))
    args = parser.parse_args()

    df, manifest = generate(args.rows, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "demo_clients.csv", index=False, encoding="utf-8")
    (args.out / "demo_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(df)} lignes écrites dans {args.out / 'demo_clients.csv'}")


if __name__ == "__main__":
    main()

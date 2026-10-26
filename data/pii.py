"""Find columns that probably hold personal information (Québec Law 25) and mask their values.

A column is flagged from its name, from the format of its values, or both. Masked examples
are the only values ever shown to users: no raw personal value leaves this module.
"""

import re
from dataclasses import dataclass

import pandas as pd

from dq import patterns
from dq.profiling import MATCH_THRESHOLD, ColumnProfile, filled_values, name_tokens

STREET_WORDS = r"rue|avenue|av|boulevard|boul|bd|chemin|ch|route|rang|place|street|st|road|rd"
STREET_ADDRESS = re.compile(rf"^\d+[a-z]?,? +({STREET_WORDS})\b", re.IGNORECASE)

RISK_ORDER = {"Élevé": 0, "Moyen": 1, "Faible": 2}


@dataclass(frozen=True)
class Category:
    label: str
    risk: str
    name_tokens: frozenset[str]
    recommendation: str


CATEGORIES = {
    "nas": Category(
        "Numéro d'assurance sociale",
        "Élevé",
        frozenset({"nas", "sin", "ssn"}),
        "Supprimer si ce n'est pas indispensable ; sinon chiffrer et limiter l'accès.",
    ),
    "date_naissance": Category(
        "Date de naissance",
        "Moyen",
        frozenset({"naissance", "birth", "birthdate", "dob", "ddn"}),
        "Remplacer par l'âge ou l'année si la date exacte n'est pas requise.",
    ),
    "courriel": Category(
        "Courriel",
        "Moyen",
        frozenset({"courriel", "email", "mail"}),
        "Masquer ou pseudonymiser hors des usages qui l'exigent.",
    ),
    "telephone": Category(
        "Téléphone",
        "Moyen",
        frozenset({"telephone", "tel", "phone", "cell", "cellulaire", "mobile"}),
        "Masquer ou pseudonymiser hors des usages qui l'exigent.",
    ),
    "adresse": Category(
        "Adresse",
        "Moyen",
        frozenset({"adresse", "address", "rue", "street"}),
        "Masquer hors des usages qui l'exigent ; garder la ville pour l'analyse.",
    ),
    "code_postal": Category(
        "Code postal",
        "Faible",
        frozenset(),  # detected from values only: "code" alone is too common in names
        "Garder seulement les 3 premiers caractères pour l'analyse.",
    ),
    "nom": Category(
        "Nom ou prénom",
        "Faible",
        frozenset({"nom", "prenom", "name", "firstname", "lastname", "surname"}),
        "Pseudonymiser (remplacer par un identifiant) pour l'analyse.",
    ),
}

# A token that marks the name as something else, e.g. "nom_produit", "numero_commande".
NOT_PERSONAL_TOKENS = {"produit", "entreprise", "compagnie", "ville", "fichier", "commande", "id"}


@dataclass(frozen=True)
class PiiFinding:
    column: str
    category: str  # key of CATEGORIES
    detected_by: str  # "nom", "format" or "nom et format"
    example: str  # always masked

    @property
    def label(self) -> str:
        return CATEGORIES[self.category].label

    @property
    def risk(self) -> str:
        return CATEGORIES[self.category].risk

    @property
    def recommendation(self) -> str:
        return CATEGORIES[self.category].recommendation


def _share(values: pd.Series, regex: re.Pattern[str]) -> float:
    return float(values.map(lambda v: bool(regex.search(v))).mean()) if len(values) else 0.0


def _category_from_values(profile: ColumnProfile, values: pd.Series) -> str | None:
    if profile.dtype in ("courriel", "telephone", "code_postal"):
        return profile.dtype
    if _share(values, patterns.SIN_LAYOUT) >= MATCH_THRESHOLD:
        return "nas"
    if _share(values, STREET_ADDRESS) >= MATCH_THRESHOLD:
        return "adresse"
    return None


def _category_from_name(name: str, dtype: str) -> str | None:
    tokens = name_tokens(name)
    if tokens & NOT_PERSONAL_TOKENS:
        return None
    if {"assurance", "sociale"} <= tokens:
        return "nas"
    is_birth = "naissance" in tokens or tokens & CATEGORIES["date_naissance"].name_tokens
    if is_birth:
        return "date_naissance" if dtype in ("date", "texte") else None
    for key, category in CATEGORIES.items():
        if tokens & category.name_tokens:
            return key
    return None


def scan(df: pd.DataFrame, profiles: dict[str, ColumnProfile]) -> list[PiiFinding]:
    """Return the columns that probably hold personal information, riskiest first."""
    findings = []
    for col in df.columns:
        values = filled_values(df[col])
        if values.empty:
            continue
        by_values = _category_from_values(profiles[col], values)
        by_name = _category_from_name(col, profiles[col].dtype)
        category = by_values or by_name
        if category is None:
            continue
        if by_values and by_name == by_values:
            detected_by = "nom et format"
        elif by_values:
            detected_by = "format"
        else:
            detected_by = "nom"
        findings.append(PiiFinding(col, category, detected_by, mask(category, values.iloc[0])))
    return sorted(findings, key=lambda f: RISK_ORDER[f.risk])


def mask(category: str, value: str) -> str:
    """Hide a personal value, keeping only what helps recognise the kind of data."""
    value = str(value).strip()
    if category == "courriel" and "@" in value:
        local, domain = value.split("@", 1)
        return f"{local[:1]}•••@{domain}"
    if category == "telephone":
        return re.sub(r"\d", "•", value)
    if category == "date_naissance":
        year = re.search(r"\d{4}", value)
        return f"{year.group()} (jour et mois masqués)" if year else "•••"
    if category == "code_postal":
        return f"{value[:3].upper()} •••"
    if category == "adresse":
        street = STREET_ADDRESS.match(value)
        return f"••• {value[street.start(1) :]}" if street else "•••"
    if category == "nom":
        return f"{value[:1]}•••"
    return "•••"  # nas and anything else: nothing shown

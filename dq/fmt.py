"""French (Québec) number formatting for everything shown to users."""

NBSP = "\N{NO-BREAK SPACE}"

DATE_FORMAT_LABELS = {"%Y-%m-%d": "AAAA-MM-JJ", "%d/%m/%Y": "JJ/MM/AAAA", "%Y/%m/%d": "AAAA/MM/JJ"}


def fr_int(value: int) -> str:
    """Format an integer with a space between thousands: 5 000."""
    return f"{value:,}".replace(",", NBSP)


def fr_pct(value: float) -> str:
    """Format a 0-100 score with a decimal comma: 99,4 %."""
    return f"{value:.1f}".replace(".", ",") + f"{NBSP}%"


def layout_label(layout: str) -> str:
    """Turn an internal layout key into something readable."""
    return DATE_FORMAT_LABELS.get(layout, layout)


def plural(count: int, singular: str, plural_form: str) -> str:
    """Return '1 valeur' or '3 valeurs' (French: 0 and 1 are singular)."""
    return f"{fr_int(count)} {singular if count <= 1 else plural_form}"

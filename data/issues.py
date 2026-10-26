"""Turn audit numbers into a ranked list of concrete problems to fix."""

from dataclasses import dataclass

from dq.audit import AuditResult
from dq.fmt import fr_pct, layout_label, plural


@dataclass(frozen=True)
class Issue:
    dimension: str
    column: str | None
    count: int  # records affected, used to rank issues
    message: str
    advice: str


def list_issues(result: AuditResult) -> list[Issue]:
    """Return every problem found, the one touching the most records first."""
    issues: list[Issue] = []
    n = result.rows

    for col, score in result.completeness_by_column.items():
        missing = n - result.profiles[col].filled
        if missing:
            issues.append(
                Issue(
                    "Complétude",
                    col,
                    missing,
                    f"{plural(missing, 'valeur manquante', 'valeurs manquantes')} "
                    f"({fr_pct(100 - score)} de la colonne).",
                    "Rendre le champ obligatoire à la saisie ou compléter depuis la source.",
                )
            )

    dup = result.uniqueness
    if dup.duplicates_on_key:
        on = f"la clé « {dup.key} »" if dup.key else "des lignes entières"
        identical = (
            f" dont {plural(dup.duplicate_rows, 'ligne identique', 'lignes identiques')}"
            if dup.key and dup.duplicate_rows
            else ""
        )
        issues.append(
            Issue(
                "Unicité",
                dup.key,
                dup.duplicates_on_key,
                f"{plural(dup.duplicates_on_key, 'enregistrement', 'enregistrements')} en double"
                f" sur {on}{identical}.",
                "Fusionner les doublons, puis imposer l'unicité dans le système source.",
            )
        )

    for col, count in result.validity_by_column.items():
        bad = count.checked - count.passed
        if bad:
            issues.append(
                Issue(
                    "Validité",
                    col,
                    bad,
                    f"{plural(bad, 'valeur mal formée', 'valeurs mal formées')} "
                    f"({fr_pct(100 - count.score)} des valeurs remplies).",
                    "Ajouter une validation de format au formulaire de saisie.",
                )
            )

    for col, detail in result.consistency_by_column.items():
        off = detail.count.checked - detail.count.passed
        if off:
            main, *others = detail.layouts
            others_text = ", ".join(layout_label(o) for o in others)
            issues.append(
                Issue(
                    "Cohérence",
                    col,
                    off,
                    f"{plural(len(detail.layouts), 'format', 'formats')} différents : "
                    f"{plural(off, 'valeur', 'valeurs')} en {others_text} au lieu de "
                    f"{layout_label(main)}.",
                    f"Uniformiser au format {layout_label(main)}.",
                )
            )

    fresh = result.freshness
    if fresh and fresh.score < 100:
        issues.append(
            Issue(
                "Fraîcheur",
                fresh.column,
                0,
                f"La donnée la plus récente date du {fresh.latest:%d/%m/%Y}, "
                f"il y a {plural(fresh.age_days, 'jour', 'jours')}.",
                "Vérifier que l'extraction ou la synchronisation est toujours active.",
            )
        )

    return sorted(issues, key=lambda i: -i.count)

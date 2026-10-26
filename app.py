"""Streamlit interface. Display only: every calculation lives in dq/."""

import io
import json
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dq.audit import DIMENSION_NAMES, AuditResult, audit
from dq.fmt import fr_int, fr_pct, layout_label, plural
from dq.io import MAX_ROWS, TooManyRowsError, load_table
from dq.issues import list_issues

DATA_DIR = Path(__file__).parent / "data"
BAR_COLOR = "#2a78d6"
MUTED_INK = "#898781"

TYPE_LABELS = {
    "courriel": "Courriel",
    "code_postal": "Code postal",
    "telephone": "Téléphone",
    "date": "Date",
    "nombre": "Nombre",
    "texte": "Texte",
}

RULES = {
    "Complétude": "Part des cellules remplies (ni vides, ni composées d'espaces).",
    "Unicité": (
        "Part des enregistrements non répétés. L'outil choisit seul la colonne clé : un nom "
        "comme « id », « code » ou « numéro », avec au moins 90 % de valeurs distinctes. "
        "Sans clé, il compare les lignes entières."
    ),
    "Validité": (
        "Part des valeurs remplies qui respectent le format de leur colonne : courriel, "
        "téléphone nord-américain, code postal canadien, date réelle, nombre. "
        "Les colonnes de texte libre ne sont pas vérifiées."
    ),
    "Cohérence": (
        "Part des valeurs valides écrites dans le format le plus courant de leur colonne "
        "(ex. toutes les dates en AAAA-MM-JJ)."
    ),
    "Fraîcheur": (
        "Âge de la date la plus récente du fichier : 100 jusqu'à 30 jours, puis baisse "
        "régulière jusqu'à 0 à un an."
    ),
}

st.set_page_config(page_title="Auditeur de qualité des données", page_icon="🔎", layout="wide")


@st.cache_data(show_spinner=False)
def load_demo() -> tuple[pd.DataFrame, date]:
    manifest = json.loads((DATA_DIR / "demo_manifest.json").read_text(encoding="utf-8"))
    return load_table(DATA_DIR / "demo_clients.csv"), date.fromisoformat(manifest["reference_date"])


@st.cache_data(show_spinner=False)
def load_upload(content: bytes, filename: str) -> pd.DataFrame:
    return load_table(io.BytesIO(content), filename)


@st.cache_data(show_spinner=False)
def run_audit(df: pd.DataFrame, today: date) -> AuditResult:
    return audit(df, today)


def bar_chart(scores: pd.Series, hover_label: str) -> go.Figure:
    """Horizontal bars, one per column, on a fixed 0-100 axis."""
    fig = go.Figure(
        go.Bar(
            x=scores.values,
            y=scores.index,
            orientation="h",
            marker={"color": BAR_COLOR, "cornerradius": 4},
            hovertemplate=f"<b>%{{y}}</b><br>%{{x:.1f}} % {hover_label}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(160, 28 * len(scores) + 60),
        margin={"l": 0, "r": 16, "t": 8, "b": 32},
        bargap=0.35,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": MUTED_INK},
        xaxis={
            "range": [0, 100],
            "ticksuffix": " %",
            "gridcolor": "rgba(137,135,129,0.2)",
            "zeroline": False,
        },
        yaxis={"autorange": "reversed"},
    )
    return fig


def score_text(score: float | None) -> str:
    return "s.o." if score is None else fr_pct(score)


def show_summary(result: AuditResult) -> None:
    head = st.columns([2, 1, 1])
    head[0].metric("Score global", score_text(result.overall))
    head[1].metric("Lignes", fr_int(result.rows))
    head[2].metric("Colonnes", len(result.profiles))
    tiles = st.columns(len(DIMENSION_NAMES))
    for tile, name in zip(tiles, DIMENSION_NAMES, strict=True):
        tile.metric(name, score_text(result.scores[name]))
    if any(s is None for s in result.scores.values()):
        st.caption("s.o. : sans objet pour ce fichier, exclu du score global.")


def show_issues(result: AuditResult) -> None:
    st.markdown("#### Points à corriger")
    issues = list_issues(result)
    if not issues:
        st.success("Aucun problème détecté.")
        return
    rows = [
        {
            "Dimension": i.dimension,
            "Colonne": i.column or "(lignes entières)",
            "Problème": i.message,
            "Recommandation": i.advice,
        }
        for i in issues
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def show_details(result: AuditResult) -> None:
    st.markdown("#### Détail par dimension")
    tabs = st.tabs(list(DIMENSION_NAMES))

    with tabs[0]:
        st.caption(RULES["Complétude"])
        st.plotly_chart(
            bar_chart(result.completeness_by_column, "rempli"), use_container_width=True
        )

    with tabs[1]:
        st.caption(RULES["Unicité"])
        u = result.uniqueness
        key = f"« {u.key} »" if u.key else "aucune (lignes entières comparées)"
        st.write(f"**Clé détectée :** {key}")
        st.write(f"**Doublons sur la clé :** {fr_int(u.duplicates_on_key)}")
        st.write(f"**Lignes strictement identiques :** {fr_int(u.duplicate_rows)}")

    with tabs[2]:
        st.caption(RULES["Validité"])
        if not result.validity_by_column:
            st.info("Aucune colonne au format vérifiable.")
        else:
            scores = pd.Series({c: v.score for c, v in result.validity_by_column.items()})
            st.plotly_chart(
                bar_chart(scores.sort_values(kind="stable"), "valide"),
                use_container_width=True,
            )

    with tabs[3]:
        st.caption(RULES["Cohérence"])
        if not result.consistency_by_column:
            st.info("Aucune colonne dont le format d'écriture peut varier.")
        else:
            rows = [
                {
                    "Colonne": col,
                    "Score": fr_pct(d.count.score),
                    "Formats rencontrés": " · ".join(
                        f"{layout_label(k)} ({fr_int(v)})" for k, v in d.layouts.items()
                    ),
                }
                for col, d in sorted(
                    result.consistency_by_column.items(), key=lambda kv: kv[1].count.score
                )
            ]
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    with tabs[4]:
        st.caption(RULES["Fraîcheur"])
        f = result.freshness
        if f is None:
            st.info("Aucune colonne de date : la fraîcheur ne s'applique pas.")
        else:
            st.write(f"**Date la plus récente :** {f.latest:%d/%m/%Y} (colonne « {f.column} »)")
            st.write(f"**Âge :** {fr_int(f.age_days)} jour(s)")


def show_columns(result: AuditResult) -> None:
    with st.expander("Colonnes et types détectés"):
        rows = [
            {
                "Colonne": col,
                "Type détecté": TYPE_LABELS[p.dtype],
                "Valeurs remplies": p.filled,
                "Complétude (%)": result.completeness_by_column[col],
            }
            for col, p in result.profiles.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


RISK_BADGES = {"Élevé": "🔴 Élevé", "Moyen": "🟠 Moyen", "Faible": "🟡 Faible"}


def show_personal_data(result: AuditResult) -> None:
    st.markdown("#### Renseignements personnels (Loi 25)")
    found = result.personal_data
    if not found:
        st.success("Aucune colonne ne semble contenir de renseignements personnels.")
        return
    high = sum(f.risk == "Élevé" for f in found)
    verb = "contient" if len(found) == 1 else "contiennent"
    summary = (
        f"{plural(len(found), 'colonne', 'colonnes')} {verb} probablement "
        "des renseignements personnels"
    )
    summary += f", dont {high} à risque élevé." if high else "."
    (st.error if high else st.warning)(summary)
    rows = [
        {
            "Colonne": f.column,
            "Catégorie": f.label,
            "Risque": RISK_BADGES[f.risk],
            "Détecté par": f.detected_by,
            "Exemple (masqué)": f.example,
            "Recommandation": f.recommendation,
        }
        for f in found
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "Détection automatique à partir du nom des colonnes et du format des valeurs : "
        "à confirmer par une personne. Les exemples sont masqués ; aucune valeur n'est "
        "affichée en clair. Ceci n'est pas un avis juridique."
    )


def show_results(result: AuditResult, source: str) -> None:
    st.subheader(f"Résultats : {source}")
    show_summary(result)
    show_issues(result)
    show_personal_data(result)
    show_details(result)
    show_columns(result)


st.title("🔎 Auditeur de qualité des données")
st.write(
    "Téléversez un fichier CSV ou Excel : l'outil mesure la qualité de vos données sur cinq "
    "dimensions et indique quoi corriger. Les fichiers sont analysés en mémoire et ne sont "
    "jamais conservés."
)
st.caption("Version en construction. Projet de Barbara Saroukou.")

left, right = st.columns([1, 2])
with left:
    if st.button("Essayer avec des données de démo", type="primary"):
        st.session_state["source"] = "demo"
    st.caption("5 000 clients fictifs, avec des erreurs ajoutées volontairement.")
with right:
    uploaded = st.file_uploader(
        f"Ou téléversez votre fichier (CSV ou XLSX, {fr_int(MAX_ROWS)} lignes max.)",
        type=["csv", "xlsx"],
    )
    if uploaded is not None:
        st.session_state["source"] = "upload"

source = st.session_state.get("source")
if source == "upload" and uploaded is not None:
    try:
        with st.spinner("Analyse en cours…"):
            data = load_upload(uploaded.getvalue(), uploaded.name)
            result = run_audit(data, date.today())
        show_results(result, uploaded.name)
    except TooManyRowsError as error:
        st.error(str(error))
    except Exception:
        st.error("Impossible de lire ce fichier. Vérifiez que c'est un CSV ou un XLSX valide.")
elif source == "demo":
    with st.spinner("Analyse en cours…"):
        data, reference_date = load_demo()
        result = run_audit(data, reference_date)
    show_results(result, "données de démo")
    st.caption(
        f"La fraîcheur de la démo est calculée au {reference_date:%d/%m/%Y}, "
        "date à laquelle les données fictives ont été générées."
    )

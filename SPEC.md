# Spec : Auditeur de qualité des données

## Hypothèses (à corriger si besoin)
1. Application web Streamlit, déployée gratuitement sur Streamlit Community Cloud.
2. Fichiers acceptés : CSV et Excel (.xlsx), jusqu'à 50 Mo / 200 000 lignes.
3. Aucune donnée n'est conservée : tout est traité en mémoire, puis effacé à la fin de la session.
4. Données de démo 100 % fictives (clients d'une entreprise fictive, avec des erreurs volontaires).
5. Interface en français, code et commentaires en anglais.

## Objectif
Un outil qui note la qualité d'un jeu de données en moins de 30 secondes et explique quoi corriger.
Public principal : des recruteurs en données et gouvernance qui ouvrent le lien depuis le CV ou LinkedIn.
Ils doivent comprendre la valeur de l'outil en 2 minutes, sans rien installer.

**Parcours utilisateur**
- En tant que visiteur, je clique sur « Essayer avec des données de démo » et je vois un score global en moins de 10 s.
- En tant qu'analyste, je téléverse mon CSV et j'obtiens un score par colonne et par dimension.
- En tant que responsable conformité, je vois quelles colonnes contiennent probablement des renseignements personnels (Loi 25).
- En tant qu'utilisateur, je télécharge un rapport HTML à joindre à un ticket.

**Dimensions mesurées** (score de 0 à 100 chacune)
| Dimension | Règle |
|---|---|
| Complétude | % de valeurs non nulles et non vides |
| Unicité | % de lignes non dupliquées, plus les doublons sur la clé choisie |
| Validité | % de valeurs conformes au type détecté (courriel, téléphone nord-américain, code postal canadien, date) |
| Cohérence | Formats mixtes dans une même colonne (ex. 2026-10-25 et 25/10/2026) |
| Fraîcheur | Âge de la date la plus récente, si une colonne de date existe |

**Détection de renseignements personnels** : courriel, téléphone, NAS (format seulement, sans jamais l'afficher en clair), date de naissance, adresse. Chaque colonne détectée reçoit un niveau de risque et une recommandation (masquer, pseudonymiser, supprimer).

## Stack technique
- Python 3.11
- Streamlit 1.x, pandas 2.x, Great Expectations n'est **pas** utilisé (trop lourd pour la démo)
- Plotly pour les graphiques
- pytest + pytest-cov pour les tests
- ruff pour le formatage

## Commandes
```
Installation : pip install -r requirements.txt
Lancer       : streamlit run app.py
Tests        : pytest --cov=dq --cov-report=term-missing
Lint         : ruff check . --fix && ruff format .
Données démo : python scripts/generate_demo_data.py --rows 5000 --seed 42
```

## Structure du projet
```
app.py                  → Interface Streamlit (affichage seulement)
dq/
  profiling.py          → Détection des types de colonnes
  dimensions.py         → Calcul des 5 scores
  pii.py                → Détection de renseignements personnels
  report.py             → Génération du rapport HTML
data/demo_clients.csv   → Jeu de démo fictif
scripts/                → Génération des données de démo
tests/                  → Un fichier de test par module de dq/
SPEC.md, README.md
```

## Style de code
Logique métier dans `dq/`, sans aucun import de Streamlit, pour qu'elle reste testable.
```python
def completeness(series: pd.Series) -> float:
    """Return the share of non-null, non-blank values, from 0 to 100."""
    if series.empty:
        return 100.0
    filled = series.notna() & (series.astype(str).str.strip() != "")
    return round(filled.mean() * 100, 1)
```
- Fonctions pures, typées, avec une docstring d'une ligne
- Noms en snake_case, explicites (`duplicate_rate`, pas `dr`)

## Stratégie de tests
- Tests unitaires pour chaque fonction de `dq/`, avec de petits DataFrames construits à la main
- Cas limites obligatoires : colonne vide, colonne 100 % nulle, un seul enregistrement, caractères accentués (é, ç), fichier encodé en latin-1
- Couverture visée : 85 % ou plus sur `dq/`
- L'interface `app.py` est vérifiée manuellement avec le jeu de démo

## Limites
- **Toujours :** lancer les tests avant chaque commit ; masquer toute valeur détectée comme sensible dans l'affichage ; utiliser uniquement des données fictives dans le dépôt
- **Demander d'abord :** ajouter une dépendance ; ajouter une base de données ou un stockage ; changer d'hébergeur
- **Jamais :** enregistrer les fichiers téléversés ; journaliser le contenu des cellules ; publier des données réelles de M2D ou d'un client

## Critères de réussite
- [ ] Le jeu de démo (5 000 lignes) est analysé en moins de 10 s sur Streamlit Cloud
- [ ] Les 5 dimensions et le score global s'affichent, avec un graphique par dimension
- [ ] Les erreurs injectées dans le jeu de démo sont toutes retrouvées (ex. 3 % de doublons injectés → 3 % détectés)
- [ ] Au moins 90 % des colonnes contenant des renseignements personnels sont signalées dans le jeu de démo
- [ ] Le rapport HTML se télécharge et s'ouvre sans connexion Internet
- [ ] Couverture de tests de 85 % ou plus, aucun test en échec
- [ ] README avec capture d'écran, lien de démo et explication des règles
- [ ] Lien ajouté au portfolio et au CV

## Décisions (approuvées le 2026-10-25)
1. Rapport en **HTML seulement**, sans PDF.
2. La colonne clé des doublons est **détectée automatiquement** : son nom contient le mot « id », « identifiant », « code », « matricule », « numero », « num » ou « no » ; elle n'est ni un code postal, ni un téléphone, ni un courriel, ni une date ; elle a au moins 90 % de valeurs distinctes. Entre plusieurs candidates, la plus distincte gagne (à égalité, la plus à gauche). Sinon, on compare les lignes entières.
4. Score global = moyenne des dimensions applicables. Une dimension sans objet (ex. pas de colonne de date pour la fraîcheur) est affichée « s.o. » et exclue.
5. Fraîcheur : 100 jusqu'à 30 jours, 0 à 365 jours, linéaire entre les deux ; les dates futures sont ignorées. La démo est évaluée à sa date de génération (20/10/2026) pour rester stable.
3. Interface **en français seulement**.

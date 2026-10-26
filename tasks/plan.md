# Plan : Auditeur de qualité des données

Référence : SPEC.md (approuvée le 2026-10-25)

## Composants et dépendances
```
generate_demo_data ─┐
                    ▼
profiling ──► dimensions ──┐
    │                      ├──► report ──► app.py ──► déploiement
    └──────► pii ──────────┘
```
- `profiling` détecte le type de chaque colonne (texte, nombre, date, courriel, téléphone, code postal). Tous les autres modules en dépendent.
- `dimensions` et `pii` sont indépendants l'un de l'autre et peuvent être construits en parallèle.
- `report` assemble les résultats. `app.py` ne fait qu'afficher.

## Ordre de construction (tranches verticales)
Chaque phase se termine par quelque chose qui fonctionne et qu'on peut montrer.

**Phase 1 : Fondations** (environ 2 h)
Données de démo avec erreurs connues, puis le profilage des types.
✔ Point de contrôle : `pytest` passe et le jeu de démo contient exactement les erreurs injectées.

**Phase 2 : Premier score de bout en bout** (environ 3 h)
Complétude seulement, plus une page Streamlit minimale : bouton de démo, score affiché.
✔ Point de contrôle : `streamlit run app.py` affiche un vrai score en moins de 10 s.

**Phase 3 : Les 4 autres dimensions** (environ 4 h)
Unicité (avec détection de la clé), validité, cohérence, fraîcheur, puis le score global.
✔ Point de contrôle : chaque erreur injectée est retrouvée au bon pourcentage (±0,5 point).

**Phase 4 : Renseignements personnels** (environ 2 h)
Détection et affichage masqué, avec une recommandation par colonne.
✔ Point de contrôle : au moins 90 % des colonnes sensibles de la démo sont signalées, et aucune valeur n'apparaît en clair.

**Phase 5 : Rapport, finition et mise en ligne** (environ 3 h)
Rapport HTML autonome, graphiques Plotly, README, déploiement sur Streamlit Cloud.
✔ Point de contrôle : tous les critères de réussite de la spec sont cochés.

Total estimé : environ 14 h, soit 3 à 4 soirées.

## Risques
| Risque | Parade |
|---|---|
| Fichier en latin-1 (fréquent avec Excel au Québec) | Essayer UTF-8, puis latin-1 ; test dédié |
| Faux positifs de renseignements personnels (ex. un numéro de commande pris pour un téléphone) | Combiner le nom de la colonne et le format, avec un seuil de 80 % de valeurs conformes |
| Lenteur sur Streamlit Cloud (1 Go de RAM) | Limite de 200 000 lignes et `st.cache_data` |
| Détection de clé erronée | Afficher la clé choisie à l'écran, pour que l'utilisateur la voie |

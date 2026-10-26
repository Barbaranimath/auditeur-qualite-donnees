# Tâches

## Phase 1 : Fondations
- [x] T1 : Initialiser le projet
  - Acceptance : requirements.txt, ruff configuré, dossier dq/ et tests/ créés
  - Verify : `pytest` s'exécute (0 test) ; `ruff check .` ne signale rien
  - Files : requirements.txt, pyproject.toml, dq/__init__.py
- [x] T2 : Générer le jeu de démo fictif
  - Acceptance : 5 000 clients fictifs avec erreurs connues : 3 % de doublons, 8 % de courriels vides, 5 % de téléphones invalides, dates en 2 formats, colonnes NAS/naissance/adresse
  - Verify : un test relit le CSV et retrouve les taux exacts (seed 42)
  - Files : scripts/generate_demo_data.py, data/demo_clients.csv, tests/test_demo_data.py
- [x] T3 : Profilage des types de colonnes
  - Acceptance : chaque colonne reçoit un type parmi texte, nombre, date, courriel, téléphone, code_postal
  - Verify : `pytest tests/test_profiling.py` ; cas accentués et latin-1 inclus
  - Files : dq/profiling.py, dq/io.py, dq/patterns.py, tests/test_profiling.py, tests/test_io.py
  - Note : patterns.py créé dès T3 (prévu en T7) car le profilage en a besoin

## Phase 2 : Premier score de bout en bout
- [x] T4 : Score de complétude
  - Acceptance : score par colonne et global ; colonne vide = 100, colonne 100 % nulle = 0
  - Verify : `pytest tests/test_dimensions.py -k completeness`
  - Files : dq/dimensions.py, tests/test_dimensions.py
- [x] T5 : Page Streamlit minimale
  - Acceptance : bouton « Essayer avec des données de démo » + téléversement CSV/XLSX ; affiche la complétude
  - Verify : manuel, `streamlit run app.py`, moins de 10 s
  - Files : app.py

## Phase 3 : Autres dimensions
- [x] T6 : Unicité + détection automatique de la clé
  - Verify : 3 % de doublons retrouvés ; clé `client_id` choisie automatiquement
  - Files : dq/dimensions.py, tests/test_dimensions.py
- [x] T7 : Validité (courriel, téléphone, code postal, date)
  - Verify : 5 % de téléphones invalides retrouvés
  - Files : dq/dimensions.py, dq/patterns.py, tests/test_dimensions.py
- [x] T8 : Cohérence et fraîcheur
  - Verify : les 2 formats de date sont signalés ; l'âge de la date la plus récente est correct
  - Files : dq/dimensions.py, tests/test_dimensions.py
- [x] T9 : Score global + affichage des 5 dimensions
  - Verify : manuel ; un graphique par dimension
  - Files : dq/dimensions.py, app.py

- Note phase 3 : ajout de dq/audit.py (assemble les 5 dimensions), dq/issues.py (liste « Points à corriger ») et dq/fmt.py (formats français)

## Phase 4 : Renseignements personnels
- [x] T10 : Détection et niveau de risque
  - Verify : au moins 90 % des colonnes sensibles de la démo sont signalées ; un numéro de commande n'est pas signalé
  - Files : dq/pii.py, tests/test_pii.py
- [x] T11 : Affichage masqué et recommandations
  - Verify : aucune valeur sensible en clair à l'écran (test sur la fonction de masquage + vérif manuelle)
  - Files : dq/pii.py, app.py

## Phase 5 : Rapport et mise en ligne
- [ ] T12 : Rapport HTML autonome
  - Verify : le fichier s'ouvre sans connexion Internet (Plotly intégré)
  - Files : dq/report.py, tests/test_report.py, app.py
- [ ] T13 : README + capture d'écran
  - Files : README.md
- [ ] T14 : Déploiement Streamlit Cloud
  - Verify : lien public fonctionnel ; démo en moins de 10 s
- [ ] T15 : Vérification finale
  - Verify : couverture ≥ 85 % ; tous les critères de SPEC.md cochés ; lien ajouté au portfolio et au CV

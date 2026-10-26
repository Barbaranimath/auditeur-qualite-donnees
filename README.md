# Auditeur de qualité des données

Outil Streamlit qui note la qualité d'un jeu de données (complétude, unicité, validité,
cohérence, fraîcheur) et repère les renseignements personnels (Loi 25).
Projet de portfolio de Barbara Saroukou. 
**Démo en ligne : https://auditeur-qualite-donnees-bs.streamlit.app**


## Démarrer
```
pip install -r requirements-dev.txt
python scripts/generate_demo_data.py --rows 5000 --seed 42
pytest --cov=dq --cov-report=term-missing
streamlit run app.py
```

![Capture de l'application](docs/capture-demo.png)

Voir `SPEC.md` pour les règles et `tasks/` pour l'avancement.
Toutes les données de `data/` sont fictives.

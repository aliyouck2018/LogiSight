# Guide de développement

## Prérequis

- Python 3.12+
- SQLite 3 (inclus avec Python)
- Make (optionnel)

## Installation

```bash
make setup          # venv + dépendances + migrations + données + alertes
```

Ou manuellement :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # ajuster si besoin
flask --app run.py db upgrade
python scripts/generate_data.py
python scripts/generate_alerts.py
```

## Lancement

```bash
python run.py                   # http://localhost:5000
# ou
flask --app run.py run --debug
# production-like
.venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 run:app
```

## Régénérer les données

```bash
SEED=42 N_SHIPMENTS=20000 N_MONTHS=24 python scripts/generate_data.py
python scripts/generate_alerts.py
```

Le dataset est déterministe : la même graine produit exactement les mêmes
données (utile pour les démonstrations et les tests).

## Migrations

```bash
flask --app run.py db migrate -m "description"
flask --app run.py db upgrade
make db-reset    # (dev) supprime la base et régénère les migrations
```

## Tests

```bash
make test        # pytest tests -v
```

- `tests/unit/` — KPI, score de risque, statistiques
- `tests/integration/` — modèle, qualité de données, moteur d'alertes
- `tests/api/` — endpoints REST via le client de test Flask

La base de test est en mémoire et semée avec un petit dataset (60 expéditions).

## Conventions

- Python : type hints, docstrings sur les fonctions importantes, fonctions courtes.
- Aucune logique métier dans les templates Jinja2 ni dans les routes.
- Les nouveaux KPI doivent être documentés dans `docs/kpis.md` et testés.
- CSS : consommer les tokens de `static/css/tokens.css` (pas de couleurs en dur).
- JS : formateurs fr-FR et mappages via `app.js` (`fmt`, `STATUS_LABELS`, …).

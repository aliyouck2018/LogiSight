PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
FLASK ?= .venv/bin/flask
PYTEST ?= .venv/bin/pytest

FLASK_APP = FLASK_APP=run.py

.PHONY: setup venv install db-upgrade generate-data generate-alerts run test clean

## Full setup: venv + deps + migrations + synthetic data + alerts
setup: venv install db-upgrade generate-data generate-alerts

venv:
	python3 -m venv .venv

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

## Apply database migrations
db-upgrade:
	$(FLASK_APP) $(FLASK) db upgrade

## Recreate migrations from scratch (dev only)
db-reset:
	rm -f data/logisight.db
	rm -rf migrations/versions/*
	$(FLASK_APP) $(FLASK) db init 2>/dev/null || true
	$(FLASK_APP) $(FLASK) db migrate -m "initial schema"
	$(FLASK_APP) $(FLASK) db upgrade

## Generate synthetic dataset (seeded, reproducible)
generate-data:
	$(PYTHON) scripts/generate_data.py

## Generate operational alerts from generated data
generate-alerts:
	$(PYTHON) scripts/generate_alerts.py

## Run the development server
run:
	$(PYTHON) run.py

## Run the test suite
test:
	$(PYTEST) tests -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache

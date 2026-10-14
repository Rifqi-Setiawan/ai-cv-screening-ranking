.PHONY: test lint typecheck run-api run-worker eval seed clean migrate

VENV = .venv
PYTHON = $(VENV)/bin/python
UVICORN = $(VENV)/bin/uvicorn
PYTEST = $(VENV)/bin/pytest
RUFF = $(VENV)/bin/ruff
MYPY = $(VENV)/bin/mypy
ALEMBIC = $(VENV)/bin/alembic

migrate:
	$(ALEMBIC) upgrade head

test:
	PYTHONPATH=. $(PYTEST) -v

lint:
	$(RUFF) check src tests

format:
	$(RUFF) format src tests

typecheck:
	$(MYPY) src tests --ignore-missing-imports

run-api:
	$(UVICORN) src.api.main:app --host 127.0.0.1 --port 8110 --reload

run-worker:
	PYTHONPATH=. $(PYTHON) -m src.worker.main

seed:
	PYTHONPATH=. $(PYTHON) scripts/seed_users.py

eval:
	cd docs/spec/golden_dataset && python3 evaluate.py --self-test
	PYTHONPATH=/srv/hermes-control/services/cv-extractor/src $(PYTHON) scripts/m0_test_adapter.py
	python3 docs/spec/golden_dataset/evaluate.py --extraction scripts/pred_extraction.json

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +

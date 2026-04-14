.PHONY: install test lint run-ai clean

VENV = venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install -e ".[dev]"
	$(PIP) install pytest flake8 black isort mypy bandit safety

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(VENV)/bin/black src/ tests/ examples/
	$(VENV)/bin/isort src/ tests/ examples/
	$(VENV)/bin/flake8 src/ tests/

run-ai:
	$(PYTHON) src/vanna_grok.py

clean:
	rm -rf __pycache__ .pytest_cache .mypy_cache .ruff_cache
	rm -rf $(VENV)

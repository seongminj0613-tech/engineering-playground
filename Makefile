SHELL := /bin/bash
PY := python
VENV := .venv
PIP := $(VENV)/Scripts/pip
PYV := $(VENV)/Scripts/python

# ✅ 여기만 네 실행에 맞게 조정
ENTRY := -m app.main

.PHONY: help setup install run serve test lint fmt clean

help:
	@echo "make setup   : create venv + install"
	@echo "make run     : run full pipeline"
	@echo "make serve   : preview docs locally"
	@echo "make test    : run pytest"
	@echo "make lint    : ruff check"
	@echo "make fmt     : ruff format"

setup:
	$(PY) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

install:
	$(PIP) install -r requirements.txt

run:
	$(PYV) $(ENTRY)

serve:
	$(PYV) -m http.server 5173 --directory docs

test:
	$(PYV) -m pytest -q

lint:
	$(PYV) -m ruff check .

fmt:
	$(PYV) -m ruff format .

clean:
	rm -rf .pytest_cache .ruff_cache reports/runs/*.json
.PHONY: setup crawl validate index all

PYTHON ?= python
VENV := .venv

ifeq ($(OS),Windows_NT)
PYTHON_BIN := $(VENV)/Scripts/python
PIP_BIN := $(VENV)/Scripts/pip
else
PYTHON_BIN := $(VENV)/bin/python
PIP_BIN := $(VENV)/bin/pip
endif

setup:
	$(PYTHON) -m venv $(VENV)
	$(PYTHON_BIN) -m pip install -U pip
	$(PYTHON_BIN) -m pip install -r collector/requirements.txt

crawl:
	$(PYTHON_BIN) -m collector.main $(ARGS)

validate:
	$(PYTHON_BIN) -m collector.validate

index:
	$(PYTHON_BIN) tools/build_index.py

all: crawl validate index

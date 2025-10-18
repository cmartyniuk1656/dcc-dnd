.PHONY: setup crawl validate index all

setup:
	python -m venv .venv
	. .venv/bin/activate && pip install -U pip && pip install -r collector/requirements.txt

crawl:
	. .venv/bin/activate && python collector/main.py

validate:
	. .venv/bin/activate && python collector/validate.py

index:
	. .venv/bin/activate && python tools/build_index.py

all: crawl validate index

# dcc-dnd

Collector and JSON archive for Dungeon Crawler Carl items and abilities. It uses the Fandom MediaWiki API plus OpenAI structured outputs to create validated, versioned data for websites and Foundry VTT.

## Prerequisites
- Python 3.11
- OpenAI API key with access to the configured model
- Make (optional but recommended)

Copy `.env.example` to `.env` and fill in the values you intend to use, especially `OPENAI_API_KEY` and `CRAWLER_CONTACT_EMAIL`.

```bash
cp .env.example .env
```

## Setup

```bash
make setup
```

This creates `.venv`, upgrades `pip`, and installs `collector/requirements.txt`.

## Commands
- `make crawl` – run the collector (`collector/main.py`) to fetch MediaWiki pages, extract data with OpenAI, and write JSON to `data/v1/items/`.
- `make validate` – validate every JSON record against `schemas/dcc-record.schema.json`.
- `make index` – rebuild `data/v1/index.json` from the generated item records.
- `make all` – run crawl, validate, and index in sequence.

All commands source the virtual environment created during setup.

## Politeness & Licensing
- Requests are routed through the MediaWiki API with a 0.7s base delay and automatic exponential backoff on server errors.
- Raw wikitext is cached under `data/v1/raw/` so unchanged pages are skipped on subsequent runs.
- Only minimal rules text is stored; each record includes `provenance.source_ref` linking back to the original wiki URL.

## Foundry Notes
- Records capture image metadata (`images[]`) suitable for Foundry tokens, icons, and tiles.
- When available, Foundry-specific hints such as token border and grid size live under `images[].foundry`.

## Sample Query

Once you have generated data and built the index, you can inspect it with:

```bash
curl -s http://localhost:8000/data/v1/index.json | jq '.items[:3]'
```

Serve the repository root however you like (for example, `python -m http.server`) before issuing the curl command.

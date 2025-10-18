MASTER PROMPT FOR CODE AGENT

You are my engineering assistant. Create a brand-new public repository that collects item/ability data from the Dungeon Crawler Carl fan wiki via the MediaWiki API, extracts structured information using OpenAI Structured Outputs (JSON Schema), validates it, and publishes versioned JSON suitable for websites and Foundry VTT.

Follow the instructions below exactly. If anything is ambiguous, choose a sensible default and proceed.

0) Project name

Repository name: dcc-dnd

1) Goals (what we’re building)

A schema-first JSON archive of DCC items/abilities.

A polite collector that:

lists item pages from Fandom MediaWiki categories,

fetches wikitext/HTML,

extracts data to our JSON schema via OpenAI Structured Outputs,

validates each record,

writes files under data/v1/items/*.json,

builds data/v1/index.json.

CI that validates JSON on every PR.

A Makefile to run the common tasks.

Documentation for setup and running.

2) Requirements & constraints

Language: Python 3.11.

Libraries: requests, tenacity, tqdm, orjson, python-dotenv, jsonschema, openai>=1.30.0.

Be a polite client: 0.7s base delay between MediaWiki calls + exponential backoff.

Respect licensing: store minimal rules text; include source URL in provenance.source_ref.

Do not scrape HTML with brittle selectors if the API can provide data; prefer MediaWiki API.

Support idempotent runs: cache raw wikitext to disk; re-extract only if content changed.

All JSON must validate against our schema (below).

3) Repository layout (create exactly this)
dcc-dnd/
├─ README.md
├─ .gitignore
├─ .editorconfig
├─ .env.example
├─ Makefile
├─ data/
│  └─ v1/
│     ├─ items/            # generated JSON per item
│     ├─ raw/              # cached raw wikitext
│     └─ index.json        # built by tools/build_index.py
├─ schemas/
│  └─ dcc-record.schema.json
├─ collector/
│  ├─ requirements.txt
│  ├─ config.py
│  ├─ mediawiki.py
│  ├─ extractor_openai.py
│  ├─ validate.py
│  └─ main.py
├─ tools/
│  └─ build_index.py
└─ .github/
   └─ workflows/
      └─ ci.yml

4) File contents to create
4.1 .gitignore
__pycache__/
*.pyc
.env
.venv/
.cache/
data/**/raw/
data/**/tmp/

4.2 .editorconfig
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true

[*.{json,jsonc}]
indent_style = space
indent_size = 2

[*.py]
indent_style = space
indent_size = 4

4.3 .env.example
OPENAI_API_KEY=sk-xxxxx
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-5-thinking
CRAWLER_CONTACT_EMAIL=you@example.com

4.4 Makefile
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

4.5 schemas/dcc-record.schema.json

Use this final schema. It includes: core fields; activation[]; enchantments[]; effects[] with trigger/chance/outcomes and nested atomic actions; images[]; form; weapon/consumable/power/area/save/modifiers/targeting; attunement/tattoo/tech; physical/economy; dnd5e_mapping; balance_flags; provenance; metadata.

{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/schemas/dcc-record.schema.json",
  "title": "Dungeon Crawler Carl — Record",
  "type": "object",
  "additionalProperties": false,
  "required": ["id", "name", "kind", "effects", "provenance", "metadata"],
  "properties": {
    "id": { "type": "string" },
    "name": { "type": "string" },
    "aliases": { "type": "array", "items": { "type": "string" } },
    "series": { "type": "string", "default": "Dungeon Crawler Carl" },
    "kind": { "type": "string", "enum": ["Item","Ability","Perk","Title","Tattoo","Other"] },
    "subcategory": { "type": ["string","null"] },
    "slot": { "type": ["string","null"] },
    "rarity": { "type": ["string","null"] },
    "level_requirement": { "type": ["integer","null"] },
    "tags": { "type": "array", "items": { "type": "string" } },

    "form": {
      "type": ["object","null"],
      "additionalProperties": false,
      "properties": {
        "conjured": { "type": "boolean" },
        "material": { "type": ["string","null"] },
        "description": { "type": ["string","null"] }
      }
    },

    "activation": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "properties": {
          "via": { "type": "string", "description": "command|gesture|ui|passive|throw|drink|equip" },
          "detail": { "type": ["string","null"] },
          "cooldown_seconds": { "type": ["number","null"] },
          "charges": { "type": ["integer","null"] }
        }
      }
    },

    "enchantments": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": true,
        "properties": {
          "name": { "type": "string" },
          "parameters": { "type": "object" }
        }
      }
    },

    "images": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type","src"],
        "additionalProperties": false,
        "properties": {
          "type": { "type": "string", "enum": ["icon","portrait","token","tile","splash","other"] },
          "src": { "type": "string" },
          "srcset": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["src"],
              "properties": {
                "src": { "type": "string" },
                "descriptor": { "type": ["string","null"] }
              },
              "additionalProperties": false
            }
          },
          "alt": { "type": ["string","null"] },
          "title": { "type": ["string","null"] },
          "width": { "type": ["integer","null"] },
          "height": { "type": ["integer","null"] },
          "mime": { "type": ["string","null"] },
          "transparent": { "type": ["boolean","null"] },
          "focal_point": {
            "type": ["object","null"],
            "properties": { "x": { "type": "number" }, "y": { "type": "number" } },
            "additionalProperties": false
          },
          "attribution": {
            "type": ["object","null"],
            "properties": {
              "author": { "type": ["string","null"] },
              "source_url": { "type": ["string","null"] },
              "license": { "type": ["string","null"] }
            },
            "additionalProperties": false
          },
          "hash_sha256": { "type": ["string","null"] },
          "cdn_key": { "type": ["string","null"] },
          "spoiler": { "type": ["boolean","null"] },
          "foundry": {
            "type": ["object","null"],
            "properties": {
              "token_border": { "type": ["boolean","null"] },
              "ring_color": { "type": ["string","null"] },
              "size_grid": { "type": ["number","null"] }
            },
            "additionalProperties": false
          }
        }
      }
    },

    "weapon": {
      "type": ["object","null"],
      "additionalProperties": false,
      "properties": {
        "category": { "type": "string" },
        "handedness": { "type": ["string","null"] },
        "reach_m": { "type": ["number","null"] },
        "range_m": { "type": ["object","null"], "properties": { "normal": { "type":"number" }, "long": { "type":"number" } }, "additionalProperties": false },
        "properties": { "type": "array", "items": { "type": "string" } },
        "damage": {
          "type": "array",
          "items": { "type": "object", "properties": { "dice": { "type":"string" }, "type": { "type":"string" }, "on_crit": { "type": ["string","null"] } }, "additionalProperties": false }
        }
      }
    },

    "consumable": {
      "type": ["object","null"],
      "additionalProperties": false,
      "properties": {
        "uses": { "type": ["integer","null"] },
        "stack_limit": { "type": ["integer","null"] },
        "use_time": { "type": ["string","null"] },
        "cooldown_seconds": { "type": ["number","null"] },
        "duration_seconds": { "type": ["number","null"] },
        "overdose_rules": { "type": ["string","null"] }
      }
    },

    "power": {
      "type": ["object","null"],
      "additionalProperties": false,
      "properties": {
        "charges_max": { "type": ["integer","null"] },
        "charges_current": { "type": ["integer","null"] },
        "recharge": {
          "type": ["object","null"],
          "properties": { "method": { "type":"string" }, "rate_per_hour": { "type":["number","null"] } },
          "additionalProperties": false
        },
        "energy_type": { "type": ["string","null"] }
      }
    },

    "effects": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name","trigger"],
        "additionalProperties": false,
        "properties": {
          "name": { "type": "string" },
          "trigger": {
            "type": "object",
            "properties": {
              "event": { "type": "string" },
              "conditions": {
                "type": "array",
                "items": { "type": "object", "properties": { "left": { "type":"string" }, "op": { "type":"string" }, "right": {} }, "additionalProperties": false }
              }
            },
            "additionalProperties": false
          },
          "chance": { "type": ["number","null"], "minimum": 0, "maximum": 1 },
          "area": {
            "type": ["object","null"],
            "properties": {
              "shape": { "type": "string", "enum": ["sphere","cube","cone","line","cylinder"] },
              "size": { "type": "number" },
              "origin": { "type": "string" }
            },
            "additionalProperties": false
          },
          "save": {
            "type": ["object","null"],
            "properties": {
              "ability": { "type": "string" },
              "dc": { "type": "number" },
              "on_success": { "type": "string" }
            },
            "additionalProperties": false
          },
          "modifiers": {
            "type": "array",
            "items": { "type": "object", "properties": { "stat": { "type":"string" }, "op": { "type":"string", "enum":["add","mul","set"] }, "value": {}, "stack_rule": { "type":["string","null"] } }, "additionalProperties": false }
          },
          "targeting": {
            "type": ["object","null"],
            "properties": { "requires_los": { "type":"boolean" }, "max_targets": { "type":["integer","null"] }, "target_filter": { "type":["string","null"] } },
            "additionalProperties": false
          },
          "outcomes": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["result"],
              "properties": {
                "weight": { "type": ["number","null"] },
                "prob": { "type": ["number","null"], "minimum": 0, "maximum": 1 },
                "result": { "type": "string" },
                "effects": {
                  "type": "array",
                  "items": {
                    "type": "object",
                    "properties": {
                      "action": { "type": "string" },
                      "targets": { "type": "array", "items": { "type": "string" } },
                      "params": { "type": "object" }
                    },
                    "additionalProperties": false
                  }
                }
              },
              "additionalProperties": false
            }
          },
          "notes": { "type": ["string","null"] }
        }
      }
    },

    "attunement": {
      "type": ["object","null"],
      "properties": {
        "required": { "type": "boolean" },
        "slots": { "type": ["integer","null"] },
        "bound_to_character": { "type": ["boolean","null"] },
        "removal_conditions": { "type": ["string","null"] }
      },
      "additionalProperties": false
    },

    "tattoo": {
      "type": ["object","null"],
      "properties": {
        "body_location": { "type": "string" },
        "faction_keys": { "type": "array", "items": { "type": "string" } }
      },
      "additionalProperties": false
    },

    "tech": {
      "type": ["object","null"],
      "properties": {
        "manufacturer": { "type": ["string","null"] },
        "model": { "type": ["string","null"] },
        "firmware": { "type": ["string","null"] },
        "compatibility": { "type": "array", "items": { "type": "string" } }
      },
      "additionalProperties": false
    },

    "physical": {
      "type": ["object","null"],
      "properties": {
        "weight_kg": { "type": ["number","null"] },
        "size_category": { "type": ["string","null"] },
        "dimensions_cm": { "type": ["object","null"], "properties": { "w": {"type":"number"}, "h": {"type":"number"}, "d": {"type":"number"} }, "additionalProperties": false },
        "durability": { "type": ["object","null"], "properties": { "max": {"type":"integer"}, "current": {"type":"integer"}, "on_break": {"type":"string"} }, "additionalProperties": false }
      },
      "additionalProperties": false
    },

    "economy": {
      "type": ["object","null"],
      "properties": {
        "cost": { "type": ["number","null"] },
        "currency": { "type": ["string","null"] },
        "trade_value": { "type": ["number","null"] }
      },
      "additionalProperties": false
    },

    "rules_text": { "type": ["string","null"] },

    "dnd5e_mapping": {
      "type": ["object","null"],
      "properties": {
        "ac_bonus": { "type": ["integer","null"] },
        "requires_attunement": { "type": ["boolean","null"] },
        "action_economy": { "type": ["string","null"] },
        "notes": { "type": ["string","null"] }
      },
      "additionalProperties": false
    },

    "balance_flags": {
      "type": ["object","null"],
      "properties": {
        "gm_review_required": { "type": ["boolean","null"] },
        "homebrew_adjustments": { "type": ["string","null"] }
      },
      "additionalProperties": false
    },

    "provenance": {
      "type": "object",
      "required": ["source_type","source_ref","extraction_method","confidence"],
      "properties": {
        "source_type": { "type": "string" },
        "source_ref": { "type": "string" },
        "extraction_method": { "type": "string" },
        "extraction_notes": { "type": ["string","null"] },
        "confidence": { "type": "number", "minimum": 0, "maximum": 1 }
      },
      "additionalProperties": false
    },

    "metadata": {
      "type": "object",
      "required": ["created_at","updated_at","version","license"],
      "properties": {
        "created_at": { "type": "string", "format": "date-time" },
        "updated_at": { "type": "string", "format": "date-time" },
        "version": { "type": "string" },
        "license": { "type": "string" }
      },
      "additionalProperties": false
    }
  }
}

4.6 collector/requirements.txt
requests
tenacity
tqdm
orjson
python-dotenv
jsonschema
openai>=1.30.0

4.7 collector/config.py
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", None) or None
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-thinking")

WIKI_API = "https://dungeon-crawler-carl.fandom.com/api.php"
CRAWLER_CONTACT_EMAIL = os.getenv("CRAWLER_CONTACT_EMAIL", "you@example.com")
USER_AGENT = f"dcc-dnd-collector/1.0 ({CRAWLER_CONTACT_EMAIL})"

DATA_DIR = os.path.join("data", "v1", "items")
RAW_DIR = os.path.join("data", "v1", "raw")
SCHEMA_PATH = os.path.join("schemas", "dcc-record.schema.json")
CATEGORY_ROOT = "Items"
RATE_LIMIT_SECONDS = 0.7

4.8 collector/mediawiki.py
import os, time
from typing import List, Dict
import requests
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from collector.config import WIKI_API, USER_AGENT, RATE_LIMIT_SECONDS, RAW_DIR

os.makedirs(RAW_DIR, exist_ok=True)

class MWError(Exception): pass

@retry(wait=wait_exponential(multiplier=1, min=1, max=30),
       stop=stop_after_attempt(5),
       retry=retry_if_exception_type((requests.HTTPError, MWError)))
def _get(params: Dict) -> Dict:
    params = {**params, "format": "json"}
    r = requests.get(WIKI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    if r.status_code >= 500:
        raise MWError(f"Server error {r.status_code}")
    r.raise_for_status()
    time.sleep(RATE_LIMIT_SECONDS)
    return r.json()

def list_category_titles(category: str) -> List[str]:
    titles, cont = [], None
    while True:
        p = {"action":"query","list":"categorymembers","cmtitle":f"Category:{category}","cmlimit":500}
        if cont: p["cmcontinue"] = cont
        data = _get(p)
        titles += [x["title"] for x in data["query"]["categorymembers"] if x.get("ns") == 0]
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont: break
    return titles

def fetch_wikitext(title: str) -> Dict:
    data = _get({"action":"query","prop":"revisions","rvprop":"content","rvslots":"main","titles":title})
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    rev = page["revisions"][0]
    content = rev["slots"]["main"]["*"]
    path = os.path.join(RAW_DIR, f"{title}.wikitext.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"title": title, "wikitext": content, "pageid": page["pageid"]}

4.9 collector/extractor_openai.py
import json, os, datetime, hashlib
from typing import Dict, Any
from openai import OpenAI
from collector.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, SCHEMA_PATH

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in environment")

client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_BASE_URL else OpenAI(api_key=OPENAI_API_KEY)
SCHEMA = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))

SYSTEM = """You are an information extractor. Return ONLY JSON that validates against the provided schema.
Rules:
- Do not invent facts.
- If a field is unknown, set null or use empty arrays/objects.
- Put short canonical text into rules_text (no long quotes).
- Set provenance.source_type='wiki'; extraction_method='llm'.
- Fill metadata timestamps in ISO 8601 UTC; version='1.0.0'; license='TBD'."""

def iso_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def extract_record(page_title: str, page_url: str, page_text: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role":"system","content":SYSTEM},
            {"role":"user","content":"Return JSON that conforms to this JSON Schema:"},
            {"role":"user","content":json.dumps(SCHEMA)},
            {"role":"user","content":f"TITLE: {page_title}\nURL: {page_url}\nWIKITEXT:\n{page_text}"}
        ],
        response_format={"type":"json_schema","json_schema":{"name":"dcc_record","schema":SCHEMA,"strict":True}}
    )
    obj = json.loads(response.choices[0].message.content)
    # required enrichments
    now = iso_now()
    obj.setdefault("series","Dungeon Crawler Carl")
    obj.setdefault("provenance", {})
    obj["provenance"].setdefault("source_ref", page_url)
    obj["provenance"].setdefault("confidence", 0.7)
    obj.setdefault("metadata", {})
    obj["metadata"].setdefault("created_at", now)
    obj["metadata"].setdefault("updated_at", now)
    obj["metadata"].setdefault("version", "1.0.0")
    obj["metadata"].setdefault("license", "TBD")
    return obj

4.10 collector/validate.py
import os, json, glob
from jsonschema import Draft202012Validator

SCHEMA_PATH = os.path.join("schemas","dcc-record.schema.json")
SCHEMA = json.load(open(SCHEMA_PATH,"r",encoding="utf-8"))
validator = Draft202012Validator(SCHEMA)

def validate_dir(path: str) -> int:
    errors = 0
    for fp in glob.glob(os.path.join(path, "*.json")):
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        errs = sorted(validator.iter_errors(data), key=lambda e: e.path)
        if errs:
            print(f"❌ {fp}")
            for e in errs:
                loc = " -> ".join([str(p) for p in e.path]) or "(root)"
                print(f"  - {loc}: {e.message}")
            errors += 1
        else:
            print(f"✅ {fp}")
    return errors

if __name__ == "__main__":
    total = validate_dir(os.path.join("data","v1","items"))
    if total:
        raise SystemExit(1)
    print("✅ All records validate.")

4.11 collector/main.py
import os, re, json, hashlib
import orjson
import argparse
from tqdm import tqdm
from collector.config import DATA_DIR, RAW_DIR, CATEGORY_ROOT
from collector.mediawiki import list_category_titles, fetch_wikitext
from collector.extractor_openai import extract_record

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

def slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+","-", s).strip("-")
    return s[:120]

def file_hash(path: str) -> str:
    if not os.path.exists(path): return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="DCC items collector")
    ap.add_argument("--category", default=CATEGORY_ROOT, help="MediaWiki category to crawl (default: Items)")
    ap.add_argument("--limit", type=int, default=0, help="Max pages to process (0 = no limit)")
    ap.add_argument("--resume-from", default="", help="Title to resume from (exclusive)")
    args = ap.parse_args()

    titles = list_category_titles(args.category)
    if args.resume_from:
        if args.resume_from in titles:
            idx = titles.index(args.resume_from) + 1
            titles = titles[idx:]
    if args.limit > 0:
        titles = titles[:args.limit]

    written = skipped = failed = 0
    for title in tqdm(titles, desc="Collecting"):
        page_url = f"https://dungeon-crawler-carl.fandom.com/wiki/{title.replace(' ', '_')}"
        raw = fetch_wikitext(title)
        raw_path = os.path.join("data","v1","raw", f"{title}.wikitext.txt")
        old_hash = file_hash(raw_path)
        new_hash = file_hash(raw_path)
        # we just rewrote raw; if previous hash equals current, skip extraction
        if old_hash == new_hash:
            skipped += 1
            continue
        try:
            rec = extract_record(title, page_url, raw["wikitext"])
            rec["id"] = rec.get("id") or slug(rec.get("name") or title)
            rec["name"] = rec.get("name") or title
            out = os.path.join(DATA_DIR, f"{rec['id']}.json")
            with open(out, "wb") as f:
                f.write(orjson.dumps(rec, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS))
            written += 1
        except Exception as e:
            failed += 1
            os.makedirs(os.path.join("data","v1","tmp"), exist_ok=True)
            with open(os.path.join("data","v1","tmp","failures.txt"), "a", encoding="utf-8") as log:
                log.write(f"{title}\t{e}\n")

    print(f"Done. written={written} skipped={skipped} failed={failed}")

if __name__ == "__main__":
    main()

4.12 tools/build_index.py
import os, json, glob

ITEMS_DIR = os.path.join("data","v1","items")
INDEX_PATH = os.path.join("data","v1","index.json")

def main():
    index = []
    for fp in glob.glob(os.path.join(ITEMS_DIR, "*.json")):
        obj = json.load(open(fp, "r", encoding="utf-8"))
        index.append({
            "id": obj["id"],
            "name": obj["name"],
            "kind": obj.get("kind"),
            "subcategory": obj.get("subcategory"),
            "tags": obj.get("tags", []),
            "image": (obj.get("images") or [{}])[0].get("src"),
            "url": f"/data/v1/items/{obj['id']}.json"
        })
    index.sort(key=lambda x: x["name"].lower())
    json.dump({"total": len(index), "items": index}, open(INDEX_PATH,"w",encoding="utf-8"), indent=2)
    print(f"Built index with {len(index)} items → {INDEX_PATH}")

if __name__ == "__main__":
    main()

4.13 .github/workflows/ci.yml
name: CI
on:
  push:
  pull_request:
  workflow_dispatch:

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m venv .venv
      - run: . .venv/bin/activate && pip install -U pip && pip install -r collector/requirements.txt
      - name: Validate JSON
        run: . .venv/bin/activate && python collector/validate.py

4.14 README.md

Create a concise README with:

project overview,

setup instructions,

Make targets,

how to run crawl/validate/index,

notes on politeness/licensing,

Foundry notes (images, tokens),

sample curl to read /data/v1/index.json.

5) Behavior & CLI

python collector/main.py --category Items --limit 20

python collector/validate.py must pass with ✅ or fail the build.

python tools/build_index.py emits data/v1/index.json.

6) Acceptance criteria (must be true)

Repo matches the exact tree above.

schemas/dcc-record.schema.json exists and is valid JSON.

make setup && make crawl produces at least 3 item JSON files in data/v1/items/.

make validate prints ✅ for each produced file.

make index creates data/v1/index.json with total and items[].

The collector politely delays calls and retries on 5xx.

The extracted JSON includes provenance.source_ref with the wiki URL.

README explains setup (including .env) and usage.

7) After creation

Make an initial commit with message: feat: scaffold DCC archive, schema, collector, CI.

Print quickstart commands at the end of your run:

cp .env.example .env
make setup
make crawl
make validate
make index
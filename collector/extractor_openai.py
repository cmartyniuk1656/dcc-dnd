import datetime
import json
from typing import Any, Dict

from openai import OpenAI

from collector.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    SCHEMA_PATH,
)

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in environment")

client = (
    OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    if OPENAI_BASE_URL
    else OpenAI(api_key=OPENAI_API_KEY)
)
with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    SCHEMA = json.load(schema_file)

SYSTEM = """You are an information extractor. Return ONLY JSON that validates against the provided schema.
Rules:
- Do not invent facts.
- If a field is unknown, set null or use empty arrays/objects.
- Put short canonical text into rules_text (no long quotes).
- Set provenance.source_type='wiki'; extraction_method='llm'.
- Fill metadata timestamps in ISO 8601 UTC; version='1.0.0'; license='TBD'."""


def iso_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def extract_record(page_title: str, page_url: str, page_text: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Return JSON that conforms to this JSON Schema:"},
            {"role": "user", "content": json.dumps(SCHEMA)},
            {
                "role": "user",
                "content": f"TITLE: {page_title}\nURL: {page_url}\nWIKITEXT:\n{page_text}",
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "dcc_record", "schema": SCHEMA, "strict": True},
        },
    )
    payload = json.loads(response.choices[0].message.content)
    now = iso_now()
    payload.setdefault("series", "Dungeon Crawler Carl")
    payload.setdefault("provenance", {})
    payload["provenance"].setdefault("source_type", "wiki")
    payload["provenance"].setdefault("source_ref", page_url)
    payload["provenance"].setdefault("extraction_method", "llm")
    payload["provenance"].setdefault("confidence", 0.7)
    payload.setdefault("metadata", {})
    payload["metadata"].setdefault("created_at", now)
    payload["metadata"].setdefault("updated_at", now)
    payload["metadata"].setdefault("version", "1.0.0")
    payload["metadata"].setdefault("license", "TBD")
    return payload

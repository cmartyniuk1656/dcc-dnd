import datetime
import json
import re
from typing import Any, Dict
from urllib.parse import quote, unquote

from jsonschema import Draft202012Validator, ValidationError
from openai import OpenAI

from collector.config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    SCHEMA_PATH,
)
from collector.mediawiki import fetch_image_info

if not OPENAI_API_KEY:
    raise SystemExit("Missing OPENAI_API_KEY in environment")

client = (
    OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    if OPENAI_BASE_URL
    else OpenAI(api_key=OPENAI_API_KEY)
)
with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    SCHEMA = json.load(schema_file)
VALIDATOR = Draft202012Validator(SCHEMA)
TOP_LEVEL_KEYS = set(SCHEMA.get("properties", {}).keys())
IMAGE_INFO_CACHE: Dict[str, Dict[str, Any]] = {}


def normalize_kind_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


ALLOWED_KINDS = {
    normalize_kind_label(value): value
    for value in SCHEMA.get("properties", {}).get("kind", {}).get("enum", [])
}
KIND_ALIASES = {
    "item": "Item",
    "consumable": "Consumable",
    "consumables": "Consumable",
    "poison": "Consumable",
    "bandages": "Consumable",
    "potion": "Consumable",
    "vehicle": "Vehicle",
    "vehicles": "Vehicle",
    "hud": "Interface",
    "headsupdisplayhud": "Interface",
    "dungeonmechanic": "Mechanic",
    "mechanic": "Mechanic",
    "calligraphypen": "Tool",
    "pen": "Tool",
    "lootbox": "LootBox",
    "lootboxes": "LootBox",
    "craftingtable": "CraftingStation",
    "craftingworkbench": "CraftingStation",
    "workbench": "CraftingStation",
    "personalspaceitem": "CraftingStation",
    "craftingstation": "CraftingStation",
    "tgheecard": "Card",
    "card": "Card",
    "hat": "Apparel",
    "clothing": "Apparel",
    "clothingchest": "Apparel",
    "facecovering": "Apparel",
    "armor": "Armor",
    "shield": "Shield",
    "bracelet": "Accessory",
    "accessory": "Accessory",
    "arrow": "Projectile",
    "projectile": "Projectile",
    "weapon": "Weapon",
}
EFFECT_KEYS = {"name", "trigger", "chance", "area", "save", "modifiers", "targeting", "outcomes", "notes"}
TRIGGER_KEYS = {"event", "conditions"}
CONDITION_KEYS = {"left", "op", "right"}
MODIFIER_KEYS = {"stat", "op", "value", "stack_rule"}
OUTCOME_KEYS = {"weight", "prob", "result", "effects"}
ACTION_KEYS = {"action", "targets", "params"}
IMAGE_KEYS = {
    "type",
    "src",
    "srcset",
    "alt",
    "title",
    "width",
    "height",
    "mime",
    "transparent",
    "focal_point",
    "attribution",
    "hash_sha256",
    "cdn_key",
    "spoiler",
    "foundry",
}
SRCSET_KEYS = {"src", "descriptor"}
FOCAL_KEYS = {"x", "y"}
ATTR_KEYS = {"author", "source_url", "license"}
FOUNDRY_KEYS = {"token_border", "ring_color", "size_grid"}
PROVENANCE_KEYS = {"source_type", "source_ref", "extraction_method", "extraction_notes", "confidence"}
METADATA_KEYS = {"created_at", "updated_at", "version", "license"}
STAT_ALIASES = {
    "str": "STR",
    "strength": "STR",
    "int": "INT",
    "intelligence": "INT",
    "con": "CON",
    "constitution": "CON",
    "dex": "DEX",
    "dexterity": "DEX",
    "cha": "CHA",
    "charisma": "CHA",
    "wis": "WIS",
    "wisdom": "WIS",
}
STAT_ALIAS_PATTERNS = sorted(STAT_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
STAT_NAMES = {
    "STR": "strength",
    "INT": "intelligence",
    "CON": "constitution",
    "DEX": "dexterity",
    "CHA": "charisma",
    "WIS": "wisdom",
}

SYSTEM = """You are an information extractor. Return ONLY JSON that validates against the provided schema.
Rules:
- Do not invent facts.
- If a field is unknown, set null or use empty arrays/objects.
- Put short canonical text into rules_text (no long quotes).
- Set provenance.source_type='wiki'; extraction_method='llm'.
- Fill metadata timestamps in ISO 8601 UTC; version='1.0.0'; license='TBD'."""


def iso_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:120] or "item"


def strip_wikitext(text: str) -> str:
    cleaned = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    cleaned = re.sub(r"<ref[^>]*>.*?</ref>", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\{\{[^{}]*\}\}", " ", cleaned)
    cleaned = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", cleaned)
    cleaned = re.sub(r"'{2,}", "", cleaned)
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_intro_description(wikitext: str) -> str | None:
    lines = wikitext.splitlines()
    buffer: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buffer:
                break
            continue
        if stripped.startswith("=="):
            break
        if stripped.startswith("{{"):
            continue
        if stripped.startswith("[[Category"):
            continue
        buffer.append(stripped)
    if not buffer:
        return None
    text = " ".join(buffer)
    result = strip_wikitext(text)
    return result or None


def extract_ai_description(wikitext: str) -> str | None:
    match = re.search(r"==\s*AI Description\s*==(?P<body>.*?)(?:\n==|$)", wikitext, re.S | re.I)
    if not match:
        return None
    body = match.group("body")
    body = re.sub(r"</?blockquote>", " ", body, flags=re.I)
    result = strip_wikitext(body)
    return result or None


def extract_type_tokens(wikitext: str) -> list[str]:
    match = re.search(r"^\|\s*type\s*=\s*(?P<value>.+)$", wikitext, re.M | re.I)
    if not match:
        return []
    raw_value = match.group("value")
    parts = re.split(r"[,/]", raw_value)
    tokens = []
    for part in parts:
        cleaned = strip_wikitext(part).strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def ensure_image_url(src: str) -> str:
    if not isinstance(src, str):
        return src
    candidate = src.strip()
    if not candidate:
        return candidate
    if candidate.startswith(("http://", "https://")):
        return candidate
    filename = candidate
    if filename.lower().startswith("file:"):
        filename = filename[5:]
    filename = filename.replace(" ", "_")
    safe_filename = quote(filename, safe=":_-().'")
    return f"https://dungeon-crawler-carl.fandom.com/wiki/File:{safe_filename}"


def resolve_image_entry(src: str, fallback_files: list[str] | None = None) -> Dict[str, Any]:
    if not src:
        return {"src": src}
    candidate = src.strip()
    file_fragment = None
    if candidate.startswith("http"):
        if "static.wikia" in candidate:
            if "/revision/" in candidate:
                return {"src": candidate}
            file_fragment = candidate.split("/")[-1].split("?", 1)[0]
        else:
            parts = candidate.split("/File:", 1)
            if len(parts) == 2:
                file_fragment = parts[1]
    else:
        file_fragment = candidate
    if not file_fragment and fallback_files:
        for item in fallback_files:
            info = resolve_image_entry(f"File:{item}", None)
            if info.get("src") and info["src"].startswith("http"):
                return info
        return {"src": candidate}
    if not file_fragment:
        return {"src": candidate}
    file_fragment = unquote(file_fragment)
    file_fragment = file_fragment.split("?", 1)[0]
    key = file_fragment.lower()
    info = IMAGE_INFO_CACHE.get(key)
    if info is None:
        info = fetch_image_info(file_fragment)
        IMAGE_INFO_CACHE[key] = info or {}
    if not info:
        return {"src": candidate}
    result: Dict[str, Any] = {"src": info.get("url") or candidate}
    if info.get("mime"):
        result.setdefault("mime", info.get("mime"))
    if info.get("width"):
        result.setdefault("width", info.get("width"))
    if info.get("height"):
        result.setdefault("height", info.get("height"))
    if info.get("sha1"):
        result.setdefault("hash_sha1", info.get("sha1"))
    return result


def extract_file_titles(wikitext: str) -> list[str]:
    if not wikitext:
        return []
    matches = re.findall(r'\[\[File:([^|\]]+)', wikitext, flags=re.I)
    matches += re.findall(r'\|image\d*\s*=\s*([^|\n]+)', wikitext, flags=re.I)
    return [match.strip() for match in matches if match.strip()]


def normalize_effect_name(value: str) -> str:
    return strip_wikitext(value or "").strip().lower()


def extract_stat_bonuses_from_wikitext(wikitext: str) -> dict[str, float | int]:
    match = re.search(
        r"\|\s*effects\s*=\s*(?P<body>.*?)(?:\n\|\s*\w+\s*=|\n\}\}|$)",
        wikitext,
        re.S | re.I,
    )
    if not match:
        return {}
    body = match.group("body")
    body = body.split("'''UPGRADED'''")[0]
    bonuses: dict[str, float | int] = {}
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("*"):
            continue
        cleaned_text = strip_wikitext(stripped.lstrip("* ").strip())
        stat_match = re.match(
            r"([+-]?\d+(?:\.\d+)?)\s*(%?)\s*(?:to\s+)?([A-Za-z]+)",
            cleaned_text,
        )
        if not stat_match or stat_match.group(2) == "%":
            continue
        stat_token = stat_match.group(3).lower()
        stat_key = STAT_ALIASES.get(stat_token) or STAT_ALIASES.get(stat_token.rstrip("s"))
        if not stat_key or stat_key in bonuses:
            continue
        value = float(stat_match.group(1))
        if value.is_integer():
            bonuses[stat_key] = int(value)
        else:
            bonuses[stat_key] = value
    return bonuses


def extract_effect_details_from_wikitext(wikitext: str) -> dict[str, dict]:
    details: dict[str, dict] = {}
    for raw_line in wikitext.splitlines():
        line = raw_line.strip()
        match = re.match(r"'''([^:]+):'''(.*)", line)
        if not match:
            if not line.startswith("*"):
                continue
            bullet = strip_wikitext(line.lstrip("* ").strip())
            if not bullet:
                continue
            name = bullet
            body = bullet
        else:
            name = strip_wikitext(match.group(1)).strip()
            body = strip_wikitext(match.group(2)).strip()
        if not name or not body:
            continue
        key = normalize_effect_name(name)
        body_lower = body.lower()
        chance = None
        if "chance" in body_lower:
            chance_match = re.search(r"(\d+(?:\.\d+)?)\s*%", body)
            if chance_match:
                chance = float(chance_match.group(1))
                if chance > 1:
                    chance /= 100.0
        modifiers: list[dict[str, Any]] = []
        seen_stats: set[str] = set()
        for stat_match in re.finditer(
            r"([+-]?\d+(?:\.\d+)?)\s*(%?)\s*(?:to\s+)?([A-Za-z]+)",
            body,
        ):
            percent_flag = stat_match.group(2) == "%"
            value = float(stat_match.group(1))
            stat_token = stat_match.group(3).lower()
            stat_key = STAT_ALIASES.get(stat_token) or STAT_ALIASES.get(stat_token.rstrip("s"))
            if not stat_key or stat_key in seen_stats:
                continue
            seen_stats.add(stat_key)
            stack_rule = None
            if "temporary" in body_lower or "temporarily" in body_lower:
                stack_rule = "temporary"
            if percent_flag:
                modifiers.append(
                    {
                        "stat": stat_key,
                        "op": "mul",
                        "value": 1 + (value / 100.0),
                        "stack_rule": stack_rule,
                    }
                )
            else:
                numeric_value: float | int = int(value) if value.is_integer() else value
                modifiers.append(
                    {
                        "stat": stat_key,
                        "op": "add",
                        "value": numeric_value,
                        "stack_rule": stack_rule,
                    }
                )
        notes = None
        if "temporary" in body_lower or "permanent" in body_lower:
            notes = body
        details[key] = {
            "chance": chance,
            "modifiers": modifiers,
            "notes": notes,
        }
    return details


def extract_record(page_title: str, page_url: str, page_text: str) -> Dict[str, Any]:
    file_candidates = extract_file_titles(page_text)
    last_error: ValidationError | None = None
    for _ in range(3):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": (
                        "Extract the structured record for the following page. "
                        "Return only JSON that conforms to the agreed schema.\n"
                        f"TITLE: {page_title}\n"
                        f"URL: {page_url}\n"
                        "WIKITEXT:\n"
                        f"{page_text}"
                    ),
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "dcc_record", "schema": SCHEMA, "strict": False},
            },
        )
        payload = json.loads(response.choices[0].message.content)
        if "id" not in payload and isinstance(payload.get("properties"), dict):
            schema_props = payload.pop("properties")
            if isinstance(schema_props, dict):
                for key, value in schema_props.items():
                    if key in TOP_LEVEL_KEYS and key not in payload:
                        payload[key] = value
        payload.pop("type", None)
        payload = {
            key: value for key, value in payload.items() if key in TOP_LEVEL_KEYS
        }
        now = iso_now()
        payload.setdefault("series", "Dungeon Crawler Carl")
        provenance_raw = payload.get("provenance") or {}
        provenance = {
            key: provenance_raw.get(key) for key in PROVENANCE_KEYS if key in provenance_raw
        }
        provenance.setdefault("source_type", "wiki")
        provenance.setdefault("source_ref", page_url)
        provenance.setdefault("extraction_method", "llm")
        confidence = provenance.get("confidence")
        if isinstance(confidence, (int, float)):
            provenance["confidence"] = max(0.0, min(1.0, float(confidence)))
        else:
            provenance["confidence"] = 0.7
        payload["provenance"] = provenance

        metadata_raw = payload.get("metadata") or {}
        metadata = {key: metadata_raw.get(key) for key in METADATA_KEYS if key in metadata_raw}
        metadata.setdefault("created_at", now)
        metadata.setdefault("updated_at", now)
        metadata.setdefault("version", "1.0.0")
        metadata.setdefault("license", "TBD")
        payload["metadata"] = metadata

        payload.pop("$id", None)
        payload.pop("title", None)

        type_tokens = extract_type_tokens(page_text)
        if type_tokens:
            payload["kind_detail"] = type_tokens
        elif isinstance(payload.get("kind_detail"), list):
            cleaned_detail = [
                strip_wikitext(str(item)).strip()
                for item in payload["kind_detail"]
                if isinstance(item, str)
            ]
            payload["kind_detail"] = [item for item in cleaned_detail if item]
        else:
            payload["kind_detail"] = []

        description_value = payload.get("description")
        if isinstance(description_value, str):
            description_value = description_value.strip()
        payload["description"] = description_value or extract_intro_description(page_text)

        ai_value = payload.get("ai_description")
        if isinstance(ai_value, str):
            ai_value = ai_value.strip()
        payload["ai_description"] = ai_value or extract_ai_description(page_text)

        for key in ("aliases", "activation", "enchantments", "images", "effects", "tags", "kind_detail"):
            if not isinstance(payload.get(key), list):
                payload[key] = []
        if payload["kind_detail"]:
            seen_tokens: set[str] = set()
            deduped_tokens: list[str] = []
            for token in payload["kind_detail"]:
                if not isinstance(token, str):
                    continue
                token = token.strip()
                if not token:
                    continue
                if token not in seen_tokens:
                    seen_tokens.add(token)
                    deduped_tokens.append(token)
            payload["kind_detail"] = deduped_tokens
        if payload.get("rules_text") is not None and not isinstance(payload["rules_text"], str):
            payload["rules_text"] = None

        name_value = payload.get("name")
        if not isinstance(name_value, str) or not name_value.strip():
            name_value = page_title
        payload["name"] = name_value
        raw_id = payload.get("id") if isinstance(payload.get("id"), str) else ""
        payload["id"] = slugify(raw_id or name_value)
        candidate_labels = []
        if payload["kind_detail"]:
            candidate_labels.extend(payload["kind_detail"])
        if isinstance(payload.get("kind"), str):
            candidate_labels.append(payload["kind"])
        candidate_labels.extend(
            tag for tag in payload.get("tags", []) if isinstance(tag, str)
        )
        canonical_kind = "Other"
        for label in candidate_labels:
            norm = normalize_kind_label(label)
            if not norm:
                continue
            if norm in ALLOWED_KINDS:
                canonical_kind = ALLOWED_KINDS[norm]
                break
            if norm in KIND_ALIASES:
                alias_kind = KIND_ALIASES[norm]
                alias_norm = normalize_kind_label(alias_kind)
                canonical_kind = ALLOWED_KINDS.get(alias_norm, alias_kind)
                if canonical_kind:
                    break
        payload["kind"] = canonical_kind
        series_value = payload.get("series")
        if not isinstance(series_value, str) or not series_value.strip():
            series_value = "Dungeon Crawler Carl"
        payload["series"] = series_value

        form = payload.get("form")
        if isinstance(form, dict) and "conjured" in form:
            conjured = form.get("conjured")
            if isinstance(conjured, str):
                form["conjured"] = conjured.strip().lower() in {"true", "yes", "1"}
            elif isinstance(conjured, (int, float)):
                form["conjured"] = bool(conjured)
            elif conjured is None:
                form["conjured"] = False

        allowed_image_types = {"icon", "portrait", "token", "tile", "splash", "other"}
        cleaned_images = []
        for raw_image in payload.get("images") or []:
            if not isinstance(raw_image, dict):
                continue
            image = {key: raw_image.get(key) for key in IMAGE_KEYS if key in raw_image}
            if image.get("type") not in allowed_image_types:
                image["type"] = "other"
            src_value = image.get("src")
            if not isinstance(src_value, str) or not src_value.strip():
                continue
            image["src"] = ensure_image_url(src_value)
            resolved_info = resolve_image_entry(image["src"], file_candidates)
            image["src"] = resolved_info.get("src", image["src"])
            if resolved_info.get("mime") and not image.get("mime"):
                image["mime"] = resolved_info.get("mime")
            if resolved_info.get("width") and not image.get("width"):
                image["width"] = resolved_info.get("width")
            if resolved_info.get("height") and not image.get("height"):
                image["height"] = resolved_info.get("height")
            srcset = []
            for entry in image.get("srcset") or []:
                if isinstance(entry, dict):
                    cleaned_entry = {
                        key: entry.get(key) for key in SRCSET_KEYS if key in entry
                    }
                    if "src" in cleaned_entry and isinstance(cleaned_entry["src"], str):
                        cleaned_entry["src"] = ensure_image_url(cleaned_entry["src"])
                        resolved_entry = resolve_image_entry(cleaned_entry["src"], file_candidates)
                        cleaned_entry["src"] = resolved_entry.get("src", cleaned_entry["src"])
                    srcset.append(cleaned_entry)
            image["srcset"] = srcset
            focal_point = image.get("focal_point")
            if isinstance(focal_point, dict):
                focal_point = {
                    key: focal_point.get(key) for key in FOCAL_KEYS if key in focal_point
                }
            else:
                focal_point = None
            image["focal_point"] = focal_point or None
            attribution = image.get("attribution")
            if isinstance(attribution, dict):
                attribution = {
                    key: attribution.get(key) for key in ATTR_KEYS if key in attribution
                }
            else:
                attribution = None
            image["attribution"] = attribution or None
            foundry = image.get("foundry")
            if isinstance(foundry, dict):
                foundry = {
                    key: foundry.get(key) for key in FOUNDRY_KEYS if key in foundry
                }
            else:
                foundry = None
            image["foundry"] = foundry or None
            cleaned_images.append(image)
        payload["images"] = cleaned_images

        stat_bonus_lookup: dict[str, float | int] = {}
        for enchantment in payload.get("enchantments") or []:
            if not isinstance(enchantment, dict):
                continue
            enchant_name = enchantment.get("name")
            if not isinstance(enchant_name, str):
                continue
            params = enchantment.get("parameters") or {}
            if not isinstance(params, dict):
                continue
            raw_bonus = None
            for key in ("bonus", "value", "amount", "modifier"):
                if key in params:
                    raw_bonus = params[key]
                    break
            if raw_bonus is None:
                continue
            try:
                if isinstance(raw_bonus, str):
                    match_bonus = re.search(r"-?\d+(?:\.\d+)?", raw_bonus)
                    if not match_bonus:
                        continue
                    bonus_value = float(match_bonus.group(0))
                else:
                    bonus_value = float(raw_bonus)
            except (TypeError, ValueError):
                continue
            stat_key = STAT_ALIASES.get(enchant_name.lower()) or STAT_ALIASES.get(
                enchant_name.lower().rstrip("s")
            )
            if not stat_key or stat_key in stat_bonus_lookup:
                continue
            if bonus_value.is_integer():
                stat_bonus_lookup[stat_key] = int(bonus_value)
            else:
                stat_bonus_lookup[stat_key] = bonus_value

        for stat_key, bonus_value in extract_stat_bonuses_from_wikitext(page_text).items():
            stat_bonus_lookup.setdefault(stat_key, bonus_value)

        effect_detail_lookup = extract_effect_details_from_wikitext(page_text)

        effects = []
        stats_present: set[str] = set()
        for raw_effect in payload.get("effects") or []:
            if not isinstance(raw_effect, dict):
                continue
            effect = {
                key: raw_effect.get(key) for key in EFFECT_KEYS if key in raw_effect
            }
            trigger = effect.get("trigger")
            if not isinstance(trigger, dict):
                trigger = {}
            trigger = {
                key: trigger.get(key) for key in TRIGGER_KEYS if key in trigger
            }
            conditions = trigger.get("conditions") or []
            cleaned_conditions = []
            for condition in conditions:
                if isinstance(condition, dict):
                    cleaned = {
                        key: condition.get(key)
                        for key in CONDITION_KEYS
                        if key in condition
                    }
                    cleaned_conditions.append(cleaned)
            trigger["conditions"] = cleaned_conditions
            event = trigger.get("event")
            if not isinstance(event, str) or not event.strip():
                trigger["event"] = "unspecified"
            effect["trigger"] = trigger

            modifiers = []
            for modifier in raw_effect.get("modifiers") or []:
                if isinstance(modifier, dict):
                    cleaned_modifier = {
                        key: modifier.get(key)
                        for key in MODIFIER_KEYS
                        if key in modifier
                    }
                    if cleaned_modifier:
                        stat_label = cleaned_modifier.get("stat")
                        if isinstance(stat_label, str):
                            normalized_stat = STAT_ALIASES.get(stat_label.lower()) or STAT_ALIASES.get(
                                stat_label.lower().rstrip("s")
                            )
                            if normalized_stat:
                                cleaned_modifier["stat"] = normalized_stat
                        value_label = cleaned_modifier.get("value")
                        if isinstance(value_label, str):
                            value_match = re.search(r"-?\d+(?:\.\d+)?", value_label)
                            if value_match:
                                numeric_value = float(value_match.group(0))
                                if numeric_value.is_integer():
                                    cleaned_modifier["value"] = int(numeric_value)
                                else:
                                    cleaned_modifier["value"] = numeric_value
                        modifiers.append(cleaned_modifier)
            effect["modifiers"] = modifiers

            targeting = effect.get("targeting")
            if isinstance(targeting, dict):
                effect["targeting"] = {
                    key: targeting.get(key) for key in ("requires_los", "max_targets", "target_filter") if key in targeting
                }

            save = effect.get("save")
            if isinstance(save, dict):
                effect["save"] = {
                    key: save.get(key) for key in ("ability", "dc", "on_success") if key in save
                }

            area = effect.get("area")
            if isinstance(area, dict):
                effect["area"] = {
                    key: area.get(key) for key in ("shape", "size", "origin") if key in area
                }

            chance_value = effect.get("chance")
            parsed_chance: float | None = None
            if isinstance(chance_value, (int, float)):
                parsed_chance = float(chance_value)
            elif isinstance(chance_value, str):
                match = re.search(r"(\d+(?:\.\d+)?)", chance_value)
                if match:
                    parsed_chance = float(match.group(1))
                if parsed_chance is not None and "%" in chance_value:
                    parsed_chance /= 100.0
            if parsed_chance is not None:
                if parsed_chance > 1 and parsed_chance <= 100:
                    parsed_chance /= 100.0
                effect["chance"] = max(0.0, min(1.0, parsed_chance))
            else:
                effect["chance"] = None

            outcomes = []
            for outcome in raw_effect.get("outcomes") or []:
                if not isinstance(outcome, dict):
                    continue
                cleaned_outcome = {
                    key: outcome.get(key)
                    for key in OUTCOME_KEYS
                    if key in outcome
                }
                actions = []
                for action in outcome.get("effects") or []:
                    if isinstance(action, dict):
                        cleaned_action = {
                            key: action.get(key)
                            for key in ACTION_KEYS
                            if key in action
                        }
                        if cleaned_action:
                            actions.append(cleaned_action)
                cleaned_outcome["effects"] = actions
                if "result" in cleaned_outcome and isinstance(cleaned_outcome["result"], str):
                    outcomes.append(cleaned_outcome)
            effect["outcomes"] = outcomes

            notes = effect.get("notes")
            if notes is not None and not isinstance(notes, str):
                effect["notes"] = None

            name_field = effect.get("name")
            if not effect["modifiers"]:
                if isinstance(name_field, str):
                    stat_match = re.match(
                        r"^\s*([+-]?\d+(?:\.\d+)?)\s*(%?)\s*(?:to\s+)?([A-Za-z]+)",
                        name_field,
                    )
                    if stat_match:
                        numeric_value = float(stat_match.group(1))
                        percent_flag = stat_match.group(2) == "%"
                        stat_token = stat_match.group(3).lower()
                        stat_key = STAT_ALIASES.get(stat_token) or STAT_ALIASES.get(
                            stat_token.rstrip("s")
                        )
                        if stat_key:
                            if percent_flag:
                                effect["modifiers"] = [
                                    {
                                        "stat": stat_key,
                                        "op": "mul",
                                        "value": 1 + (numeric_value / 100.0),
                                        "stack_rule": None,
                                    }
                                ]
                            else:
                                if numeric_value.is_integer():
                                    value: float | int = int(numeric_value)
                                else:
                                    value = numeric_value
                                effect["modifiers"] = [
                                    {
                                        "stat": stat_key,
                                        "op": "add",
                                        "value": value,
                                        "stack_rule": None,
                                    }
                                ]
                if not effect["modifiers"] and isinstance(name_field, str):
                    lowered_name = name_field.lower()
                    for alias, stat_key in STAT_ALIAS_PATTERNS:
                        if re.search(rf"\b{re.escape(alias)}\b", lowered_name):
                            bonus = stat_bonus_lookup.get(stat_key)
                            if bonus is None:
                                continue
                            if isinstance(bonus, float) and bonus.is_integer():
                                bonus_value: float | int = int(bonus)
                            else:
                                bonus_value = bonus
                            effect["modifiers"] = [
                                {
                                    "stat": stat_key,
                                    "op": "add",
                                    "value": bonus_value,
                                    "stack_rule": None,
                                }
                            ]
                            break

            detail = None
            if isinstance(name_field, str):
                normalized_name = normalize_effect_name(name_field)
                detail = effect_detail_lookup.get(normalized_name)
                if not detail:
                    for candidate in effect_detail_lookup.values():
                        mod_stats = [
                            mod.get("stat")
                            for mod in candidate.get("modifiers", [])
                            if isinstance(mod, dict)
                        ]
                        found = False
                        for stat_label in mod_stats:
                            if not isinstance(stat_label, str):
                                continue
                            stat_lower = STAT_NAMES.get(stat_label, stat_label.lower())
                            if stat_lower in normalized_name or stat_label.lower() in normalized_name:
                                detail = candidate
                                found = True
                                break
                        if found:
                            break
            if detail:
                if detail["modifiers"]:
                    effect["modifiers"] = [
                        {
                            "stat": mod["stat"],
                            "op": mod["op"],
                            "value": mod["value"],
                            "stack_rule": mod.get("stack_rule"),
                        }
        for mod in detail["modifiers"]
    ]
                if effect.get("chance") is None and detail["chance"] is not None:
                    effect["chance"] = detail["chance"]
                if detail["notes"] and not effect.get("notes"):
                    effect["notes"] = detail["notes"]

            for modifier in effect.get("modifiers", []):
                stat_label = modifier.get("stat")
                if isinstance(stat_label, str):
                    stats_present.add(stat_label)

            effects.append(effect)
        missing_stats = [stat for stat in stat_bonus_lookup if stat not in stats_present]
        for stat in missing_stats:
            value = stat_bonus_lookup[stat]
            if isinstance(value, float) and value.is_integer():
                numeric_value: float | int = int(value)
            else:
                numeric_value = value
            synthetic_effect = {
                "name": f"+{numeric_value} {stat}",
                "trigger": {"event": "unspecified", "conditions": []},
                "chance": None,
                "area": None,
                "save": None,
                "modifiers": [
                    {"stat": stat, "op": "add", "value": numeric_value, "stack_rule": None}
                ],
                "targeting": None,
                "outcomes": [],
                "notes": None,
            }
            effects.append(synthetic_effect)
            stats_present.add(stat)
        payload["effects"] = effects

        physical = payload.get("physical")
        if isinstance(physical, dict):
            weight = physical.get("weight_kg")
            if weight is not None and not isinstance(weight, (int, float)):
                physical["weight_kg"] = None
            dimensions = physical.get("dimensions_cm")
            if isinstance(dimensions, dict):
                cleaned_dimensions: dict[str, float] = {}
                for axis in ("w", "h", "d"):
                    value = dimensions.get(axis)
                    if isinstance(value, (int, float)):
                        cleaned_dimensions[axis] = float(value)
                if cleaned_dimensions:
                    physical["dimensions_cm"] = cleaned_dimensions
                else:
                    physical["dimensions_cm"] = None
            durability = physical.get("durability")
            if isinstance(durability, dict):
                for key in ("max", "current"):
                    item = durability.get(key)
                    if item is not None and not isinstance(item, (int, float)):
                        durability[key] = None


        try:
            VALIDATOR.validate(payload)
            return payload
        except ValidationError as err:
            last_error = err
    if last_error:
        raise last_error
    raise RuntimeError("Failed to extract record for unknown reasons")

#!/usr/bin/env python3
import glob
import json
import os
import re
from collections import Counter, defaultdict

from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(ROOT, "schemas", "dcc-record.schema.json"), encoding="utf-8") as schema_file:
    SCHEMA = json.load(schema_file)
ITEMS_DIR = os.path.join(ROOT, "data", "v1", "items")

validator = Draft202012Validator(SCHEMA)

dice_re = re.compile(r"^\s*\d+d\d+([+\-]\d+)?\s*$", re.I)

def soft_checks(obj):
    issues = []
    # required basics
    for k in ("id","name","kind","provenance","metadata"):
        if k not in obj: issues.append(f"missing top-level '{k}'")

    # unique id shape
    if "id" in obj and not re.match(r"^[a-z0-9\-]{3,}$", obj["id"]):
        issues.append("id should be a lowercase slug [a-z0-9-], len>=3")

    # outcomes probability sanity
    for i, eff in enumerate(obj.get("effects", [])):
        outs = eff.get("outcomes") or []
        probs = [o.get("prob") for o in outs if o.get("prob") is not None]
        if probs:
            s = sum(probs)
            if abs(s - 1.0) > 1e-6:
                issues.append(f"effects[{i}].outcomes prob sum = {s:.6f} (should be 1.0)")
        # chance bounds
        ch = eff.get("chance")
        if ch is not None and not (0.0 <= ch <= 1.0):
            issues.append(f"effects[{i}].chance out of [0,1]: {ch}")

        # dice strings in nested atomic actions (optional heuristic)
        for j, o in enumerate(outs):
            for k, ae in enumerate(o.get("effects", []) or []):
                params = ae.get("params") or {}
                for key in ("heal","damage","dice"):
                    if key in params and isinstance(params[key], str):
                        if not dice_re.match(params[key]):
                            issues.append(f"effects[{i}].outcomes[{j}].effects[{k}].params.{key} not dice-like: {params[key]}")

    # provenance basics
    prov = obj.get("provenance", {})
    if not prov.get("source_ref"): issues.append("provenance.source_ref missing")

    # images alt text (accessibility)
    imgs = obj.get("images") or []
    for idx, im in enumerate(imgs):
        if im.get("type") in ("icon","token") and not im.get("alt"):
            issues.append(f"images[{idx}] missing alt")

    return issues

def main():
    files = sorted(glob.glob(os.path.join(ITEMS_DIR, "*.json")))
    id_counter = Counter()
    name_counter = Counter()
    hard_errs = 0

    per_file = defaultdict(list)

    for fp in files:
        with open(fp, encoding="utf-8") as handle:
            data = json.load(handle)
        id_counter[data.get("id","")] += 1
        name_counter[data.get("name","")] += 1

        # schema validation
        errs = list(validator.iter_errors(data))
        if errs:
            hard_errs += 1
            for e in errs:
                per_file[fp].append(f"SCHEMA: {e.message} at path {list(e.path)}")

        # soft checks
        issues = soft_checks(data)
        if issues:

            for m in issues:
                per_file[fp].append(f"CHECK: {m}")

    # duplicates
    dups = [item_id for item_id, count in id_counter.items() if count > 1]
    if dups:
        print("ERROR duplicate IDs:", dups)
    dupsn = [name for name, count in name_counter.items() if count > 1 and name]
    if dupsn:
        print("WARN duplicate names:", dupsn[:10], "(+ more)" if len(dupsn)>10 else "")

    # print report
    for fp, msgs in per_file.items():
        if msgs:
            print(f"\n{fp}")
            for m in msgs:
                print("  -", m)

        soft_files = sum(1 for messages in per_file.values() if messages)
    print(f"\nFiles: {len(files)} | schema-bad: {hard_errs} | files-with-issues: {soft_files}")
    if hard_errs:
        raise SystemExit(1)

if __name__ == "__main__":
    main()





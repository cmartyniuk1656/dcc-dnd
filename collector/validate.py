import glob
import json
import os

from jsonschema import Draft202012Validator

SCHEMA_PATH = os.path.join("schemas", "dcc-record.schema.json")
with open(SCHEMA_PATH, "r", encoding="utf-8") as schema_file:
    SCHEMA = json.load(schema_file)
validator = Draft202012Validator(SCHEMA)


def validate_dir(path: str) -> int:
    errors = 0
    for fp in glob.glob(os.path.join(path, "*.json")):
        with open(fp, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        issues = sorted(validator.iter_errors(data), key=lambda err: err.path)
        if issues:
            print(f"[FAIL] {fp}")
            for err in issues:
                location = " -> ".join([str(part) for part in err.path]) or "(root)"
                print(f"  - {location}: {err.message}")
            errors += 1
        else:
            print(f"[OK] {fp}")
    return errors


if __name__ == "__main__":
    total = validate_dir(os.path.join("data", "v1", "items"))
    if total:
        raise SystemExit(1)
    print("[OK] All records validate.")

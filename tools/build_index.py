import glob
import json
import os

ITEMS_DIR = os.path.join("data", "v1", "items")
INDEX_PATH = os.path.join("data", "v1", "index.json")


def main() -> None:
    index = []
    for fp in glob.glob(os.path.join(ITEMS_DIR, "*.json")):
        with open(fp, "r", encoding="utf-8") as handle:
            obj = json.load(handle)
        index.append(
            {
                "id": obj["id"],
                "name": obj["name"],
                "kind": obj.get("kind"),
                "subcategory": obj.get("subcategory"),
                "tags": obj.get("tags", []),
                "image": (obj.get("images") or [{}])[0].get("src"),
                "url": f"/data/v1/items/{obj['id']}.json",
            }
        )
    index.sort(key=lambda record: record["name"].lower())
    with open(INDEX_PATH, "w", encoding="utf-8") as handle:
        json.dump({"total": len(index), "items": index}, handle, indent=2)
    print(f"Built index with {len(index)} items -> {INDEX_PATH}")


if __name__ == "__main__":
    main()

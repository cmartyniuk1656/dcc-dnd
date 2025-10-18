import json
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collector.config import DATA_DIR, RAW_DIR
from collector.utils import sanitize_title_for_fs
from collector.extractor_openai import resolve_image_entry, extract_file_titles

def load_fallback_files(provenance_ref: str, item_name: str) -> list[str]:
    title = None
    if provenance_ref and "/wiki/" in provenance_ref:
        title = provenance_ref.split("/wiki/", 1)[1]
        title = title.split("#", 1)[0]
        title = unquote(title)
        title = title.replace("_", " ")
    if not title:
        title = item_name
    raw_path = Path(RAW_DIR) / f"{sanitize_title_for_fs(title)}.wikitext.txt"
    if not raw_path.exists():
        return []
    return extract_file_titles(raw_path.read_text(encoding="utf-8"))

def needs_refresh(src: str) -> bool:
    if not src:
        return False
    src = src.strip()
    if "static.wikia" in src and "/revision/" in src:
        return False
    return True

def main() -> None:
    items_dir = Path(DATA_DIR)
    changed_files = 0
    for path in sorted(items_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        images = data.get("images") or []
        if not images:
            continue
        provenance = data.get("provenance", {})
        fallback_files = load_fallback_files(provenance.get("source_ref", ""), data.get("name") or "")
        file_candidates = fallback_files
        updated = False
        for image in images:
            if image.pop("hash_sha1", None) is not None:
                updated = True
            src = image.get("src") or ""
            if not needs_refresh(src):
                continue
            info = resolve_image_entry(src, file_candidates)
            new_src = info.get("src", src)
            if new_src != src:
                image["src"] = new_src
                updated = True
            for key in ("mime", "width", "height"):
                if key in info and info[key] is not None and key not in image:
                    image[key] = info[key]
        if updated:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed_files += 1
    print(f"Updated images in {changed_files} item(s)")

if __name__ == "__main__":
    main()

import argparse
import hashlib
import os
import re

import orjson
from tqdm import tqdm

from collector.config import CATEGORY_ROOT, DATA_DIR, RAW_DIR
from collector.extractor_openai import extract_record
from collector.mediawiki import fetch_wikitext, list_category_titles

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:120]


def file_hash(path: str) -> str:
    if not os.path.exists(path):
        return ""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="DCC items collector")
    parser.add_argument(
        "--category",
        default=CATEGORY_ROOT,
        help="MediaWiki category to crawl (default: Items)",
    )
    parser.add_argument(
        "--limit", type=int, default=0, help="Max pages to process (0 = no limit)"
    )
    parser.add_argument("--resume-from", default="", help="Title to resume from")
    args = parser.parse_args()

    titles = list_category_titles(args.category)
    if args.resume_from and args.resume_from in titles:
        start_index = titles.index(args.resume_from) + 1
        titles = titles[start_index:]
    if args.limit > 0:
        titles = titles[: args.limit]

    written = skipped = failed = 0
    for title in tqdm(titles, desc="Collecting"):
        page_url = f"https://dungeon-crawler-carl.fandom.com/wiki/{title.replace(' ', '_')}"
        raw_path = os.path.join(RAW_DIR, f"{title}.wikitext.txt")
        previous_hash = file_hash(raw_path)
        raw = fetch_wikitext(title)
        current_hash = file_hash(raw_path)
        if previous_hash and previous_hash == current_hash:
            skipped += 1
            continue
        try:
            record = extract_record(title, page_url, raw["wikitext"])
            record["id"] = record.get("id") or slug(record.get("name") or title)
            record["name"] = record.get("name") or title
            output_path = os.path.join(DATA_DIR, f"{record['id']}.json")
            with open(output_path, "wb") as handle:
                handle.write(
                    orjson.dumps(
                        record, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
                    )
                )
            written += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            os.makedirs(os.path.join("data", "v1", "tmp"), exist_ok=True)
            with open(
                os.path.join("data", "v1", "tmp", "failures.txt"),
                "a",
                encoding="utf-8",
            ) as log:
                log.write(f"{title}\t{exc}\n")

    print(f"Done. written={written} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()

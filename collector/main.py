import argparse
import hashlib
import os
import re

import orjson
from tqdm import tqdm

from collector.config import CATEGORY_ROOT, DATA_DIR, RAW_DIR
from collector.extractor_openai import extract_record
from collector.mediawiki import fetch_wikitext, list_category_titles
from collector.utils import sanitize_title_for_fs

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)


def slug(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if not value:
        value = "item"
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
    parser.add_argument(
        "--title",
        dest="titles",
        action="append",
        help="Specific page title to process (can be repeated)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of titles to skip after applying resume-from (ignored when --title is used)",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Print the number of titles that would be processed and exit",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Report titles that would be new or updated without extracting",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if cached wikitext has not changed",
    )
    args = parser.parse_args()

    if args.titles:
        titles = args.titles
    else:
        titles = list_category_titles(args.category)
        if args.resume_from and args.resume_from in titles:
            start_index = titles.index(args.resume_from) + 1
            titles = titles[start_index:]
        if args.offset > 0:
            titles = titles[args.offset:]
        if args.limit > 0:
            titles = titles[: args.limit]

    if args.count_only:
        print(f"Titles scheduled: {len(titles)}")
        return

    written = skipped = failed = 0
    report_new: list[str] = []
    report_updated: list[str] = []
    report_missing: list[str] = []

    progress_iter = tqdm(titles, desc="Collecting", disable=args.report)
    for title in progress_iter:
        page_url = f"https://dungeon-crawler-carl.fandom.com/wiki/{title.replace(' ', '_')}"
        raw_path = os.path.join(RAW_DIR, f"{sanitize_title_for_fs(title)}.wikitext.txt")
        previous_hash = file_hash(raw_path)
        raw = fetch_wikitext(title)
        current_hash = file_hash(raw_path)
        if (
            not args.force
            and previous_hash
            and previous_hash == current_hash
        ):
            candidate_output = os.path.join(DATA_DIR, f"{slug(title)}.json")
            if os.path.exists(candidate_output):
                skipped += 1
                continue
        try:
            output_path = os.path.join(DATA_DIR, f"{slug(title)}.json")
            if args.report:
                if not os.path.exists(output_path):
                    if previous_hash:
                        report_missing.append(title)
                    else:
                        report_new.append(title)
                elif args.force or previous_hash != current_hash:
                    report_updated.append(title)
                continue

            record = extract_record(title, page_url, raw["wikitext"])
            base_identifier = record.get("id") or record.get("name") or title
            record["id"] = slug(base_identifier)
            record["name"] = record.get("name") or title
            if not record["id"]:
                record["id"] = slug(title)
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
                log.write(f"{title}\t{type(exc).__name__}: {exc}\n")
            print(f"[ERROR] {title}: {exc}")

    if args.report:
        if report_new:
            print("New titles:")
            for title in report_new:
                print(f"  + {title}")
        if report_updated:
            print("Updated titles:")
            for title in report_updated:
                print(f"  * {title}")
        if report_missing:
            print("Missing outputs:")
            for title in report_missing:
                print(f"  ? {title}")
        total = len(report_new) + len(report_updated) + len(report_missing)
        print(f"Report complete. total={total} new={len(report_new)} updated={len(report_updated)} missing={len(report_missing)}")
        return

    print(f"Done. written={written} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()

import os
import time
from typing import List, Dict

import requests
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)

from collector.config import WIKI_API, USER_AGENT, RATE_LIMIT_SECONDS, RAW_DIR

os.makedirs(RAW_DIR, exist_ok=True)


class MWError(Exception):
    pass


@retry(
    wait=wait_exponential(multiplier=1, min=1, max=30),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((requests.HTTPError, MWError)),
)
def _get(params: Dict) -> Dict:
    params = {**params, "format": "json"}
    response = requests.get(
        WIKI_API,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    if response.status_code >= 500:
        raise MWError(f"Server error {response.status_code}")
    response.raise_for_status()
    time.sleep(RATE_LIMIT_SECONDS)
    return response.json()


def list_category_titles(category: str) -> List[str]:
    titles: List[str] = []
    continuation = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": 500,
        }
        if continuation:
            params["cmcontinue"] = continuation
        data = _get(params)
        titles.extend(
            [
                entry["title"]
                for entry in data["query"]["categorymembers"]
                if entry.get("ns") == 0
            ]
        )
        continuation = data.get("continue", {}).get("cmcontinue")
        if not continuation:
            break
    return titles


def fetch_wikitext(title: str) -> Dict:
    data = _get(
        {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
        }
    )
    pages = data["query"]["pages"]
    page = next(iter(pages.values()))
    revision = page["revisions"][0]
    content = revision["slots"]["main"]["*"]
    path = os.path.join(RAW_DIR, f"{title}.wikitext.txt")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return {"title": title, "wikitext": content, "pageid": page["pageid"]}

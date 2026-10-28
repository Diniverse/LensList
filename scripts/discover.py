from __future__ import annotations

import sys
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

from scripts.core import DATA, LOGS, ROOT, parse_deadline, utc_now, write_json, load_json

HEADERS = {"User-Agent": "LensListBot/1.0 (+https://github.com/Diniverse/LensList)"}
TIMEOUT = 25


def domain_matches(url: str, trusted_domain: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    trusted_domain = trusted_domain.lower()
    return hostname == trusted_domain or hostname.endswith("." + trusted_domain)


def fetch_page(session: requests.Session, url: str) -> tuple[str, str]:
    response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "noscript"]):
        element.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else url
    text = soup.get_text(" ", strip=True)
    return title, text


def candidate_from_page(source: dict[str, Any], title: str, text: str, url: str) -> dict[str, Any]:
    return {
        "id": source["id"],
        "title": source.get("name") or title,
        "organization": source["organization"],
        "category": source["category"],
        "location": source.get("location", "Not specified"),
        "geography": source.get("geography", "Other"),
        "deadline": parse_deadline(text),
        "rolling": bool(source.get("rolling", False)),
        "eligibility": source.get("eligibility", "Verify on the official page."),
        "compensation": source.get("compensation", "Not stated."),
        "copyright_terms": source.get("copyright_terms", "Verify on the official page."),
        "publication_costs": source.get("publication_costs", "Verify on the official page."),
        "source_url": url,
        "verification_url": url,
        "source_text": text[:100000],
        "summary": text[:360].strip(),
        "tags": source.get("tags", []),
        "discovered_at": utc_now(),
    }


def discover_source(session: requests.Session, source: dict[str, Any]) -> list[dict[str, Any]]:
    if not domain_matches(source["url"], source["trusted_domain"]):
        raise ValueError(f"Source domain does not match trusted_domain: {source['id']}")

    if source["type"] == "page":
        title, text = fetch_page(session, source["url"])
        return [candidate_from_page(source, title, text, source["url"])]

    response = session.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    keywords = [keyword.lower() for keyword in source.get("include_keywords", [])]
    candidates: list[dict[str, Any]] = []
    for index, entry in enumerate(feed.entries[:30]):
        entry_title = str(entry.get("title", ""))
        entry_summary = BeautifulSoup(str(entry.get("summary", "")), "html.parser").get_text(" ", strip=True)
        haystack = f"{entry_title} {entry_summary}".lower()
        if keywords and not any(keyword in haystack for keyword in keywords):
            continue
        link = str(entry.get("link", ""))
        if not link or not domain_matches(link, source["trusted_domain"]):
            continue
        try:
            page_title, page_text = fetch_page(session, link)
        except requests.RequestException:
            page_title, page_text = entry_title, entry_summary
        item_source = dict(source)
        item_source["id"] = f"{source['id']}-{index}"
        item_source["name"] = entry_title or page_title
        candidates.append(candidate_from_page(item_source, page_title, page_text, link))
    return candidates


def main() -> int:
    sources = load_json(ROOT / "config" / "sources.json", [])
    session = requests.Session()
    candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    successful_sources = 0
    for source in sources:
        try:
            candidates.extend(discover_source(session, source))
            successful_sources += 1
        except Exception as error:  # keep other sources operational
            errors.append({"source": source.get("id", "unknown"), "error": f"{type(error).__name__}: {error}"})

    write_json(DATA / "candidates.json", candidates)
    write_json(LOGS / "discovery.json", {
        "checked_at": utc_now(),
        "sources_total": len(sources),
        "sources_successful": successful_sources,
        "candidates_found": len(candidates),
        "errors": errors,
    })
    print(f"Discovered {len(candidates)} candidates from {successful_sources}/{len(sources)} sources")
    for error in errors:
        print(f"WARNING {error['source']}: {error['error']}", file=sys.stderr)
    return 0 if successful_sources else 1


if __name__ == "__main__":
    raise SystemExit(main())

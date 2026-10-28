from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"

FREE_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in (
        r"\bno (?:mandatory )?(?:application|submission|entry) fee\b",
        r"\bfree to (?:apply|submit|enter)\b",
        r"\bthere is no fee to (?:apply|submit|enter)\b",
        r"\b(?:applications?|submissions?|entries) (?:are|is) free\b",
        r"\bfree of charge\b",
    )
]

PAID_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:mandatory )?(?:application|submission|entry) fee\s*(?:is|of|:)?\s*(?:US\s*)?[£$€]\s?\d+",
        r"[£$€]\s?\d+(?:\.\d{1,2})?\s+(?:application|submission|entry) fee",
        r"\bpay(?:ment)?\s+(?:an?\s+)?(?:application|submission|entry) fee\b",
    )
]

DATE_PATTERNS = [
    re.compile(r"\b(?:deadline|due|closes?|applications? close)\s*(?:is|on|:)?\s*([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+20\d{2}))", re.I),
    re.compile(r"\b(?:deadline|due|closes?|applications? close)\s*(?:is|on|:)?\s*(20\d{2}-\d{2}-\d{2})", re.I),
    re.compile(r"\b(?:deadline|due|closes?|applications? close)\s*(?:is|on|:)?\s*(\d{1,2}\s+[A-Z][a-z]+\s+20\d{2})", re.I),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, sort_keys=False)
        handle.write("\n")
    temporary.replace(path)


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    clean_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "fbclid", "gclid"}
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(clean_query), ""))


def fingerprint(item: dict[str, Any]) -> str:
    key = "|".join(
        re.sub(r"[^a-z0-9]+", " ", str(item.get(field, "")).lower()).strip()
        for field in ("organization", "title")
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def evidence_excerpt(text: str, match: re.Match[str], radius: int = 120) -> str:
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def classify_fee(text: str) -> tuple[str, str | None]:
    normalized = re.sub(r"\s+", " ", text)
    free_match = next((pattern.search(normalized) for pattern in FREE_PATTERNS if pattern.search(normalized)), None)
    paid_match = next((pattern.search(normalized) for pattern in PAID_PATTERNS if pattern.search(normalized)), None)
    if free_match and not paid_match:
        return "confirmed-free", evidence_excerpt(normalized, free_match)
    if paid_match:
        return "fee-detected", evidence_excerpt(normalized, paid_match)
    return "unverified", None


def parse_deadline(text: str) -> str | None:
    normalized = re.sub(r"\s+", " ", text)
    for pattern in DATE_PATTERNS:
        match = pattern.search(normalized)
        if not match:
            continue
        try:
            parsed = date_parser.parse(match.group(1), fuzzy=True, dayfirst=False)
            return parsed.date().isoformat()
        except (ValueError, OverflowError):
            continue
    return None


def is_expired(deadline: str | None, today: date | None = None) -> bool:
    if not deadline:
        return False
    today = today or datetime.now(timezone.utc).date()
    try:
        return date.fromisoformat(deadline) < today
    except ValueError:
        return True


def deduplicate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    output: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda value: value.get("last_verified", ""), reverse=True):
        url = canonical_url(str(item.get("source_url", "")))
        item["source_url"] = url
        item_fingerprint = fingerprint(item)
        if not url or url in seen_urls or item_fingerprint in seen_fingerprints:
            continue
        seen_urls.add(url)
        seen_fingerprints.add(item_fingerprint)
        item["fingerprint"] = item_fingerprint
        output.append(item)
    return output

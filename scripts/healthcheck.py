from __future__ import annotations

from datetime import datetime, timezone

from scripts.core import DATA, LOGS, canonical_url, fingerprint, is_expired, load_json, utc_now, write_json

REQUIRED_FIELDS = {
    "id", "title", "organization", "category", "location", "geography",
    "eligibility", "compensation", "copyright_terms", "publication_costs",
    "source_url", "deadline", "fee_status", "last_verified",
}


def validate_active(items: list[dict]) -> list[str]:
    errors: list[str] = []
    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    for item in items:
        missing = REQUIRED_FIELDS - item.keys()
        if missing:
            errors.append(f"{item.get('id', 'unknown')}: missing {sorted(missing)}")
        if item.get("fee_status") != "confirmed-free":
            errors.append(f"{item.get('id')}: active item is not confirmed free")
        if is_expired(item.get("deadline")):
            errors.append(f"{item.get('id')}: expired item is active")
        url = canonical_url(item.get("source_url", ""))
        item_fingerprint = fingerprint(item)
        if url in seen_urls or item_fingerprint in seen_fingerprints:
            errors.append(f"{item.get('id')}: duplicate active item")
        seen_urls.add(url)
        seen_fingerprints.add(item_fingerprint)
    return errors


def main() -> int:
    active = load_json(DATA / "opportunities.json", [])
    review = load_json(DATA / "review_queue.json", [])
    meta = load_json(DATA / "meta.json", {})
    errors = validate_active(active)
    if not meta.get("last_updated"):
        errors.append("meta.json has no last_updated timestamp")
    report = {
        "checked_at": utc_now(),
        "healthy": not errors,
        "active_count": len(active),
        "review_count": len(review),
        "errors": errors,
    }
    write_json(LOGS / "automation-health.json", report)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Healthy: {len(active)} active opportunities; {len(review)} awaiting review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

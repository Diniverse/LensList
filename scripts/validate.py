from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from scripts.core import DATA, classify_fee, deduplicate, fingerprint, is_expired, load_json, utc_now, write_json


def public_item(candidate: dict[str, Any], fee_status: str, evidence: str | None) -> dict[str, Any]:
    item = {key: value for key, value in candidate.items() if key != "source_text"}
    item["fee_status"] = fee_status
    item["fee_evidence"] = evidence
    item["last_verified"] = utc_now()
    item["status"] = "open"
    item["fingerprint"] = fingerprint(item)
    return item


def review_reason(candidate: dict[str, Any], fee_status: str) -> list[str]:
    reasons: list[str] = []
    if fee_status != "confirmed-free":
        reasons.append("mandatory fee not conclusively ruled out" if fee_status == "unverified" else "fee language detected")
    if not candidate.get("deadline") and not candidate.get("rolling"):
        reasons.append("opening or deadline not confirmed")
    return reasons


def main() -> int:
    candidates = load_json(DATA / "candidates.json", [])
    previous_active = load_json(DATA / "opportunities.json", [])
    archive = load_json(DATA / "archive.json", [])
    previous_by_fingerprint = {item.get("fingerprint") or fingerprint(item): item for item in previous_active}

    active: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []

    for candidate in candidates:
        fee_status, evidence = classify_fee(candidate.get("source_text", ""))
        item = public_item(candidate, fee_status, evidence)
        reasons = review_reason(candidate, fee_status)
        if is_expired(item.get("deadline")):
            item["status"] = "expired"
            item["archived_at"] = utc_now()
            archive.append(item)
            continue
        if reasons:
            item["status"] = "review"
            item["review_reasons"] = reasons
            review.append(item)
            continue

        prior = previous_by_fingerprint.get(item["fingerprint"])
        if not prior:
            changes.append({"kind": "new", "id": item["id"], "title": item["title"], "detected_at": utc_now()})
        elif prior.get("deadline") != item.get("deadline"):
            changes.append({
                "kind": "deadline-changed",
                "id": item["id"],
                "title": item["title"],
                "old_deadline": prior.get("deadline"),
                "new_deadline": item.get("deadline"),
                "detected_at": utc_now(),
            })
        active.append(item)

    current_fingerprints = {fingerprint(item) for item in active + review}
    for prior in previous_active:
        if (prior.get("fingerprint") or fingerprint(prior)) not in current_fingerprints and is_expired(prior.get("deadline")):
            archived = dict(prior)
            archived["status"] = "expired"
            archived["archived_at"] = utc_now()
            archive.append(archived)

    active = deduplicate(active)
    review = deduplicate(review)
    archive = deduplicate(archive)
    write_json(DATA / "opportunities.json", active)
    write_json(DATA / "review_queue.json", review)
    write_json(DATA / "archive.json", archive)
    write_json(DATA / "changes.json", changes)
    write_json(DATA / "meta.json", {
        "last_updated": utc_now(),
        "active_count": len(active),
        "review_count": len(review),
        "archive_count": len(archive),
        "pipeline": "operational",
    })
    print(f"Validated {len(active)} active; {len(review)} review; {len(archive)} archived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

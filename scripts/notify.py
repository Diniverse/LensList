from __future__ import annotations

import html
import os
import smtplib
import ssl
from datetime import date, datetime, timezone
from email.message import EmailMessage

from scripts.core import DATA, load_json, utc_now, write_json


def due_items(items: list[dict], thresholds: list[int], sent: set[str]) -> list[tuple[dict, int, str]]:
    output: list[tuple[dict, int, str]] = []
    today = datetime.now(timezone.utc).date()
    for item in items:
        if not item.get("deadline"):
            continue
        days = (date.fromisoformat(item["deadline"]) - today).days
        if days not in thresholds:
            continue
        key = f"deadline:{item['fingerprint']}:{item['deadline']}:{days}"
        if key not in sent:
            output.append((item, days, key))
    return output


def frequency_due(last_digest: str | None, frequency: str) -> bool:
    if not last_digest:
        return True
    elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last_digest.replace("Z", "+00:00"))
    minimum = {"daily": 1, "weekly": 7, "monthly": 28}.get(frequency, 7)
    return elapsed.days >= minimum


def main() -> int:
    required = ["LENSLIST_SMTP_HOST", "LENSLIST_SMTP_USERNAME", "LENSLIST_SMTP_PASSWORD", "LENSLIST_EMAIL_TO"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print("Email disabled: configure GitHub Actions secrets " + ", ".join(missing))
        return 0

    frequency = (os.getenv("LENSLIST_DIGEST_FREQUENCY") or "weekly").lower()
    threshold_setting = os.getenv("LENSLIST_DEADLINE_DAYS") or "14,7,3,1"
    thresholds = [int(value) for value in threshold_setting.split(",") if value.strip().isdigit()]
    opportunities = load_json(DATA / "opportunities.json", [])
    changes = load_json(DATA / "changes.json", [])
    state = load_json(DATA / "notification_state.json", {"sent_ids": [], "last_digest": None})
    sent = set(state.get("sent_ids", []))

    new_items = []
    if frequency_due(state.get("last_digest"), frequency):
        by_id = {item["id"]: item for item in opportunities}
        for change in changes:
            if change.get("kind") != "new" or change.get("id") not in by_id:
                continue
            item = by_id[change["id"]]
            key = f"new:{item['fingerprint']}:{item['last_verified']}"
            if key not in sent:
                new_items.append((item, key))

    deadlines = due_items(opportunities, thresholds, sent)
    if not new_items and not deadlines:
        print("No unsent LensList alerts")
        return 0

    body = ["<h1>LensList digest</h1>"]
    if new_items:
        body.append("<h2>New verified opportunities</h2><ul>")
        for item, _key in new_items:
            body.append(f'<li><a href="{html.escape(item["source_url"])}">{html.escape(item["title"])}</a> — {html.escape(item["organization"])}</li>')
        body.append("</ul>")
    if deadlines:
        body.append("<h2>Approaching deadlines</h2><ul>")
        for item, days, _key in deadlines:
            body.append(f'<li><a href="{html.escape(item["source_url"])}">{html.escape(item["title"])}</a> — {days} day(s) left</li>')
        body.append("</ul>")
    body.append("<p>Every item in the active feed has official-source evidence that no mandatory application or submission fee was found.</p>")

    message = EmailMessage()
    message["Subject"] = f"LensList: {len(new_items)} new, {len(deadlines)} deadlines"
    message["From"] = os.getenv("LENSLIST_EMAIL_FROM") or os.environ["LENSLIST_SMTP_USERNAME"]
    message["To"] = os.environ["LENSLIST_EMAIL_TO"]
    message.set_content("LensList has new verified opportunities or approaching deadlines. View the HTML version of this email.")
    message.add_alternative("".join(body), subtype="html")

    host = os.environ["LENSLIST_SMTP_HOST"]
    port = int(os.getenv("LENSLIST_SMTP_PORT") or "465")
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
        server.login(os.environ["LENSLIST_SMTP_USERNAME"], os.environ["LENSLIST_SMTP_PASSWORD"])
        server.send_message(message)

    sent.update(key for _item, key in new_items)
    sent.update(key for _item, _days, key in deadlines)
    state["sent_ids"] = sorted(sent)[-2000:]
    state["last_digest"] = utc_now()
    write_json(DATA / "notification_state.json", state)
    print(f"Sent {len(new_items)} new and {len(deadlines)} deadline alerts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

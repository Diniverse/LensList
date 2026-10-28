# LensList

LensList is a static, mobile-first directory that discovers photography opportunities from trusted official sources and only promotes a listing to the active feed when the page contains explicit evidence that there is no mandatory application, submission, or entry fee.

## What is operational

- Responsive GitHub Pages interface with search, category/geography/deadline filters, local saves, a local application tracker, CSV export, detailed terms, a separate review queue, and a visible update timestamp.
- Daily discovery from configured official pages and RSS feeds.
- Fee-language validation, deadline extraction, canonical-URL/title deduplication, deadline-change events, expiry removal, and archive maintenance.
- Automated unit tests and a health check that reject expired, duplicate, or non-confirmed-free active listings.
- Automatic Pages deployment whenever the UI or data changes.
- SMTP email code with persistent duplicate-alert protection and configurable digest/deadline frequency.

## What requires owner configuration

GitHub Pages and the scheduled data refresh need no third-party credentials. Email is intentionally disabled until SMTP secrets are added.

### 1. Enable GitHub Pages

In **Settings → Pages**, set **Source** to **GitHub Actions**. The `Deploy LensList to GitHub Pages` workflow publishes the site.

### 2. Allow Actions to update data

In **Settings → Actions → General → Workflow permissions**, select **Read and write permissions**. The refresh and email workflows need this to commit JSON state. If branch protection is enabled, allow GitHub Actions to push or change the workflow to open a pull request.

### 3. Configure email (optional)

Add these at **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Purpose |
|---|---|
| `LENSLIST_SMTP_HOST` | SMTP server, e.g. `smtp.gmail.com` |
| `LENSLIST_SMTP_PORT` | SSL port, normally `465` |
| `LENSLIST_SMTP_USERNAME` | SMTP login / sender account |
| `LENSLIST_SMTP_PASSWORD` | SMTP password or app password |
| `LENSLIST_EMAIL_FROM` | Optional From address; defaults to username |
| `LENSLIST_EMAIL_TO` | Digest recipient |

Optional repository variables:

| Variable | Values | Default |
|---|---|---|
| `LENSLIST_DIGEST_FREQUENCY` | `daily`, `weekly`, or `monthly` | `weekly` |
| `LENSLIST_DEADLINE_DAYS` | Comma-separated day thresholds | `14,7,3,1` |

Gmail SMTP can be used without a paid API, but requires a Google account with two-step verification and an app password. Provider sending limits still apply. Services such as Resend or Postmark may require registration, a verified sending domain, and can incur charges above their free allowances; LensList does not require them.

## Workflows

- `refresh-data.yml` — daily at 06:17 UTC: discover → validate → test → health-check → commit data.
- `email-digest.yml` — daily at 06:47 UTC: send any due digest/deadline alerts and commit only notification state. Missing SMTP secrets produce a clean no-op.
- `deploy-pages.yml` — deploy the static site on relevant `main` changes.
- `ci.yml` — run tests and the health check on pull requests and relevant pushes.

Schedules can be run manually from the **Actions** tab. GitHub may delay scheduled workflows during periods of heavy load.

## Editorial and validation policy

The active feed is fail-closed. A candidate must:

1. come from a configured official domain;
2. contain an explicit phrase such as “no application fee” or “free to submit”;
3. contain no conflicting mandatory-fee pattern;
4. be rolling or have a non-expired deadline.

Anything uncertain goes to `data/review_queue.json`; it is never labelled confirmed free. Expired calls move to `data/archive.json`. Automated extraction is deliberately conservative and cannot replace reading the official terms before applying.

Each record supports official URL, deadline, eligibility, location/geography, compensation, copyright terms, publication costs, evidence, and verification time. Some fields remain “verify on the official page” until they can be extracted reliably; that does not weaken the fee gate.

## Add or change sources

Edit `config/sources.json`. Each source must declare `trusted_domain`. Supported source types are:

- `page`: check one official opportunity/hub page;
- `feed`: inspect an official RSS feed, filter entries by `include_keywords`, then validate each matching official page.

Avoid aggregator pages as proof. Their links may help discovery, but fee confirmation should come from the organiser.

## Local development

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m scripts.healthcheck
python -m http.server 8000
```

Run live discovery with `python -m scripts.discover`, then `python -m scripts.validate`. It performs outbound requests and rewrites JSON data.

## Error logging and health

- `logs/discovery.json` records per-source failures without discarding successful sources.
- `logs/automation-health.json` records schema, fee, duplicate, and expiry checks.
- Failed workflow runs remain visible in the repository Actions tab and do not silently publish invalid active data.

The front end has no API keys, email credentials, analytics, account system, or build-time secret injection. Saved opportunities and tracker stages remain in browser local storage.

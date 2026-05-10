# PrayerTimes

Automated prayer-time events in Google Calendar, travel-aware. A GitHub Actions
workflow runs on the 1st of every month, populates the current and next month
of events into the **Prayer Times** calendar, and switches location automatically
when it sees flights in the **Travelling** calendar.

## How it works

1. **Default location** is Richmond, BC (`America/Vancouver`).
2. The script reads multiple Google Calendars (default: **Travelling**,
   **Egypt Trip 2026**, and **My Life**) for the past 60 days through the end
   of the target month, and recognises flight events in two formats:
   - **Manual:** `<FLIGHT> from <ORIGIN_IATA> to <DEST_IATA> (...)` —
     destination IATA in the title.
   - **Gmail-imported:** title `Flight to <CITY> (<FLIGHT>)` with the origin
     in the Location field — destination city is mapped to its main IATA
     via `CITY_TO_IATA` overrides plus an `airportsdata` fallback.
   Duplicate landings (same destination within 30 min) are deduped, so it's
   safe for the same flight to appear in two calendars.
3. The end datetime of each flight is taken as the real arrival moment in UTC
   (whatever offset/TZ Google returns is honored as-is).
4. After each landing, prayer times follow the destination city until the next
   landing. During a flight (and any layover), the source city still applies
   — matching the rule "during travel, follow source; on arrival, switch."
5. For each location segment, prayer times come from
   [Aladhan](https://aladhan.com)'s `calendarByAddress` endpoint with method 15
   (Moonsighting Committee).
6. Each run **wipes existing prayer events for the target month and reinserts
   a fresh set**. Manual edits don't survive a re-run — intentional, so the
   calendar always reflects current travel plans.

## Files

- `prayertimes.py` — main script.
- `bootstrap_oauth.py` — one-time helper to mint a refresh token.
- `.github/workflows/prayer-times.yml` — monthly cron + manual trigger.
- `requirements.txt` — Python deps.
- `PrayerTimes.ps1` — original PowerShell script, kept for reference.

## One-time setup

### 1. Create a Google Cloud OAuth Client

1. Go to <https://console.cloud.google.com/>, create a project (or reuse one).
2. **APIs & Services → Library**, search for **Google Calendar API**, enable it.
3. **APIs & Services → OAuth consent screen**: configure as **External**, add
   yourself as a Test user. No scopes need to be added on the consent screen.
4. **APIs & Services → Credentials → Create Credentials → OAuth Client ID**,
   choose **Desktop app**. Download the JSON (called something like
   `client_secret_xxx.json`).

### 2. Mint a refresh token locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bootstrap_oauth.py /path/to/client_secret_xxx.json
```

A browser window opens; grant Calendar access. The script prints three values.

### 3. Add three GitHub Actions secrets

In the repo's **Settings → Secrets and variables → Actions**, add:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`

### 4. Trigger the first run

Go to **Actions → Update Prayer Times → Run workflow** and run with defaults
(or set `dry_run = true` first to verify what it would do). After that, it
runs automatically on the 1st of every month.

## Manual overrides (e.g., during ground travel)

When you're somewhere a flight event can't represent — e.g., in Mecca after
landing at Jeddah — trigger the workflow manually with `address` and `tz`:

- `address`: `Mecca, Saudi Arabia`
- `tz`: `Asia/Riyadh`
- `year` / `month`: leave blank to use current

The override replaces the *default* home location only; it does not override
landings parsed from the Travelling calendar.

## Local dry-run

```bash
export GOOGLE_CLIENT_ID=...
export GOOGLE_CLIENT_SECRET=...
export GOOGLE_REFRESH_TOKEN=...
python prayertimes.py --year 2026 --month 5 --dry-run
```

## Caveats

- IATA → city/timezone lookup uses the [`airportsdata`](https://pypi.org/project/airportsdata/)
  package. Unknown IATA codes log a warning and are skipped.
- For Gmail-format flights, destination city → IATA goes through `CITY_TO_IATA`
  first (handles ambiguous cities like London, and cases where airportsdata
  uses a non-obvious city name like "Richmond" for YVR or "Frankfurt am Main"
  for FRA), then falls back to airportsdata for unambiguous matches. Add an
  entry to `CITY_TO_IATA` if a new destination doesn't resolve.
- A few country codes (ISO alpha-2) are mapped to friendlier names in
  `COUNTRY_NAMES` for Aladhan geocoding; extend if you travel somewhere new
  and Aladhan can't resolve the address.
- On the day you fly, prayers that fall in the window between landing and the
  destination's next prayer time may not appear (e.g., if you land after the
  source's Fajr but before the destination's). This is the consistent
  application of the "follow source until landing" rule.

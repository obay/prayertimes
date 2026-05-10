# PrayerTimes — Claude session context

Personal automation that puts Ahmad's prayer times into Google Calendar each
month, switching cities automatically when his travel calendars show a flight.
Replaced a manual PowerShell + CSV import that he ran by hand monthly.

## Live system

- **Repo:** https://github.com/obay/prayertimes
- **Workflow:** `.github/workflows/prayer-times.yml` runs cron `0 12 1 * *`
  (1st of each month, 12:00 UTC, ~04:00 PT) and on-demand via
  `workflow_dispatch`. Default behavior populates current + next month.
- **Auth:** OAuth refresh token stored as three repo secrets
  (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`).
  Already provisioned in Ahmad's personal Google Cloud project; Calendar
  API enabled.

## Calendar IDs

| Purpose | Name | ID |
|---|---|---|
| Output (script writes here) | Prayer Times | `fh2sb9rtl1182njokiqfv3d7es@group.calendar.google.com` |
| Travel — long-running default | Travelling | `14qanoij4omvbp74r209vpgfko@group.calendar.google.com` |
| Travel — per-trip | Egypt Trip 2026 | `0524a0fe62dc7366047772d4a633c753166708920daf0813c70c1dec63b8cf90@group.calendar.google.com` |
| Personal — Gmail-imported flights live here | My Life | `ahmad.obay@gmail.com` |
| Personal recurring dates (e.g. Egyptian Mother's Day) | Events | `nd6pm6cuvlfdf6b2o05vvp8tcs@group.calendar.google.com` |

The script scans the three travel-related calendars by default. Override with
`--travel-calendar-ids` (comma-separated).

## The travel rule (codified, do not change without asking)

> "During a flight, follow the source city's prayer schedule. Once you land,
> switch to the destination's schedule."

Implementation: each LANDING (the end datetime of a flight event) marks a
location transition. Between two landings, only one city's schedule applies —
the destination of the most recent landing (or the default home location
before any landing). During a flight in progress, the previous segment's
location continues to apply until that flight lands.

## Flight event recognition

Two formats are recognized in `parse_flight_destination()`:

- **Manual:** title `<FLIGHT> from <ORIGIN_IATA> to <DEST_IATA> (<PNR>)` —
  destination IATA in the title.
- **Gmail-auto-imported:** title `Flight to <CITY> (<FLIGHT>)` with origin
  in the Location field. City → IATA via `CITY_TO_IATA` overrides + the
  `airportsdata` package as fallback.

Duplicate landings within 30 minutes at the same destination are deduped
(`_dedupe_landings`), so the same flight in multiple calendars is harmless.

## Design choices with a "why"

- **Aladhan API method 15** (Moonsighting Committee) — matches the legacy
  `PrayerTimes.ps1`. Don't change without asking Ahmad.
- **Six events per day** — Fajr, Sunrise, Dhuhr (or Friday Prayer on Fri),
  Asr, Maghrib, Isha. Sunrise is included as a *time marker* (end of Fajr
  window), not as a prayer. Imsak and Midnight are intentionally off.
- **Wipe-and-recreate per month** — manual edits to prayer events do not
  survive a re-run. Intentional, so the calendar always matches current
  travel plans.
- **End-time TZ on flight events is *not* trusted** — Ahmad's calendar
  has historical events with wrong end-TZs (e.g. an LHR→CAI flight tagged
  America/Vancouver). The dateTime field's offset/Z is what we use to
  compute UTC; only the destination IATA from the title (or from Gmail
  city lookup) determines the new location's TZ.
- **100ms sleep + exponential-backoff retry on writes** — Google Cloud
  projects ship with conservative per-second write quotas; the first real
  run hit `rateLimitExceeded` partway through May. `_execute_with_retry`
  in `prayertimes.py` handles 403/429/5xx with exponential backoff.

## Known transition-day quirk

On the day Ahmad lands somewhere, prayers between the source's last
in-window prayer and the destination's next in-window prayer are dropped.
Example: May 16 2026 only emits 2 events (Vancouver Fajr + London Asr) —
the YVR→LHR landing is at 12:20 UTC and the LHR→CAI landing is at 18:55
UTC; everything else falls in a gap. This is the mathematically consistent
application of the travel rule; he has accepted it.

## Manual operations

- **Trigger a run:** Actions tab → Update Prayer Times → Run workflow.
- **Dry run:** check the `dry_run` box — prints what would happen, no writes.
- **Override default location during ground travel** (e.g. when in Mecca but
  the script thinks Jeddah from the JED landing): trigger with
  `address=Mecca, Saudi Arabia`, `tz=Asia/Riyadh`. Only changes the
  *default* location — landings parsed from calendars still take precedence.
- **Specific past/future month:** trigger with `year` and `month` inputs.

## Files

- `prayertimes.py` — main script (parser, segments, Aladhan, Calendar I/O)
- `bootstrap_oauth.py` — one-time helper to mint the refresh token
- `smoketest.py` — offline test harness using synthetic landings (no auth)
- `.github/workflows/prayer-times.yml` — cron + manual trigger
- `requirements.txt`, `.gitignore`, `README.md`
- `PrayerTimes.ps1` — original PowerShell, kept for reference

## Setup that's already done — don't redo

- Google Cloud OAuth client (Desktop type) created in Ahmad's personal
  Google Cloud project.
- Calendar API enabled.
- Three repo secrets set via `gh secret set`.
- May + June 2026 prayer events live in the Prayer Times calendar.
- Egypt Trip 2026 calendar consolidated: holds all 9 trip flights plus
  itinerary events. Travelling calendar is empty for this trip window.

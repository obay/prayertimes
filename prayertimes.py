#!/usr/bin/env python3
"""Generate prayer-time events in a Google Calendar, travel-aware.

Default location is Richmond, BC. Reads the user's "Travelling" calendar
to find flight events (titles like "AC2849 from CAI to LHR (...)") and
switches the prayer-times location to the destination at each landing.

Each monthly run wipes existing prayer events for the target month and
reinserts a fresh set so it stays correct as travel plans change.
"""

import argparse
import calendar
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

import airportsdata
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ALADHAN_BASE = "https://api.aladhan.com/v1/calendarByAddress"
ALADHAN_METHOD = 15  # Moonsighting Committee — matches PrayerTimes.ps1

PRAYERS_TO_EMIT = ["Sunrise", "Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
FRIDAY_DHUHR_TITLE = "Friday Prayer"
ALL_PRAYER_TITLES = set(PRAYERS_TO_EMIT) | {FRIDAY_DHUHR_TITLE}

DEFAULT_ADDRESS = "Richmond, BC, Canada"
DEFAULT_TZ = "America/Vancouver"
DEFAULT_TRAVEL_CALENDAR_IDS = [
    "14qanoij4omvbp74r209vpgfko@group.calendar.google.com",  # Travelling
    "0524a0fe62dc7366047772d4a633c753166708920daf0813c70c1dec63b8cf90@group.calendar.google.com",  # Egypt Trip 2026
    "ahmad.obay@gmail.com",  # My Life — picks up Gmail-imported flight events
]
DEFAULT_PRAYER_CALENDAR_ID = "fh2sb9rtl1182njokiqfv3d7es@group.calendar.google.com"

# Format A — manually-entered flights: "AC2849 from CAI to LHR (...)"
FLIGHT_TITLE_RE = re.compile(r"\bfrom\s+([A-Z]{3})\s+to\s+([A-Z]{3})\b", re.IGNORECASE)

# Format B — Gmail-auto-imported flights: title "Flight to Cairo (SV 383)" with
# Location field "Jeddah JED" (city + IATA). The destination IATA is not in the
# title, so we resolve it from the city name via CITY_TO_IATA / airportsdata.
GMAIL_FLIGHT_TITLE_RE = re.compile(r"^\s*Flight\s+to\s+(.+?)\s*\(", re.IGNORECASE)
GMAIL_LOCATION_IATA_RE = re.compile(r"\b([A-Z]{3})\b\s*$")

# City name -> canonical IATA. Used by parse_flight_destination when the
# Gmail event title only gives a city name. Two reasons an entry needs to be
# here: (a) the city has multiple airports and we want a specific one, or
# (b) airportsdata stores the city under a different name (e.g. YVR's city
# is "Richmond", FRA's city is "Frankfurt am Main", "Cairo" is also a town
# in Idaho USA, etc.). For unambiguous cities not in this list, the lookup
# falls back to airportsdata directly.
CITY_TO_IATA = {
    "Cairo": "CAI",
    "Vancouver": "YVR",
    "Frankfurt": "FRA",
    "Frankfurt am Main": "FRA",
    "London": "LHR",
    "New York": "JFK",
    "Paris": "CDG",
    "Tokyo": "HND",
    "Shanghai": "PVG",
    "Beijing": "PEK",
    "Moscow": "SVO",
    "Rome": "FCO",
    "Berlin": "BER",
    "Toronto": "YYZ",
    "Houston": "IAH",
    "Washington": "IAD",
    "Chicago": "ORD",
    "Los Angeles": "LAX",
    "Dubai": "DXB",
    "Riyadh": "RUH",
    "Hong Kong": "HKG",
    "Seoul": "ICN",
    "Mumbai": "BOM",
    "Delhi": "DEL",
    "Bangkok": "BKK",
    "Sydney": "SYD",
    "Melbourne": "MEL",
    "Sao Paulo": "GRU",
    "Mexico City": "MEX",
    "Buenos Aires": "EZE",
    "Istanbul": "IST",
}

AIRPORTS = airportsdata.load("IATA")  # IATA -> {name, city, country, tz, lat, lon, ...}

# ISO 3166-1 alpha-2 -> friendly name. Aladhan accepts "City, Country"; the
# friendlier the country name, the better the geocoding. Extend as travel widens.
COUNTRY_NAMES = {
    "AE": "United Arab Emirates", "BH": "Bahrain", "CA": "Canada",
    "CH": "Switzerland", "DE": "Germany", "EG": "Egypt", "ES": "Spain",
    "FR": "France", "GB": "United Kingdom", "GR": "Greece", "IE": "Ireland",
    "IT": "Italy", "JO": "Jordan", "KW": "Kuwait", "LB": "Lebanon",
    "MA": "Morocco", "NL": "Netherlands", "OM": "Oman", "QA": "Qatar",
    "SA": "Saudi Arabia", "TR": "Turkey", "US": "United States",
}


@dataclass
class Location:
    address: str  # Aladhan-friendly, e.g. "Cairo, Egypt"
    tz: str       # IANA TZ name, e.g. "Africa/Cairo"
    label: str    # for log output


@dataclass
class Landing:
    when_utc: datetime
    location: Location


@dataclass
class Segment:
    start_utc: datetime  # inclusive
    end_utc: datetime    # exclusive
    location: Location


@dataclass
class PrayerEvent:
    title: str
    when_local: datetime  # naive, in `tz`
    tz: str


def airport_to_location(iata: str) -> Location | None:
    info = AIRPORTS.get(iata.upper())
    if not info:
        return None
    city = info["city"]
    country_code = info["country"]
    country = COUNTRY_NAMES.get(country_code, country_code)
    return Location(
        address=f"{city}, {country}",
        tz=info["tz"],
        label=f"{iata.upper()} ({city}, {country})",
    )


def city_to_iata(city_name: str) -> str | None:
    """Resolve a city name to its main IATA code.

    Uses CITY_TO_IATA overrides first (for ambiguous cities like London),
    then falls back to scanning airportsdata for an unambiguous single match.
    Returns None if the city is unknown or ambiguous.
    """
    name = city_name.strip()
    if name in CITY_TO_IATA:
        return CITY_TO_IATA[name]
    matches = [iata for iata, info in AIRPORTS.items() if info["city"].lower() == name.lower()]
    if len(matches) == 1:
        return matches[0]
    return None


def parse_flight_destination(summary: str, location: str | None) -> str | None:
    """Return the destination IATA for a flight event, or None if not a flight.

    Handles two formats:
      A. Manual: "<FLIGHT> from <ORIGIN_IATA> to <DEST_IATA> (<PNR>)"
      B. Gmail:  title "Flight to <CITY> (<FLIGHT>)", location "<City> <IATA>"
    """
    m = FLIGHT_TITLE_RE.search(summary)
    if m:
        return m.group(2).upper()
    m = GMAIL_FLIGHT_TITLE_RE.search(summary)
    if m:
        return city_to_iata(m.group(1).strip())
    return None


def get_calendar_service(refresh_token: str, client_id: str, client_secret: str):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _to_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_event_datetime(field: dict) -> datetime | None:
    """Parse a Calendar API start/end dict into a UTC-aware datetime.

    Trusts whatever offset/TZ the field carries (whether the dateTime ends in
    "Z", has a numeric offset like "+03:00", or is naive with a separate
    `timeZone`). The dateTime represents a real instant in time; we don't
    re-interpret it against the destination's TZ.
    """
    iso = field.get("dateTime")
    if not iso:
        return None
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        tz_name = field.get("timeZone") or "UTC"
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc)


def fetch_landings(svc, calendar_ids: list[str], start_utc: datetime, end_utc: datetime) -> list[Landing]:
    """Read flight events from one or more travel calendars and turn each into a Landing.

    The destination IATA in the event title is the source of truth for which
    city's prayer times to use after landing. The event's end datetime is
    trusted as a real moment in UTC (whatever offset Google returned).
    """
    landings: list[Landing] = []
    for calendar_id in calendar_ids:
        page_token = None
        while True:
            resp = svc.events().list(
                calendarId=calendar_id,
                timeMin=_to_rfc3339(start_utc),
                timeMax=_to_rfc3339(end_utc),
                singleEvents=True,
                orderBy="startTime",
                pageToken=page_token,
                maxResults=2500,
            ).execute()
            for ev in resp.get("items", []):
                summary = ev.get("summary") or ""
                location_field = ev.get("location") or ""
                dest_iata = parse_flight_destination(summary, location_field)
                if not dest_iata:
                    continue
                loc = airport_to_location(dest_iata)
                if not loc:
                    print(f"[warn] unknown IATA {dest_iata!r} in event {summary!r}", file=sys.stderr)
                    continue
                when_utc = _parse_event_datetime(ev.get("end", {}))
                if when_utc is None:
                    continue
                landings.append(Landing(when_utc=when_utc, location=loc))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
    return _dedupe_landings(landings)


def _dedupe_landings(landings: list[Landing]) -> list[Landing]:
    """Drop duplicate landings to the same destination within 30 min of each other.

    This handles the common case where the same flight appears in two scanned
    calendars (e.g., manually in 'Egypt Trip 2026' and Gmail-imported into
    'My Life'). The first one wins.
    """
    landings = sorted(landings, key=lambda l: l.when_utc)
    deduped: list[Landing] = []
    for l in landings:
        if deduped:
            last = deduped[-1]
            same_dest = last.location.label == l.location.label
            close_in_time = abs((l.when_utc - last.when_utc).total_seconds()) < 1800
            if same_dest and close_in_time:
                continue
        deduped.append(l)
    return deduped


def build_segments(
    landings: list[Landing],
    default_loc: Location,
    start_utc: datetime,
    end_utc: datetime,
) -> list[Segment]:
    """Slice [start_utc, end_utc) into [start, end) segments, one per location.

    Default location applies before any landing. After each landing, that
    flight's destination applies until the next landing — which means during
    the next flight, the source (= previous destination) still applies until
    that flight lands. This matches the user's stated rule.
    """
    current_loc = default_loc
    for landing in landings:
        if landing.when_utc <= start_utc:
            current_loc = landing.location
        else:
            break

    segments: list[Segment] = []
    cursor = start_utc
    for landing in landings:
        if landing.when_utc <= start_utc:
            continue
        if landing.when_utc >= end_utc:
            break
        if landing.when_utc > cursor:
            segments.append(Segment(start_utc=cursor, end_utc=landing.when_utc, location=current_loc))
        cursor = landing.when_utc
        current_loc = landing.location
    if cursor < end_utc:
        segments.append(Segment(start_utc=cursor, end_utc=end_utc, location=current_loc))
    return segments


def fetch_aladhan_month(address: str, year: int, month: int) -> list[dict]:
    resp = requests.get(
        ALADHAN_BASE,
        params={"address": address, "method": ALADHAN_METHOD, "month": month, "year": year},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 200 or "data" not in payload:
        raise RuntimeError(f"Aladhan returned non-200 for {address} {year}-{month}: {payload}")
    return payload["data"]


def build_events_for_segment(seg: Segment, year: int, month: int) -> list[PrayerEvent]:
    """Aladhan is fetched for the *target* year/month only.

    Adjacent months are deliberately skipped: emitting (say) April-30 events
    while populating May is surprising. Anything that spills past the target
    month gets picked up by the next month's run.
    """
    seg_tz = ZoneInfo(seg.location.tz)
    data = fetch_aladhan_month(seg.location.address, year, month)

    events: list[PrayerEvent] = []
    for day in data:
        date_str = day["date"]["gregorian"]["date"]
        d = datetime.strptime(date_str, "%d-%m-%Y").date()
        is_friday = d.weekday() == 4
        for prayer in PRAYERS_TO_EMIT:
            t_str = day["timings"][prayer].split(" ")[0]
            hh, mm = map(int, t_str.split(":"))
            local_dt = datetime(d.year, d.month, d.day, hh, mm, tzinfo=seg_tz)
            utc_dt = local_dt.astimezone(timezone.utc)
            if utc_dt < seg.start_utc or utc_dt >= seg.end_utc:
                continue
            title = FRIDAY_DHUHR_TITLE if (prayer == "Dhuhr" and is_friday) else prayer
            events.append(PrayerEvent(
                title=title,
                when_local=local_dt.replace(tzinfo=None),
                tz=seg.location.tz,
            ))
    return events


def wipe_month(svc, calendar_id: str, year: int, month: int) -> int:
    """Delete prayer-titled events whose start is within the target month."""
    days_in_month = calendar.monthrange(year, month)[1]
    range_start = datetime(year, month, 1, tzinfo=timezone.utc) - timedelta(days=1)
    range_end = datetime(year, month, days_in_month, 23, 59, 59, tzinfo=timezone.utc) + timedelta(days=2)

    target_month_first = datetime(year, month, 1)  # naive, compared in event-local TZ
    target_month_last = datetime(year, month, days_in_month, 23, 59, 59)

    deleted = 0
    page_token = None
    while True:
        resp = svc.events().list(
            calendarId=calendar_id,
            timeMin=_to_rfc3339(range_start),
            timeMax=_to_rfc3339(range_end),
            singleEvents=True,
            orderBy="startTime",
            pageToken=page_token,
            maxResults=2500,
        ).execute()
        for ev in resp.get("items", []):
            if (ev.get("summary") or "") not in ALL_PRAYER_TITLES:
                continue
            iso = ev.get("start", {}).get("dateTime")
            if not iso:
                continue
            ev_dt = datetime.fromisoformat(iso)
            ev_local_naive = ev_dt.replace(tzinfo=None)
            if not (target_month_first <= ev_local_naive <= target_month_last):
                continue
            try:
                svc.events().delete(calendarId=calendar_id, eventId=ev["id"]).execute()
                deleted += 1
            except HttpError as e:
                print(f"[warn] failed to delete {ev['id']}: {e}", file=sys.stderr)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return deleted


def insert_events(svc, calendar_id: str, events: Iterable[PrayerEvent]) -> int:
    inserted = 0
    for ev in events:
        body = {
            "summary": ev.title,
            "start": {"dateTime": ev.when_local.isoformat(timespec="seconds"), "timeZone": ev.tz},
            "end":   {"dateTime": ev.when_local.isoformat(timespec="seconds"), "timeZone": ev.tz},
            "transparency": "transparent",
        }
        svc.events().insert(calendarId=calendar_id, body=body).execute()
        inserted += 1
    return inserted


def main() -> int:
    today = date.today()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=today.year)
    parser.add_argument("--month", type=int, default=today.month)
    parser.add_argument("--address", default=DEFAULT_ADDRESS,
                        help="Default home address (Aladhan-compatible). Used when not traveling.")
    parser.add_argument("--tz", default=DEFAULT_TZ, help="IANA TZ for the default address.")
    parser.add_argument("--prayer-calendar-id", default=DEFAULT_PRAYER_CALENDAR_ID)
    parser.add_argument("--travel-calendar-ids", default=",".join(DEFAULT_TRAVEL_CALENDAR_IDS),
                        help="Comma-separated list of calendar IDs to scan for flight events.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen, but don't touch the calendar.")
    args = parser.parse_args()

    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not all([refresh_token, client_id, client_secret]):
        print("Missing GOOGLE_REFRESH_TOKEN / GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET env vars.",
              file=sys.stderr)
        return 2

    svc = get_calendar_service(refresh_token, client_id, client_secret)

    days_in_month = calendar.monthrange(args.year, args.month)[1]
    month_start_utc = datetime(args.year, args.month, 1, tzinfo=timezone.utc)
    month_end_utc = datetime(args.year, args.month, days_in_month, 23, 59, 59, tzinfo=timezone.utc) + timedelta(seconds=1)

    # Look back 60 days so we can pick up a flight whose landing happened
    # before the start of the target month but still determines the location.
    lookback_start = month_start_utc - timedelta(days=60)

    print(f"== {args.year}-{args.month:02d} ==")
    travel_calendar_ids = [cid.strip() for cid in args.travel_calendar_ids.split(",") if cid.strip()]
    landings = fetch_landings(svc, travel_calendar_ids, lookback_start, month_end_utc)
    print(f"Found {len(landings)} landing(s) in [{lookback_start.date()}, {month_end_utc.date()})")
    for l in landings:
        marker = "  " if l.when_utc < month_start_utc else "* "
        print(f"  {marker}{l.when_utc.isoformat()} -> {l.location.label}")

    default_loc = Location(address=args.address, tz=args.tz, label=f"default ({args.address})")
    segments = build_segments(landings, default_loc, month_start_utc, month_end_utc)
    print(f"Built {len(segments)} segment(s):")
    for s in segments:
        print(f"  - {s.start_utc.isoformat()} -> {s.end_utc.isoformat()}  {s.location.label}")

    all_events: list[PrayerEvent] = []
    for seg in segments:
        all_events.extend(build_events_for_segment(seg, args.year, args.month))
    all_events.sort(key=lambda e: (e.when_local, e.title))
    print(f"Generated {len(all_events)} event(s) total.")

    if args.dry_run:
        for ev in all_events[:36]:
            print(f"  {ev.when_local.isoformat()} {ev.tz:24} {ev.title}")
        if len(all_events) > 36:
            print(f"  ... +{len(all_events) - 36} more")
        return 0

    print(f"Wiping existing prayer events for {args.year}-{args.month:02d}...")
    wiped = wipe_month(svc, args.prayer_calendar_id, args.year, args.month)
    print(f"  Deleted {wiped} event(s).")

    print(f"Inserting {len(all_events)} new event(s)...")
    inserted = insert_events(svc, args.prayer_calendar_id, all_events)
    print(f"  Inserted {inserted} event(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

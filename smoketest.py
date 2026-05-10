"""Local smoke test — exercises everything except Google Calendar reads/writes.

Synthesizes a landing list that mirrors the user's upcoming itinerary, builds
segments for May 2026, fetches real Aladhan data for each segment's location,
and prints the resulting events. No Google credentials required.
"""

from datetime import datetime, timedelta, timezone

import prayertimes as pt


def main():
    year, month = 2026, 5

    home = pt.Location(address=pt.DEFAULT_ADDRESS, tz=pt.DEFAULT_TZ, label="default (Richmond)")

    yvr = pt.airport_to_location("YVR")
    lhr = pt.airport_to_location("LHR")
    cai = pt.airport_to_location("CAI")
    jed = pt.airport_to_location("JED")
    print("airport lookups:")
    for code, loc in [("YVR", yvr), ("LHR", lhr), ("CAI", cai), ("JED", jed)]:
        print(f"  {code}: {loc}")

    # Synthetic itinerary: YVR -> LHR (lands 2026-05-16 11:00 BST),
    # LHR -> CAI (lands 2026-05-16 23:00 EET), CAI -> JED (lands 2026-06-01),
    # JED -> YVR (lands 2026-06-10).
    landings = [
        pt.Landing(
            when_utc=datetime(2026, 5, 16, 10, 0, tzinfo=timezone.utc),
            location=lhr,
        ),
        pt.Landing(
            when_utc=datetime(2026, 5, 16, 21, 0, tzinfo=timezone.utc),
            location=cai,
        ),
        pt.Landing(
            when_utc=datetime(2026, 6, 1, 5, 0, tzinfo=timezone.utc),
            location=jed,
        ),
    ]

    import calendar as cal
    days = cal.monthrange(year, month)[1]
    start_utc = datetime(year, month, 1, tzinfo=timezone.utc)
    end_utc = datetime(year, month, days, 23, 59, 59, tzinfo=timezone.utc) + timedelta(seconds=1)

    segments = pt.build_segments(landings, home, start_utc, end_utc)
    print(f"\n{len(segments)} segment(s) for {year}-{month:02d}:")
    for s in segments:
        print(f"  {s.start_utc.isoformat()} -> {s.end_utc.isoformat()}  {s.location.label}")

    all_events = []
    for seg in segments:
        evs = pt.build_events_for_segment(seg, year, month)
        all_events.extend(evs)
    all_events.sort(key=lambda e: (e.when_local, e.title))

    print(f"\n{len(all_events)} prayer event(s) total. First and last 14:")
    for ev in all_events[:14]:
        print(f"  {ev.when_local.isoformat()}  {ev.tz:24} {ev.title}")
    print("  ...")
    for ev in all_events[-14:]:
        print(f"  {ev.when_local.isoformat()}  {ev.tz:24} {ev.title}")

    # Quick sanity counts per TZ
    from collections import Counter
    by_tz = Counter(ev.tz for ev in all_events)
    print("\nEvents per TZ:")
    for tz, n in by_tz.most_common():
        print(f"  {tz:24} {n}")


if __name__ == "__main__":
    main()

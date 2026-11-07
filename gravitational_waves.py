"""Gravitational wave events, from GraceDB (LIGO/Virgo/KAGRA)."""

import urequests

from wifi import HEADERS

# Significant public alerts only (SIGNIF_LOCKED), not retracted ones (ADVNO).
# Each event weighs about 3 KB of JSON, read in one piece: 3 events keep it small.
URL = (
    "https://gracedb.ligo.org/api/superevents/?count=3"
    "&query=category%3A+Production+SIGNIF_LOCKED+%26+~ADVNO"
)


def fetch() -> list[str]:
    """Return the ids of the latest significant gravitational wave events, newest first."""
    r = urequests.get(URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        # json.load(r.raw) fails on an HTTPS stream ("stream operation not
        # supported"), so the whole answer is read first, then parsed.
        data = r.json()
        if "superevents" not in data:
            raise ValueError("unexpected response")
        return [event["superevent_id"] for event in data["superevents"]]
    finally:
        r.close()

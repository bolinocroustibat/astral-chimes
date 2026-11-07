"""Earthquakes in Japan, from the USGS catalog."""

import json

import urequests

from wifi import HEADERS

# The USGS lists no quakes below M4 in Japan. The box around the country
# also catches rare quakes off Taiwan, Korea and Sakhalin.
MIN_MAGNITUDE = 4
URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
    "&minlatitude=24&maxlatitude=46&minlongitude=122&maxlongitude=146"
    f"&minmagnitude={MIN_MAGNITUDE}&limit=5&orderby=time"
)


def fetch() -> list[str]:
    """Return the ids of the latest earthquakes in Japan, newest first."""
    r = urequests.get(URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        data = json.load(r.raw)  # parsed from the stream, the raw text is never kept
        if "features" not in data:
            raise ValueError("unexpected response")
        return [feature["id"] for feature in data["features"]]
    finally:
        r.close()

"""Confirmed supernovae, from the Transient Name Server (TNS)."""

import urequests

from wifi import HEADERS

URL = (
    "https://www.wis-tns.org/search?format=csv&num_page=20&classified_sne=1"
    "&discovered_period_value=30&discovered_period_units=days"
)


def read_lines(stream):
    """Yield the lines of a response, which has no readline() of its own.

    Reading small blocks keeps the CSV out of memory: it may not fit in it.
    """
    buffer = b""
    while True:
        block = stream.read(256)
        if not block:
            break
        lines = (buffer + block).split(b"\n")
        buffer = lines.pop()  # the last line may still be incomplete
        for line in lines:
            yield line
    if buffer:
        yield buffer


def fetch() -> list[str]:
    """Return the names of the latest confirmed supernovae, newest first."""
    r = urequests.get(URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        names = []
        for index, line in enumerate(read_lines(r.raw)):
            if index == 0:
                if not line.startswith(b'"ID"'):
                    raise ValueError("unexpected response")
                continue
            fields = line.split(b'","')
            if len(fields) > 1:
                names.append(fields[1].decode())
        return names
    finally:
        r.close()

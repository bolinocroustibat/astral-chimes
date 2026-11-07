import gc
import json
import time

import urequests
from machine import PWM, Pin

import wifi

REST_ANGLE = 0
STRIKE_ANGLE = 180
PAUSE = 0.3  # seconds: time spent at the strike position
STRIKE_GAP = 3  # seconds after each strike, long enough to count them by ear
TEST_GAP = 5  # extra seconds between the two servos on a test strike
TEST_DELAY = 2  # seconds between the button press and the first test strike
CHECK_INTERVAL = 300  # seconds between two checks of the catalogs
MAX_SEEN = 40  # names remembered, must stay above the page size of the URL
SUPERNOVA_URL = (
    "https://www.wis-tns.org/search?format=csv&num_page=20&classified_sne=1"
    "&discovered_period_value=30&discovered_period_units=days"
)
# Significant public alerts only (SIGNIF_LOCKED), not retracted ones (ADVNO).
# Each event weighs about 3 KB of JSON, so the page stays small.
GRAVITATIONAL_WAVE_URL = (
    "https://gracedb.ligo.org/api/superevents/?count=5"
    "&query=category%3A+Production+SIGNIF_LOCKED+%26+~ADVNO"
)
HEADERS = {"User-Agent": "astral-chimes/0.1 (personal project)"}

servo1 = PWM(Pin(13), freq=50)
servo2 = PWM(Pin(27), freq=50)
test_button = Pin(0, Pin.IN, Pin.PULL_UP)  # BOOT button, reads 0 when pressed


def set_angle(servo: PWM, angle: int) -> None:
    us = 500 + (angle / 180) * 1900  # 0 deg = 500 us, 180 deg = 2400 us
    servo.duty_ns(int(us * 1000))


def strike(servo: PWM, times: int = 1) -> None:
    for _ in range(times):
        set_angle(servo, STRIKE_ANGLE)
        time.sleep(PAUSE)
        set_angle(servo, REST_ANGLE)
        time.sleep(STRIKE_GAP)


def wait_and_watch_button(seconds: int) -> None:
    """Sleep for the given time, striking both servos when the test button is pressed.

    The button is polled, not handled by an interrupt: an interrupt handler
    must not sleep, and the strike needs to.
    """
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if test_button.value() == 0:
            print("test strike")
            time.sleep(TEST_DELAY)
            strike(servo1)
            time.sleep(TEST_GAP)
            strike(servo2)
        time.sleep_ms(50)


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


def fetch_supernovae() -> list[str]:
    """Return the names of the latest confirmed supernovae, newest first."""
    r = urequests.get(SUPERNOVA_URL, headers=HEADERS)
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


def fetch_gravitational_waves() -> list[str]:
    """Return the ids of the latest significant gravitational wave events, newest first."""
    r = urequests.get(GRAVITATIONAL_WAVE_URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        data = json.load(r.raw)  # parsed from the stream, the raw text is never kept
        if "superevents" not in data:
            raise ValueError("unexpected response")
        return [event["superevent_id"] for event in data["superevents"]]
    finally:
        r.close()


def find_new(names: list[str], seen: list[str] | None) -> list[str]:
    """Return the names that should ring.

    The first pass (seen is None) rings nothing: it only sets the reference.

    A list made only of unknown names rings nothing either. It points to an
    anomaly, like a changed response format, and not to real events: without
    this guard, a list that keeps changing could ring at every check, forever.
    """
    if seen is None:
        return []
    new = [n for n in names if n not in seen]
    if len(new) == len(names):
        print("anomaly: only unknown names, ignored")
        return []
    return new


def remember(names: list[str], seen: list[str] | None) -> list[str]:
    """Return the updated seen list, newest first, capped at MAX_SEEN names."""
    older = [n for n in (seen or []) if n not in names]
    return (names + older)[:MAX_SEEN]


def check(label: str, fetch, seen: list[str] | None, servo: PWM) -> list[str] | None:
    """Fetch the latest events, strike once per new one, return the updated seen list."""
    try:
        gc.collect()  # the TLS handshake needs a large block of free memory
        names = fetch()
        print(label, "names:", len(names))
        if not names:  # an empty answer must not replace the reference
            return seen
        new = find_new(names, seen)
        seen = remember(names, seen)  # before ringing, so nothing rings twice
        for name in new:
            print(label, "new:", name)
            strike(servo)
    except Exception as e:
        print(label, "error:", e)
    return seen


set_angle(servo1, REST_ANGLE)
set_angle(servo2, REST_ANGLE)
time.sleep(1)

wlan = wifi.connect()
seen_supernovae = None
seen_gravitational_waves = None

while True:
    if not wlan.isconnected():
        wlan = wifi.connect()
    seen_supernovae = check("supernova", fetch_supernovae, seen_supernovae, servo1)
    seen_gravitational_waves = check(
        "gravitational wave", fetch_gravitational_waves, seen_gravitational_waves, servo2
    )
    wait_and_watch_button(CHECK_INTERVAL)

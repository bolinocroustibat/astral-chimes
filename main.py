import gc
import json
import socket
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
# Earthquakes in and around Japan, from the USGS catalog, which lists none
# below M4 there. The box also catches rare quakes off Taiwan, Korea and Sakhalin.
EARTHQUAKE_MIN_MAGNITUDE = 4
EARTHQUAKE_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
    "&minlatitude=24&maxlatitude=46&minlongitude=122&maxlongitude=146"
    f"&minmagnitude={EARTHQUAKE_MIN_MAGNITUDE}&limit=5&orderby=time"
)
HEADERS = {"User-Agent": "astral-chimes/0.1 (personal project)"}
HTTP_PORT = 80
MAX_HTTP_TIMES = 5  # strikes allowed in one HTTP call

servo1 = PWM(Pin(13), freq=50)
servo2 = PWM(Pin(27), freq=50)
# Earthquake chime, disabled for now. To enable it, uncomment the lines that
# use servo3 or seen_earthquakes, and the TEST_GAP sleep just before strike(servo3).
# servo3 = PWM(Pin(26), freq=50)
test_button = Pin(0, Pin.IN, Pin.PULL_UP)  # BOOT button, reads 0 when pressed
SERVOS = {  # numbers used by the HTTP call
    1: servo1,
    2: servo2,
    # 3: servo3,
}


def set_angle(servo: PWM, angle: int) -> None:
    us = 500 + (angle / 180) * 1900  # 0 deg = 500 us, 180 deg = 2400 us
    servo.duty_ns(int(us * 1000))


def strike(servo: PWM, times: int = 1) -> None:
    for _ in range(times):
        set_angle(servo, STRIKE_ANGLE)
        time.sleep(PAUSE)
        set_angle(servo, REST_ANGLE)
        time.sleep(STRIKE_GAP)


def parse_strike(request_line: str) -> tuple[str, int | None, int]:
    """Read a request line like "GET /strike?servo=1&times=2 HTTP/1.1".

    Return the HTTP status line, then the servo number and the number of
    strikes. The servo number is None when nothing should ring.
    """
    parts = request_line.split()
    if len(parts) < 2 or parts[0] != "GET":
        return "404 Not Found", None, 0
    path_and_query = parts[1].split("?", 1)
    if path_and_query[0] != "/strike":
        return "404 Not Found", None, 0
    params = {}
    if len(path_and_query) == 2:
        for pair in path_and_query[1].split("&"):
            if "=" in pair:
                key, value = pair.split("=", 1)
                params[key] = value
    try:
        servo = int(params["servo"])
        times = int(params.get("times", "1"))
    except (KeyError, ValueError):
        return "400 Bad Request", None, 0
    if servo not in SERVOS or not 1 <= times <= MAX_HTTP_TIMES:
        return "400 Bad Request", None, 0
    return "200 OK", servo, times


def start_http_server() -> socket.socket:
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", HTTP_PORT))
    server.listen(2)
    server.setblocking(False)  # accept() returns at once when nobody is calling
    return server


def handle_http(server: socket.socket) -> None:
    """Answer one pending HTTP call, if any, then strike the requested servo."""
    try:
        client, _ = server.accept()
    except OSError:  # nobody is calling
        return
    servo, times = None, 0
    try:
        client.settimeout(2)
        request_line = client.readline().decode()
        # Read the headers too: closing with unread data would reset the connection.
        for _ in range(30):
            line = client.readline()
            if not line or line == b"\r\n":
                break
        status, servo, times = parse_strike(request_line)
        body = "ok" if servo else "usage: /strike?servo=N&times=K"
        client.send(f"HTTP/1.0 {status}\r\nContent-Type: text/plain\r\n\r\n{body}\n".encode())
    except Exception as e:
        print("http error:", e)
    finally:
        client.close()  # before striking, so the caller gets its answer at once
    if servo:
        print("http strike", servo, times)
        strike(SERVOS[servo], times)


def wait_and_watch_inputs(seconds: int, server: socket.socket) -> None:
    """Sleep for the given time, while watching the test button and HTTP calls.

    A press on the button strikes all servos. An HTTP call strikes the servo
    it asks for. Both are polled, not handled by an interrupt:
    an interrupt handler must not sleep, and the strike needs to.
    """
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        handle_http(server)
        if test_button.value() == 0:
            print("test strike")
            time.sleep(TEST_DELAY)
            strike(servo1)
            time.sleep(TEST_GAP)
            strike(servo2)
            # time.sleep(TEST_GAP)
            # strike(servo3)
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


def fetch_earthquakes() -> list[str]:
    """Return the ids of the latest earthquakes in Japan, newest first."""
    r = urequests.get(EARTHQUAKE_URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        data = json.load(r.raw)  # parsed from the stream, the raw text is never kept
        if "features" not in data:
            raise ValueError("unexpected response")
        return [feature["id"] for feature in data["features"]]
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
# set_angle(servo3, REST_ANGLE)
time.sleep(1)

wlan = wifi.connect()
server = start_http_server()
seen_supernovae = None
seen_gravitational_waves = None
# seen_earthquakes = None

while True:
    if not wlan.isconnected():
        wlan = wifi.connect()
    seen_supernovae = check("supernova", fetch_supernovae, seen_supernovae, servo1)
    seen_gravitational_waves = check(
        "gravitational wave", fetch_gravitational_waves, seen_gravitational_waves, servo2
    )
    # seen_earthquakes = check("earthquake", fetch_earthquakes, seen_earthquakes, servo3)
    wait_and_watch_inputs(CHECK_INTERVAL, server)

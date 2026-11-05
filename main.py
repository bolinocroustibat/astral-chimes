import time

import urequests
from machine import PWM, Pin

import wifi

REST_ANGLE = 0
STRIKE_ANGLE = 180
PAUSE = 0.3  # seconds: time spent at the strike position, and time to return
CHECK_INTERVAL = 300  # seconds between two checks of the TNS catalog
MAX_SEEN = 40  # names remembered, must stay above the page size of the URL
URL = (
    "https://www.wis-tns.org/search?format=csv&num_page=20&classified_sne=1"
    "&discovered_period_value=30&discovered_period_units=days"
)
HEADERS = {"User-Agent": "astral-chimes/0.1 (personal project)"}

servo1 = PWM(Pin(13), freq=50)
servo2 = PWM(Pin(27), freq=50)


def set_angle(servo: PWM, angle: int) -> None:
    us = 500 + (angle / 180) * 1900  # 0 deg = 500 us, 180 deg = 2400 us
    servo.duty_ns(int(us * 1000))


def strike(servo: PWM, times: int = 1) -> None:
    for _ in range(times):
        set_angle(servo, STRIKE_ANGLE)
        time.sleep(PAUSE)
        set_angle(servo, REST_ANGLE)
        time.sleep(PAUSE)


def fetch_names() -> list[str]:
    """Return the names of the latest confirmed supernovae, newest first."""
    r = urequests.get(URL, headers=HEADERS)
    try:
        if r.status_code != 200:
            raise ValueError(f"http {r.status_code}")
        if not r.raw.readline().startswith(b'"ID"'):
            raise ValueError("unexpected response")
        names = []
        while True:  # line by line: the whole CSV may not fit in memory
            line = r.raw.readline()
            if not line:
                return names
            fields = line.split(b'","')
            if len(fields) > 1:
                names.append(fields[1].decode())
    finally:
        r.close()


set_angle(servo1, REST_ANGLE)
set_angle(servo2, REST_ANGLE)
time.sleep(1)

wlan = wifi.connect()
seen = None

while True:
    if not wlan.isconnected():
        wlan = wifi.connect()
    try:
        names = fetch_names()
        print("names:", len(names))
        if names:  # an empty answer must not replace the reference
            new = [] if seen is None else [n for n in names if n not in seen]
            # the first pass only memorizes the current position
            seen = (names + [n for n in (seen or []) if n not in names])[:MAX_SEEN]

            for name in new[:3]:  # at most 3 strikes per request
                print("supernova:", name)
                strike(servo1)
    except Exception as e:
        print("error:", e)
    time.sleep(CHECK_INTERVAL)

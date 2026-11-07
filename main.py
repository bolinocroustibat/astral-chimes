import gc
import time

from machine import PWM

import gravitational_waves
import supernovae
import wifi
from button import handle_button
from http_server import handle_http, start_http_server
from servos import REST_ANGLE, SERVOS, servo1, servo2, set_angle, strike

# Earthquake chime, disabled for now. To enable it, uncomment servo3 in
# servos.py, then here the lines that use earthquakes, servo3 or seen_earthquakes.
# import earthquakes
# from servos import servo3

CHECK_INTERVAL = 300  # seconds between two checks of the catalogs
MAX_SEEN = 40  # names remembered, must stay above the page size of each catalog


def wait_and_watch_inputs(seconds: int, server) -> None:
    """Sleep for the given time, while watching the test button and HTTP calls.

    A press on the button strikes all servos. An HTTP call strikes the servo
    it asks for. Both are polled, not handled by an interrupt:
    an interrupt handler must not sleep, and the strike needs to.
    """
    deadline = time.ticks_add(time.ticks_ms(), seconds * 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        handle_http(server)
        handle_button()
        time.sleep_ms(50)


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


for servo in SERVOS.values():
    set_angle(servo, REST_ANGLE)
time.sleep(1)

wlan = wifi.connect()
server = start_http_server()
seen_supernovae = None
seen_gravitational_waves = None
# seen_earthquakes = None

while True:
    if not wlan.isconnected():
        wlan = wifi.connect()
    seen_supernovae = check("supernova", supernovae.fetch, seen_supernovae, servo1)
    seen_gravitational_waves = check(
        "gravitational wave", gravitational_waves.fetch, seen_gravitational_waves, servo2
    )
    # seen_earthquakes = check("earthquake", earthquakes.fetch, seen_earthquakes, servo3)
    wait_and_watch_inputs(CHECK_INTERVAL, server)

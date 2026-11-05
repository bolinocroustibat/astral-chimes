import time

import urequests
from machine import PWM, Pin

import wifi

REST_ANGLE = 0
STRIKE_ANGLE = 180
PAUSE = 0.3  # seconds: time spent at the strike position, and time to return
CHECK_INTERVAL = 4
URL = (
    "https://en.wikipedia.org/w/api.php?action=query&list=recentchanges"
    "&rctype=edit&rcprop=ids|title&rclimit=10&format=json"
)
HEADERS = {"User-Agent": "esp32-chime-test/0.1 (personal project)"}

servo = PWM(Pin(13), freq=50)


def set_angle(angle):
    us = 500 + (angle / 180) * 1900  # 0 deg = 500 us, 180 deg = 2400 us
    servo.duty_ns(int(us * 1000))


def strike():
    set_angle(STRIKE_ANGLE)
    time.sleep(PAUSE)
    set_angle(REST_ANGLE)
    time.sleep(PAUSE)  # wait until it is back at rest


set_angle(REST_ANGLE)
time.sleep(1)

wlan = wifi.connect()
last_rcid = 0

while True:
    if not wlan.isconnected():
        wlan = wifi.connect()
    try:
        r = urequests.get(URL, headers=HEADERS)
        changes = r.json()["query"]["recentchanges"]
        r.close()

        new = [c for c in changes if c["rcid"] > last_rcid]
        if last_rcid == 0:
            new = []  # first pass only memorizes the current position
        if changes:
            last_rcid = max(c["rcid"] for c in changes)

        for c in new[:3]:  # at most 3 strikes per request
            print("edit:", c["title"])
            strike()
    except Exception as e:
        print("error:", e)
    time.sleep(CHECK_INTERVAL)

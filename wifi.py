import time
from secrets import PASSWORD, SSID

import network


def connect(timeout: int = 20) -> network.WLAN:
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(SSID, PASSWORD)
        for _ in range(timeout):
            if wlan.isconnected():
                break
            time.sleep(1)
    if wlan.isconnected():
        print("wifi ok :", wlan.ifconfig()[0])
    else:
        print("wifi failed")
    return wlan

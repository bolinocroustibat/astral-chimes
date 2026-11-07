import time

from machine import PWM, Pin

REST_ANGLE = 0
STRIKE_ANGLE = 180
PAUSE = 0.3  # seconds: time spent at the strike position
STRIKE_GAP = 3  # seconds after each strike, long enough to count them by ear

servo1 = PWM(Pin(13), freq=50)  # supernovae
servo2 = PWM(Pin(27), freq=50)  # gravitational waves
# servo3 = PWM(Pin(26), freq=50)  # earthquakes, disabled for now
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

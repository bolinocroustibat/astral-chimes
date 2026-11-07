import time

from machine import PWM, Pin

REST_ANGLE = 0
STRIKE_ANGLE = 180
PAUSE = 0.3  # seconds: time spent at the strike position
# The strike stays fast so the chime rings well, but the way back is slow:
# a sudden return is what makes the servo loud.
RETURN_DURATION = 1.5  # seconds to go back to rest
STEP_MS = 20  # one step per period of the servo signal, finer would be useless
STRIKE_GAP = 3  # seconds after each strike, long enough to count them by ear

servo1 = PWM(Pin(13), freq=50)  # supernovae
servo2 = PWM(Pin(27), freq=50)  # gravitational waves
# servo3 = PWM(Pin(26), freq=50)  # earthquakes, disabled for now
SERVOS = {  # numbers used by the HTTP call
    1: servo1,
    2: servo2,
    # 3: servo3,
}


def set_angle(servo: PWM, angle: float) -> None:
    us = 500 + (angle / 180) * 1900  # 0 deg = 500 us, 180 deg = 2400 us
    servo.duty_ns(int(us * 1000))


def move_slowly(servo: PWM, start: int, end: int) -> None:
    """Go from one angle to another in small steps, over RETURN_DURATION."""
    steps = max(1, int(RETURN_DURATION * 1000 / STEP_MS))
    for step in range(1, steps + 1):
        set_angle(servo, start + (end - start) * step / steps)
        time.sleep_ms(STEP_MS)


def strike(servo: PWM, times: int = 1) -> None:
    for _ in range(times):
        set_angle(servo, STRIKE_ANGLE)
        time.sleep(PAUSE)
        move_slowly(servo, STRIKE_ANGLE, REST_ANGLE)
        time.sleep(STRIKE_GAP)

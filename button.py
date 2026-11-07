import time

from machine import Pin

from servos import SERVOS, strike

TEST_DELAY = 2  # seconds between the button press and the first test strike
TEST_GAP = 5  # extra seconds between two servos on a test strike

test_button = Pin(0, Pin.IN, Pin.PULL_UP)  # BOOT button, reads 0 when pressed


def handle_button() -> None:
    """If the test button is pressed, strike every servo, one after the other."""
    if test_button.value() != 0:
        return
    print("test strike")
    time.sleep(TEST_DELAY)
    for index, servo in enumerate(SERVOS.values()):
        if index > 0:
            time.sleep(TEST_GAP)
        strike(servo)

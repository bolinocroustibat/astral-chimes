# Astral Chimes

Ring a chime for each new confirmed supernova explosion in the universe, and a second one for each new gravitational wave event. MicroPython project for ESP32 chip. Supernovae come from the [Transient Name Server](https://www.wis-tns.org/), gravitational waves from [GraceDB](https://gracedb.ligo.org/) (LIGO/Virgo/KAGRA).

Only significant, non-retracted gravitational wave alerts ring. There are about 1 to 3 per week while the detectors are observing, and none between observing runs.

Both catalogs are checked every 5 minutes. The first check after boot only memorizes the current lists, so nothing rings until a new event is published.

## Flash the firmware

Download the latest `.bin` from [MicroPython for ESP32](https://micropython.org/download/ESP32_GENERIC/), find the board's port with `ls /dev/cu.*` (e.g. `/dev/cu.usbserial-0001`), then:

```bash
uvx esptool --port /dev/cu.usbserial-0001 erase-flash
uvx esptool --port /dev/cu.usbserial-0001 --baud 460800 write-flash 0x1000 ESP32_GENERIC-*.bin
```

Tested with MicroPython v1.29.0.

## Setup

Create `secrets.py` (gitignored):

```python
SSID = "your-network"
PASSWORD = "your-password"
```

Connect the supernova servo signal wire to GPIO 13 and the gravitational wave servo to GPIO 27. Power the servos from a separate supply sharing a common ground with the board, as their current peaks can reset the ESP32.

Then copy `main.py`, `wifi.py` and `secrets.py` to the board with [Thonny](https://thonny.org/) (select the MicroPython ESP32 interpreter, then upload from the Files view), or with `mpremote`:

```bash
mpremote cp main.py wifi.py secrets.py :
```

## Test strike

Press the BOOT button (GPIO 0, next to the USB port) to strike both servos, one after the other. It works at any time between two checks of the catalogs. Do not hold it while the board boots or resets: the chip would start in flashing mode instead of running `main.py`.

## TODO

Ring a third chime for another kind of event from TNS. Ideas, with rough orders of magnitude (not checked against TNS):

- **New unclassified discoveries (AT)**: ~20,000 per year, several dozen per day. Likely to ring almost nonstop.
- **Bright supernovae**: the frequency depends on the magnitude threshold, a few dozen per year below 16, a few per year below 14.
- **Tidal disruption events (TDE)**: a few dozen per year, about one strike a week.
- **Novae**: a few dozen per year.
- **Kilonovae**: only one observed for sure (2017), so it would almost never ring.

This needs another URL, servo and `seen` list. `check`, `find_new` and `remember` can be reused as they are.

Other sources, beyond TNS (to check before use):

- **[NOAA SWPC](https://services.swpc.noaa.gov/)**: space weather in JSON, with no key, such as solar flares and geomagnetic storms (Kp index). A storm can mean visible aurorae. The frequency follows the solar cycle.

It returns JSON, like GraceDB, so `fetch_gravitational_waves` is a good model for its own `fetch` function.

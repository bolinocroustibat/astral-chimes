# Astral Chimes

Ring a chime for each new confirmed supernova explosion in the universe. MicroPython project for ESP32 chip. Supernovae come from the [Transient Name Server](https://www.wis-tns.org/).

## Flash the firmware

Download the latest `.bin` from [MicroPython for ESP32](https://micropython.org/download/ESP32_GENERIC/), find the board's port with `ls /dev/cu.*` (e.g. `/dev/cu.usbserial-0001`), then:

```bash
uvx esptool --port /dev/cu.usbserial-0001 erase-flash
uvx esptool --port /dev/cu.usbserial-0001 --baud 460800 write-flash 0x1000 ESP32_GENERIC-*.bin
```

## Setup

Create `secrets.py` (gitignored):

```python
SSID = "your-network"
PASSWORD = "your-password"
```

Connect the servo signal wire to GPIO 13, then copy `main.py`, `wifi.py` and `secrets.py` to the board with [Thonny](https://thonny.org/) (select the MicroPython ESP32 interpreter, then upload from the Files view), or with `mpremote`:

```bash
mpremote cp main.py wifi.py secrets.py :
```

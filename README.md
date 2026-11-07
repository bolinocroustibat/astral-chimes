# 🔔 Astral Chimes

Ring a chime for each new confirmed supernova explosion in the universe, and a second one for each new gravitational wave event. Rust project for ESP32 chip, with [`esp-idf-svc`](https://github.com/esp-rs/esp-idf-svc) (the Rust standard library on top of ESP-IDF). Supernovae come from the [Transient Name Server](https://www.wis-tns.org/), gravitational waves from [GraceDB](https://gracedb.ligo.org/) (LIGO/Virgo/KAGRA).

Only significant, non-retracted gravitational wave alerts ring. There are about 1 to 3 per week while the detectors are observing, and none between observing runs.

All catalogs are checked every 5 minutes. The first check after boot only memorizes the current lists, so nothing rings until a new event is published.

## 🔧 Toolchain

The ESP32 is an Xtensa chip, which needs the Rust fork installed by `espup`:

```bash
cargo install espup ldproxy espflash
espup install
. ~/export-esp.sh  # in every new shell, or add it to your shell profile
```

The first build also downloads ESP-IDF (into `.embuild/`, a few GB) and takes a while.

## 🔌 Wiring

Connect the supernova servo signal wire to GPIO 13 and the gravitational wave servo to GPIO 27. Power the servos from a separate supply sharing a common ground with the board, as their current peaks can reset the ESP32. If they share the board's VIN pin instead, put a capacitor of 1000 µF or more (at least 10 V) between VIN and GND, close to the servos, minding its polarity.

## ⚡ Build and flash

Copy `secrets.rs.example` to `src/secrets.rs` (gitignored) and fill it in. Then, with the board plugged in:

```bash
cargo run --release
```

This builds, flashes the board (`espflash` finds its port) and shows its output (Ctrl-C to quit). There is no need to flash MicroPython first: the program replaces whatever was on the board.

## 🧪 Test strike

Press the BOOT button (GPIO 0, next to the USB port) to strike all servos, one after the other. It works at any time between two checks of the catalogs. Do not hold it while the board boots or resets: the chip would start in flashing mode instead of running the program.

## 🌐 Ring over HTTP

From any device on the local network, call `/strike` with the servo number (1 = supernova, 2 = gravitational wave) and, optionally, the number of strikes (1 to 5):

```bash
curl "http://astral-chimes.local/strike?servo=1"
curl "http://astral-chimes.local/strike?servo=2&times=3"
```

If `astral-chimes.local` does not resolve, use the IP address printed by `wifi ok` at boot, and reserve it in the router so it does not change.

Calls are answered at once, even during a check of the catalogs or a strike. The strikes they ask for are then done in order. There is no authentication, so anyone on the local network can ring.

## ✅ Tests

The logic that does not touch the hardware (which names ring, the HTTP query, the TNS CSV) is in `src/logic.rs`, and can be tested on the computer:

```bash
rustc --edition 2021 --test src/logic.rs -o /tmp/logic-tests && /tmp/logic-tests
```

## 📝 TODO

Ring a third chime for another kind of event from TNS. Ideas, with rough orders of magnitude (not checked against TNS):

- **New unclassified discoveries (AT)**: ~20,000 per year, several dozen per day. Likely to ring almost nonstop.
- **Bright supernovae**: the frequency depends on the magnitude threshold, a few dozen per year below 16, a few per year below 14.
- **Tidal disruption events (TDE)**: a few dozen per year, about one strike a week.
- **Novae**: a few dozen per year.
- **Kilonovae**: only one observed for sure (2017), so it would almost never ring.

This needs a `fetch` function with its own URL in `src/catalogs.rs`, plus a servo and a `seen` list in `src/main.rs`. `check`, `find_new` and `remember` can be reused as they are.

Other sources, beyond TNS (to check before use):

- **[NOAA SWPC](https://services.swpc.noaa.gov/)**: space weather in JSON, with no key, such as solar flares and geomagnetic storms (Kp index). A storm can mean visible aurorae. The frequency follows the solar cycle.

It returns JSON, like GraceDB, so `fetch_gravitational_waves` is a good model for it.

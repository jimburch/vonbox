# Claude Code instructions — NFC Movie Box

This is the always-on context. The full project plan, rationale, and lessons learned live in `spec.md` — read it when you need depth on any decision or want to know what comes after the current step. This file is the running, terse version.

## What this is

A device that lets a 3.5-year-old start movies on the living room TV by **tapping** an NFC-tagged object (card, coin, mini character — form factor TBD) against a small box. NFC identifies the tag; Home Assistant translates that into Apple TV + Plex commands.

The interaction model is **tap-and-go**, not continuous-presence-on-the-box like a Tonie Box. The tag is brought to the reader, fires once, and then goes away. The movie keeps playing whether the tag is nearby or not. **v1 has no on-box controls beyond the tap** — the volume knob and play/pause button were dropped to keep the first build simple; volume and pause are the Siri Remote's job. See [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md) (interaction model) and [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md) (v1 scope).

The user is the dad building this for his son Von.

## Current state

**Phase 1 ✅ done** — Apple TV + Plex pipeline working end-to-end via HA webhooks. A single `curl` from cold sleep wakes TV + soundbar + Apple TV, opens Plex, plays a chosen movie.

**Phase 2 ✅ done** — Pico detects a tag tap and prints the UID *once per tap* over USB serial.

1. ✅ **Pico alive** — MicroPython v1.28.0 flashed, MicroPico connected, `blink.py` toggles the onboard LED.
2. ✅ **PN532 wired and talking** — wired over I2C on GP4 (SDA) / GP5 (SCL), DIP switches set to I2C (`SEL0=OFF, SEL1=ON`), responds at `0x24`, identifies as PN532 firmware 1.6 via raw `GetFirmwareVersion`. Bench scripts in `test/i2c_scan.py` and `test/nfc_firmware_test.py`.
3. ✅ **Single-shot tap detection** — Polls PN532 at ~10Hz; prints `TAPPED: <UID>` exactly once per tap; suppresses re-fires until the tag is absent ≥2s. Confirmed with NTAG215 sticker `04462765C82A81`. Inline driver in `test/nfc_tap_test.py` (will extract to `lib/pn532.py` during Phase 3).

**Phase 3 ▶️ in progress** — Pico ↔ HA via MQTT.

1. ✅ **Mosquitto reachable from the laptop.** Broker on Synology at `192.168.0.123:1883` (Docker container). User `vonbox` created via `mosquitto_passwd`. `mosquitto_pub`/`mosquitto_sub` work end-to-end from Mac.
2. ✅ **Pico on Wi-Fi.** Pico associates with SSID `Jabby`, lease `192.168.0.80`, RSSI `-42 dBm`. Credentials in gitignored `secrets.py`. Test script: `test/wifi_test.py`.
3. ✅ **Pico → MQTT broker.** `test/mqtt_hello_test.py` publishes a heartbeat to `test/hello` every 5s; laptop `mosquitto_sub` receives each message. `umqtt.simple` is *not* frozen into the official `RPI_PICO2_W` build — install once via `test/install_umqtt.py` (calls `mip.install("umqtt.simple")`, writes to `/lib/umqtt/simple.mpy`).
4. ✅ **`lib/pn532.py` + orchestrator.** Inline driver extracted to `lib/pn532.py` (uploaded to Pico flash); `test/nfc_to_mqtt_test.py` runs the polling + MQTT loop and publishes `{"uid": "<HEX>"}` to `vonbox/nfc/tapped`. Edge-trigger + 2s-absence cooldown preserved. Verified end-to-end with NTAG215 `04462765C82A81`.
5. ▶️ **HA UID→rating-key automation.** First true tap-to-play moment. *(currently here)*
6. **HA → Pico state sync.** `vonbox/state` drives Pico's session-active tracking and (eventually) the LED ring.

Topic prefix: all project topics use `vonbox/...` (matches the repo name and the Mosquitto user). The MQTT user is `vonbox`; the password lives in `secrets.py` on the Pico and in the HA MQTT integration config.

**Phase 4 ▶️ output hardware bench-tested early** — both v1 *output* devices are on the breadboard and verified with standalone scripts, ahead of the remaining Phase 3 integration and the full feedback vocabulary. (Pins for both are in the **Pico pin allocation** table below.)

1. ✅ **LED ring lit and animating.** 24-px WS2812 ring, `DIN`→GP28, `PWR`→VSYS, `GND`→shared rail. `test/led_ring_test.py` cycles solid colors (white/yellow/red/blue) plus wipe/comet/rainbow/chase/breathe — all 24 pixels correct, no flicker. Brightness is capped at 25% in firmware (`BRIGHTNESS = 0.25`) as a hard current-safety limit; all-white at full tilt (~1.4 A) exceeds what VSYS/USB can supply.
2. ✅ **Buzzer playing tones.** KY-006 passive piezo, `S`→GP22, `−`→GND (middle header pin unused), driven directly by PWM — no transistor or VCC. `test/buzzer_test.py` auditions a menu of success / error / neutral cues plus a 150 Hz→4 kHz range sweep. Which cues become `play_success()` / `play_error()` is still TBD.
3. **OLED** — not yet wired; shares the PN532 I2C bus (GP4/GP5). The remaining Phase 4 hardware.

Still Phase-4-pending: per-state LED animations + buzzer cues bound to `vonbox/state`, and the OLED.

## Project structure

```
moviebox-pico/
├── CLAUDE.md       # This file
├── spec.md         # Full project plan + lessons learned (source of truth)
├── .vscode/        # MicroPico-generated config
├── lib/            # MicroPython libraries copied to Pico (e.g. pn532.py) — created when needed
├── secrets.py      # WiFi/MQTT credentials — gitignored, never commit
└── *.py            # Test scripts (blink.py, nfc_test.py, etc.) — run ephemerally during dev
```

`main.py` doesn't exist yet and won't until late Phase 4 / Phase 5 when the box runs unattended. During development everything is run as ephemeral one-off scripts via MicroPico's "Run current file on Pico".

## Development environment

- **Editor:** VS Code with the **MicroPico** extension (publisher: `paulober`).
- **Board:** Raspberry Pi Pico 2 WH — RP2350 chip, WiFi via CYW43, pre-soldered headers.
- **Language:** MicroPython, latest stable `RPI_PICO2_W` build from micropython.org.
- **Connection:** USB serial — Pico shows up as `/dev/cu.usbmodem*` on macOS, `/dev/ttyACM*` on Linux.

Common MicroPico commands (Cmd+Shift+P):

- **`MicroPico: Run current file on Pico`** — ephemeral run, doesn't persist across reboots. Default during Phase 2.
- **`MicroPico: Upload project to Pico`** — writes files to the Pico's flash filesystem. Files survive power cycles; a file named `main.py` auto-runs on boot. Don't suggest using this until the box is in its final form.
- **`MicroPico: Stop execution`** — Ctrl-C equivalent.
- **`MicroPico: Open REPL`** — interactive `>>>` prompt over USB serial. Useful for poking at hardware state.

## Hardware

| Component | Notes |
|---|---|
| Raspberry Pi Pico 2 WH | RP2350, WiFi/BT, onboard LED routed through the CYW43 chip (not a regular GPIO — see gotchas) |
| HiLetgo PN532 V3 NFC module (red PCB) | DIP switches on back select interface. Default ships in HSU/UART; **must be set to I2C** before wiring |
| NTAG215 stickers | The PN532 kit's included Mifare Classic cards work for initial bench testing |
| WS2812 NeoPixel ring, 24 LEDs (DIYMalls) | Phase 4. Power from **VSYS (5V)**, not 3V3 — ~360mA at 25% brightness (~1.4A if all-white at full brightness, more than VSYS/USB can supply, so cap brightness and never sustain all-white). 3 wires only: PWR→VSYS, GND→Pico GND, DIN→a PIO GPIO; leave the DOUT pad empty |
| SSD1306 0.96" OLED, I2C | Phase 4. Shares I2C bus with PN532 (different addresses, no conflict) |
| Passive buzzer | Phase 4. PWM on any GPIO |

> **Dropped from v1** (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)): the KY-040 rotary encoder (volume knob) and a play/pause button. Volume and pause are handled by the Siri Remote. The kit parts stay in the bin in case a control returns in a later iteration.

## Pico pin allocation

Running map of every wired pin — **check this before adding a device so nothing double-books.** Update it whenever a wire goes on or comes off.

**Notation:** `L<n>` / `R<n>` = breadboard **row** `n` (1–20, counted from the USB end), on the **L**eft or **R**ight side of the Pico. Left row `n` = physical Pico pin `n`; right row `n` = physical pin `41 − n`. Assumes the Pico is seated with pin 1 (GP0) in breadboard row 1.

| Device | Signal | Notation | Physical pin | Label / GPIO |
|---|---|---|---|---|
| PN532 NFC | SDA | **L6** | 6 | GP4 |
| PN532 NFC | SCL | **L7** | 7 | GP5 |
| PN532 NFC | 3V3 | **R5** | 36 | 3V3(OUT) |
| PN532 NFC | GND | **R3** | 38 | GND |
| LED ring | 5V (PWR) | **R2** | 39 | VSYS |
| LED ring | GND | **R3** | 38 | GND *(shared common ground)* |
| LED ring | DIN | **R7** | 34 | GP28 |
| Buzzer (KY-006) | S (signal) | **R12** | 29 | GP22 |
| Buzzer (KY-006) | − (GND) | **R13** | 28 | GND |

Notes:
- **Ground is a shared rail** — any device's GND can land in any free hole of a GND row. The ring shares the PN532's ground at R3; the buzzer uses **R13** (pin 28); **R8** (pin 33) is still a free GND hole.
- **R4 (pin 37) is `3V3_EN`, not ground.** ⚠️ Never wire ground here — it disables the 3.3 V regulator and kills power to the PN532.
- **I²C bus (GP4/GP5, L6/L7) is shared.** The Phase 4 OLED joins the *same two pins* — different I²C address, no conflict, no new pins.
- **Power rails:** VSYS = R2 (pin 39, ~4.7 V, also the future battery rail), VBUS = R1 (pin 40, true 5 V from USB).
- **Buzzer signal is on GP22 (R12).** Passive piezo — driven directly by PWM on `Pin(22)`, no transistor or VCC. Its middle header pin (between S and −) is not connected; leave it empty. GP22 is a plain digital GPIO, so all three ADC pins (GP26/27/28) stay free.

## Architecture (Phase 3+ target)

```
Pico 2 WH  ──MQTT──▶  Mosquitto (Synology)  ◀─MQTT──▶  Home Assistant (Pi)
   │                                                          │
   │ (NFC tap → events)                                        │ pyatv → Apple TV
   │ (state ← LEDs, OLED)                                      │ Plex API → movies
   ▼                                                           ▼
Local feedback (LEDs, OLED, buzzer)                         Living room TV
```

**Brains live in Home Assistant, not on the Pico.** The Pico is a near-dumb input device that publishes events; HA owns all logic (tag→movie mapping, Apple TV control, switching). Changing a movie mapping never requires reflashing the box. The one piece of *local* state the Pico cares about is "is there an active session for UID X?" — so it can suppress duplicate taps and produce local feedback for re-taps. That state is driven by HA via the `vonbox/state` MQTT topic.

## Phase 1 reference values (use these exact strings)

| Thing | Value |
|---|---|
| HA URL (LAN) | `http://192.168.0.122:8123` |
| Apple TV `media_player` entity | `media_player.living_room` |
| Plex-on-AppleTV `media_player` entity | `media_player.plex_plex_for_apple_tv_apple_tv` |
| Plex source name (for `select_source`) | `Plex` |
| Working webhook example | `play_super_mario_movie` |
| Movie identifier convention | **Plex rating key (numeric), never title.** Find via Plex web URL: `...details?key=%2Flibrary%2Fmetadata%2F<NUMBER>` |

## MicroPython gotchas (don't re-derive these)

- **Onboard LED is `Pin('LED', Pin.OUT)`**, NOT `Pin(25, Pin.OUT)`. The Pico 2 W's LED is on the CYW43 wireless chip, not a direct GPIO. The `Pin(25)` pattern is from the older non-W Pico and will silently do nothing on this board.
- **No `pip install`.** Library installation = copy a `.py` file into the Pico's filesystem under `lib/`. Use MicroPico's "Upload project" or `mpremote cp`. CPython-only libraries (`paho-mqtt`, `requests`, etc.) won't work — find the MicroPython equivalent.
- **Use `asyncio`** (built into MicroPython) for concurrency between NFC polling, MQTT, LED animations. Don't reach for `_thread` — async is the idiomatic and supported path.
- **`umqtt.simple` is the right MQTT client, but is *not* frozen** into the official `RPI_PICO2_W` MicroPython 1.28.0 build. Install it once via `mip` (`test/install_umqtt.py` does this — connects to Wi-Fi, calls `mip.install("umqtt.simple")`, which writes `/lib/umqtt/simple.mpy` to flash). After that, `from umqtt.simple import MQTTClient` works forever on this Pico. If a Pico ever gets reflashed, re-run the installer.
- **Timing:** `time.sleep_ms()` and `time.ticks_ms()` for short waits, not `time.sleep(0.1)`.
- **Memory:** ~520 KB SRAM on the RP2350. Avoid building large strings in tight loops; use `bytearray` and memoryview.
- **`secrets.py`** stores WiFi/MQTT credentials and is gitignored. Never hardcode credentials in tracked files.

## Code conventions

- Snake_case for everything.
- One responsibility per file: `nfc.py`, `mqtt_client.py`, `leds.py`, `display.py`, `main.py` orchestrating.
- `async` functions where it makes sense (polling loops, MQTT receive, animations); plain functions for setup/teardown.
- Constants in UPPER_SNAKE at module top, with units in the name: `POLL_INTERVAL_MS = 100`, not `POLL_INTERVAL = 0.1`.
- `print()` for logging during dev; we'll replace with a small logger if it gets noisy.
- Comments earn their keep by explaining *why*, not *what*. The "what" should be obvious from the code.

## Working style

- **One variable at a time.** When something doesn't work, the goal is to halve the search space. Don't change two things and re-test.
- **Bench-test before integrating.** Get a component working on the breadboard with a tiny standalone script before merging it into a larger program.
- **Decisions in `spec.md` are intentional.** If a different approach seems better, raise it as a question — don't refactor unilaterally. Many of those decisions encode hard-won lessons that aren't visible from the code alone (e.g. "HA on Pi not Synology" looks arbitrary; it's not).
- **Hardware verification needs human eyes.** When you write a Pico script, the user runs it and reports back what they observed (LED behavior, serial output, multimeter reading). Don't try to verify by running scripts via shell — there's no Pico on the shell side, and your output won't reflect reality. Ask the user to run it and tell you what happened.
- **Don't auto-commit.** The user reviews and commits manually.
- **Update `spec.md` when phase status changes.** When a sub-milestone closes, when a new gotcha is found, when an entity ID gets locked in. The doc's "Lessons learned" sections are where hard-won facts go.

## Key references

- `spec.md` — full project plan and lessons learned
- [MicroPython RP2 quickref](https://docs.micropython.org/en/latest/rp2/quickref.html) — PIO, networking, I2C, async
- [MicroPico extension](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go)
- [PN532 datasheet (NXP)](https://www.nxp.com/docs/en/nxp/data-sheets/PN532_C1.pdf)
- [Adafruit CircuitPython PN532 driver](https://github.com/adafruit/Adafruit_CircuitPython_PN532) — closest reference; may need light port to MicroPython
# Claude Code instructions — NFC Movie Box

This is the always-on context. The full project plan, rationale, and lessons learned live in `spec.md` — read it when you need depth on any decision or want to know what comes after the current step. This file is the running, terse version.

## What this is

A Tonie-Box-inspired device that lets a 3.5-year-old start movies on the living room TV by placing 3D-printed figurines on top of a box. NFC identifies each figurine; Home Assistant translates that into Apple TV + Plex commands.

The user is the dad building this for his son Von.

## Current state

**Phase 1 ✅ done** — Apple TV + Plex pipeline working end-to-end via HA webhooks. A single `curl` from cold sleep wakes TV + soundbar + Apple TV, opens Plex, plays a chosen movie.

**Phase 2 ▶️ in progress** — Pico detects figurine placement and removal, prints tag UIDs over USB serial.

Sub-milestones for Phase 2, in order:

1. ✅ **Pico alive** — MicroPython v1.28.0 flashed, MicroPico connected, `blink.py` toggles the onboard LED.
2. **PN532 wired and talking** — I2C handshake successful, library loaded, reader responds with its firmware version. *(currently here)*
3. **NFC polling loop** — 10Hz placement/removal detection printing `PLACED: <UID>` / `REMOVED: <UID>` over serial.

Don't skip ahead. Each sub-milestone isolates one variable for debugging.

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
| WS2812B NeoPixel ring, 16 LEDs | Phase 4. Power from **VSYS (5V)**, not 3V3 — at 25% brightness draws ~240mA which exceeds the regulator |
| KY-040 rotary encoder | Phase 4. Read via **PIO** — zero missed pulses, hardware-timed |
| SSD1306 0.96" OLED, I2C | Phase 4. Shares I2C bus with PN532 (different addresses, no conflict) |
| Passive buzzer | Phase 4. PWM on any GPIO |

## Architecture (Phase 3+ target)

```
Pico 2 WH  ──MQTT──▶  Mosquitto (Synology)  ◀─MQTT──▶  Home Assistant (Pi)
   │                                                          │
   │ (NFC, encoder, button → events)                           │ pyatv → Apple TV
   │ (state ← LEDs, OLED)                                      │ Plex API → movies
   ▼                                                           ▼
Local feedback (LEDs, OLED, buzzer)                         Living room TV
```

**Brains live in Home Assistant, not on the Pico.** The Pico is a dumb input device that publishes events; HA owns all logic (tag→movie mapping, resume timers, Apple TV control). Changing a movie mapping never requires reflashing the box.

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
- **`umqtt.simple` is built in** and is the right MQTT client for this project.
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
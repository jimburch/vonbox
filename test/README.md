# `test/` — what's what

Scripts and configs used while building the box. Three groups by purpose:

| Folder | What's in it | Where it runs |
|---|---|---|
| `bench/` | single-subsystem bring-up tests | on the Pico (MicroPico "Run current file") |
| `offline-harness/` | the "away from home" mock-HA testing setup | Pico **and** laptop |
| `home-assistant/` | HA automations + the prod broker config (not tests) | the Pi (HA) / Synology |

> **Pico-side scripts run ephemerally** via MicroPico's *Run current file on Pico* — they aren't uploaded to flash. Their `import`s (`pn532`, `feedback`, `umqtt.simple`, `secrets`) resolve from the Pico's **flash** `/lib` and `/`, so the folder a script lives in here doesn't affect how it runs. Only `lib/` modules and `secrets.py` must be uploaded to flash (*Upload project to Pico* or `mpremote cp`).

## `bench/` — single-subsystem bring-up

Run one at a time to prove a single piece of hardware/connectivity in isolation.

| File | Proves |
|---|---|
| `i2c_scan.py` | the PN532 answers on the I2C bus at `0x24` |
| `nfc_firmware_test.py` | PN532 alive — raw `GetFirmwareVersion` |
| `nfc_tap_test.py` | single-shot tap detection (`TAPPED: <UID>` once per tap) |
| `nfc_to_mqtt_test.py` | NFC → MQTT orchestrator (publishes `vonbox/nfc/tapped`) |
| `wifi_test.py` | the Pico associates with Wi-Fi from `secrets.py` |
| `mqtt_hello_test.py` | Pico → broker heartbeat on topic `test/hello` |
| `install_umqtt.py` | one-time: `mip.install("umqtt.simple")` to flash |
| `led_ring_test.py` | the 24-px WS2812 ring — colors + animations |
| `buzzer_test.py` | the KY-006 piezo — success/error/neutral cue menu |

## `offline-harness/` — testing away from home base

Exercise the full `tap → feedback` loop with no home network, HA, or Apple TV.
See **`docs/testing-away-from-home.md`** for the full runbook (hotspot setup, etc.).

| File | Role |
|---|---|
| `state_render_test.py` | **Layer 1** (Pico): drive `lib/feedback.py` through every state — no network, no NFC |
| `full_loop_test.py` | **Layer 3** (Pico): Wi-Fi + MQTT + PN532, the whole tap → ring/buzzer choreography |
| `mock_ha.py` | **Layer 3** (laptop, CPython/paho): fake Home Assistant — subscribes to taps, publishes `vonbox/state` |
| `mosquitto.dev.conf` | throwaway **anonymous** laptop broker (`mosquitto -c test/offline-harness/mosquitto.dev.conf -v`) |

## `home-assistant/` — configs, not tests

Server-side configuration that happens to live in the repo. Not run on the Pico.

| File | What it is |
|---|---|
| `play_mario.yaml` | canonical HA automation — the proven cold-start play sequence |
| `play_from_tap.yaml` | HA automation: `vonbox/nfc/tapped` → look up rating key → play |
| `mosquitto.conf` | the **production** broker config (deployed on the Synology) |

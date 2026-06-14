# Testing the tap → feedback loop away from home

- **Status:** Living runbook
- **Date:** 2026-06-08
- **Applies to:** Phase 3 (MQTT) + Phase 4 (LED ring / buzzer feedback) bench work, done anywhere with no home network, no Home Assistant, and no Apple TV.

> This is a how-to, not a decision record. It tells you how to exercise the full
> `tap → local feedback → MQTT → state → ring/buzzer` choreography on a kitchen
> table, a hotel desk, or a car seat — using nothing but the Pico, a laptop, and
> an iPhone hotspot.

## The core idea

The Pico is a near-dumb MQTT device. It only ever does three things over the
network: publish `vonbox/nfc/tapped`, subscribe to `vonbox/state`, and reconnect
when the link drops. It has **no idea** what's behind the broker — whether it's
real Home Assistant driving a real Apple TV, or a 40-line Python script
pretending to be one.

So to test away from home we replace exactly two things:

1. **The broker** — instead of Mosquitto on the Synology, run Mosquitto on the laptop.
2. **The thing behind the broker** — instead of Home Assistant + pyatv + Plex,
   run `test/offline-harness/mock_ha.py`, a fake HA that subscribes to `vonbox/nfc/tapped` and
   publishes plausible `vonbox/state` updates back.

**Pico firmware is unchanged.** The only edit is to `secrets.py` (Wi-Fi SSID +
broker IP), which is gitignored, so the swap is safe to leave in place between
trips. No MQTT code changes — see the note on the anonymous dev broker below.

## The three layers

Pick the lowest layer that answers the question you have. Each layer adds one
moving part, in keeping with the project's "one variable at a time" rule.

### Layer 1 — pure hardware, no network: `test/offline-harness/state_render_test.py`

Drives `lib/feedback.py` through every state on a timer. No Wi-Fi, no MQTT, no
PN532. Just the LED ring and buzzer.

**Use it to** answer "does the ring show the right thing for each state, and do
the buzzer cues sound right?" — without any of the networking that could
confound a visual/audio bug. Run it any time, anywhere, even with no hotspot.
This is where you tune animations and cue pitches.

Run: MicroPico "Run current file on Pico" on `test/offline-harness/state_render_test.py`. Watch
the ring cycle idle → loading → playing → already_playing → paused → standby →
error and listen to the cues.

### Layer 2 — hand-publish state to the Pico over MQTT

Run the broker on the laptop (below), run the Pico's full loop (or a minimal
subscriber), and **type state changes by hand** with `mosquitto_pub`. No
`mock_ha.py`, no PN532 tap required.

**Use it to** answer "does the Pico correctly react to a `vonbox/state` message
arriving over the wire?" — separating MQTT delivery + JSON parsing from the
NFC-read path. This is the bridge between "the renderer works" (Layer 1) and
"the whole loop works" (Layer 3). The raw command is in
[Manual state injection](#manual-state-injection-no-tag-required) below.

### Layer 3 — the full loop: `test/offline-harness/full_loop_test.py` + `test/offline-harness/mock_ha.py`

Everything end-to-end. On the Pico, `test/offline-harness/full_loop_test.py` connects Wi-Fi →
MQTT → PN532, and on a tap fires local `tap_accepted()` feedback, publishes
`{"uid": "<HEX>"}` to `vonbox/nfc/tapped`, and optimistically sets the
`loading` state. It subscribes to `vonbox/state` and renders whatever the mock
sends. On the laptop, `test/offline-harness/mock_ha.py` is the fake Home Assistant: it
subscribes to `vonbox/nfc/tapped`, and (after a short fake "wake the Apple TV"
delay) publishes `loading` then `playing` back on `vonbox/state` — or `error`
for an unknown UID.

**Use it to** answer "does the real choreography work?" Tap the NTAG215 and
watch the whole sequence play out on the box.

## One-time laptop install (macOS)

```bash
brew install mosquitto      # the broker + mosquitto_pub / mosquitto_sub clients
pip3 install paho-mqtt      # mock_ha.py is CPython and uses paho
```

> **paho is laptop-only.** The "no `pip install`, no paho" rule in CLAUDE.md is
> about the **Pico** (MicroPython, `umqtt.simple`). The laptop mock is ordinary
> CPython, so `paho-mqtt` is fine and expected there.

## ⚠️ iPhone hotspot gotcha — the Pico is 2.4 GHz only

**Read this before anything else fails.** The Pico 2 W's radio (CYW43439) is
**2.4 GHz only**. Newer iPhones default their Personal Hotspot to 5 GHz, and the
Pico simply **will not associate** — you'll see it retry Wi-Fi forever with no
useful error.

**Fix:** on the iPhone, Settings → Personal Hotspot → enable **"Maximize
Compatibility."** That forces the hotspot to 2.4 GHz, which the Pico can join.
(On iPhones that don't show this toggle, the hotspot may already be 2.4 GHz;
if association still fails, that's the first thing to suspect.)

Join **both** the laptop **and** the Pico to the same hotspot:

- **Laptop:** join the hotspot's Wi-Fi normally (or USB-tether — either way it
  lands on the hotspot LAN).
- **Pico:** set the hotspot SSID/password in `secrets.py` (below).

## Find the laptop's IP on the hotspot

The Pico needs the laptop's address on the hotspot LAN to reach the broker:

```bash
ipconfig getifaddr en0          # usual Wi-Fi interface on a Mac
```

The interface isn't always `en0` (USB tethering, a dock, or a second adapter can
shift it). Confirm which interface actually has a hotspot-range address:

```bash
ifconfig | grep "inet "
```

Pick the `inet` line on the hotspot subnet (Apple hotspots hand out
`172.20.10.x`). That address is your `MQTT_HOST`.

## `secrets.py` changes

`secrets.py` is gitignored, so editing it for a trip is safe — it won't get
committed and you can leave the away-from-home values in place.

| Key | Home value | Away-from-home value |
|---|---|---|
| `WIFI_SSID` | home SSID | the iPhone hotspot's name |
| `WIFI_PASSWORD` | home password | the hotspot password |
| `MQTT_HOST` | Synology LAN IP | the **laptop's** hotspot IP (from above) |
| `MQTT_PORT` | `1883` | `1883` (unchanged) |
| `MQTT_USER` | `vonbox` | `vonbox` (unchanged — see below) |
| `MQTT_PASSWORD` | (home value) | (unchanged — see below) |

**Leave `MQTT_USER` / `MQTT_PASSWORD` alone.** The dev broker
(`test/offline-harness/mosquitto.dev.conf`) runs with `allow_anonymous true`, so it accepts the
connection regardless of the credentials the Pico sends. That's the whole reason
the Pico's MQTT code needs **zero** changes away from home — same connect call,
the broker just doesn't check the password.

Write the edited `secrets.py` to the Pico's flash — `from secrets import ...`
resolves against flash, not the file on the laptop, so a "Run current file on
Pico" of `test/offline-harness/full_loop_test.py` still imports the **flash** copy of
`secrets.py`. There are only two ways to write to flash:

- **MicroPico: "Upload project to Pico"** — note this writes *all* project
  files to flash, not just `secrets.py`, **or**
- single-file copy: `mpremote cp secrets.py :secrets.py`.

(There is no MicroPico "Upload current file" command — "Run current file on
Pico" is ephemeral and does *not* persist to flash.) Remember to swap the values
back when you get home.

## macOS firewall

If the macOS firewall is on, it will block the Pico's inbound TCP connection to
`laptop:1883` and the broker will look dead from the Pico's side.

- System Settings → Network → Firewall → Options → add `mosquitto` and allow
  incoming connections. macOS *may* show an interactive prompt the first time
  the broker binds a port, but for a Homebrew CLI binary it often does **not**
  and silently blocks the port instead — so don't wait for a prompt. **or**
- temporarily turn the firewall off for the test session.

If the broker looks dead from the Pico, confirm with `mosquitto_sub` (see
Troubleshooting): if a publish from another device never reaches the bus, the
firewall is the prime suspect.

## Run order

From the repo root, three terminals (plus the Pico):

```bash
# 1. Broker — verbose so you can watch clients connect and messages flow.
mosquitto -c test/offline-harness/mosquitto.dev.conf -v

# 2. Fake Home Assistant — subscribes to taps, publishes state.
python3 test/offline-harness/mock_ha.py

# 3. (optional, recommended) Watch the whole bus in a third terminal:
mosquitto_sub -h localhost -t 'vonbox/#' -v
```

Then: MicroPico "Run current file on Pico" on **`test/offline-harness/full_loop_test.py`**.

Watch the Pico associate with the hotspot and connect to the broker (the
`mosquitto -v` terminal logs the connection). Now **tap the NTAG215
(`045AED5ECD2A81`)** against the PN532 and watch the choreography:

1. Pico fires **local** `tap_accepted()` — green sparkle + rising two-note chime,
   *before* any network round-trip.
2. Pico publishes `vonbox/nfc/tapped {"uid": "045AED5ECD2A81"}` and optimistically
   shows `loading` (blue chase).
3. `mock_ha.py` sees the tap, waits its fake wake delay, publishes `loading` then
   `playing` on `vonbox/state`.
4. Pico settles to `playing` — steady solid green.

Tap an **unknown** tag and the mock publishes `error` (with a `reason`); the ring
does its 3 red flashes and reverts to the prior state.

## Manual state injection (no tag required)

Useful for Layer 2, and for forcing states the mock won't naturally produce.

Watch the bus:

```bash
mosquitto_sub -h localhost -t 'vonbox/#' -v
```

Drive a state by hand — note the **tagged** payload shape (every field present):

```bash
mosquitto_pub -h localhost -t vonbox/state \
  -m '{"state":"playing","uid":"045AED5ECD2A81","title":"The Super Mario Bros. Movie","reason":null}'
```

Swap `"state"` for any of: `idle`, `loading`, `playing`, `already_playing`,
`paused`, `standby`, `error`. For `error`, put a human-readable string in
`"reason"` (e.g. `"unknown_tag"`); the others can leave it `null`.

`test/offline-harness/mock_ha.py` also reads simple commands on **stdin** so you can nudge it
without touching `mosquitto_pub` — type one of `idle`, `playing`, `paused`,
`standby`, `error`, `help`, or `quit` in the terminal running the mock to have
it publish that state (each uses a fixed placeholder UID/title). (See the
file's header for its exact command vocabulary.)

## Troubleshooting

- **Pico never associates with Wi-Fi.** Almost always the 2.4 GHz gotcha. Enable
  "Maximize Compatibility" on the iPhone hotspot. Double-check the SSID/password
  in `secrets.py` and that you wrote it to flash ("Upload project to Pico" or
  `mpremote cp secrets.py :secrets.py`) — a "Run current file" alone does not
  persist `secrets.py`.
- **Pico connects to the broker but no taps reach the mock.** Either the macOS
  firewall is blocking inbound `1883` (allow `mosquitto`), or the hotspot has
  AP/client isolation so the Pico and laptop can't see each other — confirm with
  the `mosquitto_sub -t 'vonbox/#' -v` watcher: if the Pico's publish never shows
  up there, it's a network-path problem, not a code problem.
- **Broker refuses the connection / only localhost works.** Make sure
  `test/offline-harness/mosquitto.dev.conf` binds `0.0.0.0` (all interfaces), not just
  `localhost`/`127.0.0.1` — otherwise the Pico can reach the port number but the
  broker isn't listening on the hotspot interface.
- **Ring/buzzer wrong but network looks fine.** Drop to Layer 1
  (`test/offline-harness/state_render_test.py`) to isolate the renderer from the network.
- **Wrong `MQTT_HOST`.** Re-run `ipconfig getifaddr en0` (and the `ifconfig`
  check) — the laptop's hotspot IP can change between sessions.

## See also

- `lib/feedback.py` — the LED + buzzer state renderer the Pico scripts drive.
- `test/offline-harness/state_render_test.py` — Layer 1 harness.
- `test/offline-harness/full_loop_test.py` — Layer 3 Pico-side harness.
- `test/offline-harness/mock_ha.py` — Layer 3 laptop-side fake HA.
- `test/offline-harness/mosquitto.dev.conf` — throwaway anonymous broker config for the laptop.
- `SPEC.md` → "Testing the feedback loop away from home" — the same picture in
  the project plan, plus the canonical `vonbox/state` payload.

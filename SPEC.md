---
created: 2026-04-20, 3:48 PM
updated: 2026-06-08
tags:
---
# NFC Movie Box for Von — Project Plan

A device that lets a 3.5-year-old start movies on the living room TV by **tapping** an NFC-tagged object (card, coin, mini character) against a small box. NFC identifies the tag, Home Assistant translates that into commands for the Apple TV running Plex.

---

## Inspiration & Goal

Closely modeled on [Simply Explained's NFC movie library for kids](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/). The Tonie Box was an earlier inspiration but the *interaction model has been deliberately changed away from Tonie's continuous-presence design* — see [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md).

Von (3.5 years old) loves the physical-object-triggers-media experience of his Tonie Box for songs. This project brings that to his movies — but with a **tap-and-go** interaction: Von brings the Buzz Lightyear tag to the box, hears a confirmation chime, takes the tag away, and Toy Story plays. No magnets, no continuous presence, no "the figurine has to live on the box for the movie to keep playing."

---

## Current status

**✅ Phase 1 done — Apple TV + Plex pipeline working end-to-end.** A single curl from the laptop wakes the TV + soundbar + Apple TV from full sleep, opens Plex, and starts a chosen movie. Tested with The Super Mario Bros. Movie (Plex rating key `190`).

**✅ Phase 2 done — NFC reading on the Pico.**
- ✅ Sub-milestone 1: MicroPython v1.28.0 flashed onto the Pico 2 WH, VS Code + MicroPico extension connected over USB serial, `blink.py` runs and toggles the onboard LED.
- ✅ Sub-milestone 2: PN532 V3 (HiLetgo red board) wired to the Pico over I2C on GP4 (SDA) / GP5 (SCL), DIP switches set to I2C mode, responds at address `0x24`, identifies itself as PN532 firmware 1.6 via the `GetFirmwareVersion` command. Bench-test scripts saved to `test/bench/i2c_scan.py` and `test/bench/nfc_firmware_test.py`.
- ✅ Sub-milestone 3: single-shot tap detection working. Polls at ~10Hz via `InListPassiveTarget`, prints `TAPPED: <UID>` exactly once per tap, suppresses re-fires until the tag has been absent ≥2s. Confirmed with an NTAG215 sticker (UID `04462765C82A81`): hold-for-5s produces one event, rapid re-tap within 2s is suppressed, post-cooldown re-tap fires correctly. Inline minimal driver lives in `test/bench/nfc_tap_test.py`; will be extracted to `lib/pn532.py` during Phase 3.

**▶️ Phase 3 in progress — MQTT to Home Assistant.**
- ✅ Sub-milestone 1: Mosquitto MQTT broker deployed as a Docker container on the Synology at `192.168.0.123:1883`. Authenticated user `vonbox` created via `mosquitto_passwd`. Verified from the laptop using `mosquitto_pub`/`mosquitto_sub` — a message published to `test/hello` is received by a subscriber within milliseconds.
- ✅ Sub-milestone 2: Pico associates with the home Wi-Fi (`Jabby`), receives DHCP lease `192.168.0.80`, reports RSSI `-42 dBm`. Credentials live in `secrets.py` (gitignored); uploaded to the Pico's flash via MicroPico "Upload current file" so subsequent test scripts can `from secrets import ...`. Test script: `test/bench/wifi_test.py`.
- ✅ Sub-milestone 3: Pico → Mosquitto verified end-to-end. `test/bench/mqtt_hello_test.py` publishes `hello N` to `test/hello` every 5 seconds via `umqtt.simple`; laptop `mosquitto_sub` receives each one within milliseconds. `umqtt.simple` is **not** frozen into the `RPI_PICO2_W` MicroPython 1.28.0 build despite older docs implying otherwise — installed once via `mip.install("umqtt.simple")` to `/lib/umqtt/simple.mpy` using `test/bench/install_umqtt.py`.
- ✅ Sub-milestone 4: Inline PN532 driver extracted into `lib/pn532.py` (class `PN532` with `init()` and `read_passive_target()`; framing helpers private; raises `PN532Error` on bring-up failure). Orchestrator at `test/bench/nfc_to_mqtt_test.py` connects Wi-Fi → MQTT → PN532, then runs the Phase 2 polling loop and publishes `{"uid": "<HEX>"}` to `vonbox/nfc/tapped` on each new tap. Edge-trigger + 2s-absence cooldown preserved verbatim. Verified end-to-end: NTAG215 `04462765C82A81` produces `vonbox/nfc/tapped {"uid": "04462765C82A81"}` on the Mac subscriber; hold-for-5s = one publish, rapid re-tap suppressed, post-cooldown re-tap fires, tag-swap fires immediately with the new UID.
- ▶️ Sub-milestone 5 next: HA automation. UID → Plex rating-key mapping (input_text helper or YAML config). On `vonbox/nfc/tapped`, look up the rating key and run the Phase 1 cold-start sequence. First true tap-to-play moment.
- Sub-milestone 6 (planned): Bidirectional state sync. HA publishes Apple TV state transitions to `vonbox/state`; Pico subscribes and uses the state to decide whether a re-tap of the same UID is a local no-op or a fresh session.

> **Tooling note:** switched from Thonny (mentioned in Phase 2 plan below) to **VS Code + MicroPico extension** — same MicroPython workflow, fits the existing editor. Phase 2 instructions still apply, just substitute MicroPico's "Run current file on Pico" for Thonny's run button.

**Deferred from Phase 1** (intentional — will fold into later work):
- Pause webhook — dropped from v1 along with the play/pause button (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)). v1 has no on-box pause; the Siri Remote covers it in the meantime. (It was previously planned to fold into the Phase 3 `nfc/removed` automation, then the Phase 4 button automation — both now gone; see [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md).)
- Tailscale remote access — works any time, not blocking anything.

---

## How it works (end-to-end flow)

1. Von taps the Buzz Lightyear tag against the box (no need to hold it there)
2. Box's NFC reader detects the tag UID once, fires a single MQTT/webhook event to Home Assistant, and enters "session active" state for that UID
3. HA wakes Apple TV, launches Plex, starts Toy Story
4. Apple TV plays on living room TV, audio through soundbar via HDMI-ARC/CEC
5. Von can walk away. The movie keeps playing. No tag has to stay near the box.
6. **If Von taps the same tag again while Toy Story is still playing/paused:** the box ignores the tap (the session is already active for that UID) and gives a soft "already playing" cue (gentle chime + brief LED pulse). No new HA event.
7. **If Von taps a different tag (e.g. Cars) while Toy Story is playing:** HA switches movies immediately — stops Toy Story, starts Cars. Plex's native resume position remembers where Toy Story was for the next time it's tapped.
8. **Pause (v1):** the box has no pause control in v1 — a movie plays until a different tag is tapped or the Apple TV goes to sleep. The Siri Remote can still pause/resume in the meantime. (The play/pause button was dropped from v1 — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md).)
9. **Session ends** when the Apple TV goes back to sleep (HA detects this and tells the box). After session-end, the next tap of any tag — including the same one that started the previous session — is a fresh start (Plex's own resume window still applies for picking up mid-movie inside Plex's memory).
10. **Volume (v1):** adjusted with the Siri Remote / soundbar through the existing Apple TV → HDMI-CEC path. There is no volume knob on the box in v1 (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)).

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Movie Box      │      │  Raspberry Pi 4  │      │  Apple TV       │
│  ─ Pico 2 WH    │◀───▶│  ─ Home Assistant│─────▶│  ─ Plex app     │
│  ─ PN532 NFC    │ MQTT │  ─ pyatv         │pyatv │  ─ Soundbar via │
│  ─ NeoPixel ring│      │  ─ Plex integr.  │      │    HDMI-CEC     │
│  ─ Buzzer       │      │  ─ State machine │      │                 │
│  ─ OLED display │      │  ─ Cloudflared   │      │                 │
│                 │      │  (existing)      │      │                 │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                  │
                                  │ Plex API
                                  ▼
                         ┌──────────────────┐
                         │  Synology        │
                         │  ─ Plex server   │
                         │  ─ Movie library │
                         │  ─ Mosquitto MQTT│
                         └──────────────────┘
```

**Infrastructure layout:**

- **Home Assistant** runs in Docker on the **Raspberry Pi 4** (already running Portainer + Cloudflared). Moved off Synology because Synology Container Manager's Docker daemon has known issues extracting modern HA image layers. Pi runs standard Raspberry Pi OS with a current Docker daemon — HA updates "just work" long-term.
- **Mosquitto MQTT broker** runs in Docker on the **Synology** (Synology Docker handles simpler images like Mosquitto fine).
- **Plex** continues running on the Synology, unchanged.
- **Tailscale** installed on Pi + phone + laptop for private remote access to HA.

**Key design principles:**

- **Brains live in Home Assistant, not on the box.** The Pico is a dumb input device that reads NFC and publishes events. HA owns all logic (tag-to-movie mapping, Apple TV control, switching between movies). This means changing a movie mapping doesn't require reflashing the box.
- **Tap-and-go, not continuous presence.** A tag near the reader fires *once*, then the tag goes away. The box does not require any object to remain on or near it for a movie to keep playing. This is the central design pivot away from the Tonie-Box model. See [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md).
- **Plex handles resume automatically.** When HA stops one movie and switches to another (or when a movie is paused for a long time and the Apple TV sleeps), Plex's own resume position is what brings Von back to where he left off the next time that movie's tag is tapped. The box does not manage resume timers.
- **Volume passes through Apple TV → HDMI-CEC → soundbar.** Same path as the existing Apple TV remote. v1 has no volume control on the box — the Siri Remote owns volume (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)).
- **NFC polls at ~10Hz but events are edge-triggered.** The Pico publishes a single `tapped` event the first time a UID is read; it then suppresses further events for that UID until the tag has been *absent* for ~2s (or a different UID appears). Von can mash the tag against the box repeatedly; HA sees one event.
- **The Pico tracks "session active" state per-UID so it can give local feedback.** While a UID's session is active, re-reads of the same UID produce a *local* "already playing" cue (chime + LED pulse) and do not generate HA events. The Pico learns session-end either by HA pushing state via MQTT (preferred — Apple TV state changes) or by its own timeout.
- **MQTT for bidirectional Pico ↔ HA communication.** Event-driven, low-overhead. The Pico publishes events (tapped); HA publishes state updates back (playing, paused, standby, error) so the Pico can update LEDs, the OLED, and its own session-active state.
- **Pico is immediately responsive**, HA confirms state. Local feedback (instant beep/LED on tap acceptance) fires on the Pico the moment the read succeeds; HA-confirmed feedback (LED ring transitioning to "playing") follows once the movie is actually playing on the Apple TV.

---

## Hardware

### From the Inventr "30 Days Lost in Space" Arduino kit (already owned)

- Rotary encoder module (KY-040 style) — *not used in v1 (volume knob dropped — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)); kept in the parts bin for a later iteration*
- Passive buzzer module (can play actual tones via PWM)
- 0.96" OLED display (SSD1306, I2C)
- Tactile buttons — *not used in v1 (play/pause button dropped — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)); kept for a later iteration*
- Breadboard, jumper wires, resistor assortment
- LEDs (for bench testing)
- HERO board / Arduino Uno clone (for bench-testing components before wiring to Pi)
- Soldering iron and supplies (owned separately)

### To purchase

| Item | Approx cost | Notes |
|---|---|---|
| Raspberry Pi Pico 2 WH (with pre-soldered headers) | $7 | Wi-Fi + BT, RP2350 chip, low power. Pico WH (RP2040) is an acceptable fallback if 2 WH is out of stock. |
| USB-A to micro-USB cable | $3 | For programming + power |
| PN532 NFC module (I2C, with headers) | $10 | HiLetgo or Adafruit |
| NeoPixel ring, WS2812, 24 LEDs (DIYMalls) | $8 | For the illuminated status ring on top of the box. Went with the larger 24-LED ring over the original 16 — proportionally more current draw (see Phase 4 power note). |
| NTAG215 stickers, 50-pack | $10 | Any brand. Will be embedded into / stuck onto whatever physical token Von taps (cards, 3D-printed coins, small figurines, etc.) |
| Mounting hardware (M2.5 screws, heat-set inserts) | $10 | For enclosure assembly |
| **Subtotal (Phases 1–4)** | **~$48** | Enough to prototype everything |
| Pico-specific protoboard (Pimoroni or Adafruit) | $5 | For Phase 5 — transfers breadboard layout to permanent wiring |
| Female header sockets (2x20 pin) | $3 | Pico plugs into these on the protoboard, stays removable |
| JST or screw-terminal connectors (optional) | $5 | For swappable component wiring |
| **Total (through Phase 5)** | **~$61** | |

> **Struck from the original BOM** (no longer needed with the tap-and-go pivot): neodymium magnets and NFC ferrite shielding stickers. Magnets were only for figurine/box mating; without continuous-presence seating there's nothing to mate. Ferrite was only needed because magnets near an NFC antenna detune the field — no magnets, no detuning, no ferrite.

> **Why the pre-soldered "H" variant:** saves soldering 40 pins. If you buy the bare Pico 2 W it's $6; the "H" (pre-soldered) is $7. Worth the dollar.
>
> **Where to buy the Pico 2 WH:** Adafruit (product #6315), PiShop US (SC1634), or Micro Center are best. Amazon works but verify the board is genuine Raspberry Pi-branded with the RP2350 chip — some listings mix in clones or the older RP2040 Pico 1 WH.

### Why the Pico 2 W (and not a Pi Zero 2 W or Arduino)

**Vs. Arduino (HERO board in the kit):** no Wi-Fi, no Bluetooth, not enough flash/RAM for the full feature set. Out of the running.

**Vs. Pi Zero 2 W:** the Pi Zero was my first recommendation because of Python dev velocity, but the Pico 2 W is a better fit for this project because:

- **~10x better battery life** (Pico ~50mA active vs. Pi Zero ~400mA). Aligns with the "eventually battery-powered" goal without needing to port to ESP32 later.
- **Instant boot** — Pico is ready in milliseconds. Pi Zero takes ~20s to boot from cold, which would frustrate Von when the battery-powered box wakes up.
- **PIO (Programmable I/O)** — genuinely excellent for NeoPixels and rotary encoders. Timing is handled in hardware; no missed encoder pulses, rock-solid LED updates.
- **No SD card** — removes the single biggest reliability failure mode in hobby Pi projects.
- **Appliance feel** — a microcontroller running one program forever is the right mental model for a kid's toy. Pi Zero is a general-purpose Linux box that can get into weird states.
- **Smaller + cheaper** — ~21mm × 51mm, fits anywhere, ~$7.

**Tradeoff accepted:** dev loop is slightly slower (flash firmware and reboot vs. edit Python and re-run). Thonny makes this manageable. Debugging uses USB serial instead of SSH. The box's logic is simple enough that these don't meaningfully hurt us.

---

## Tag tokens & box physical design

**Tag tokens** (the things Von taps against the box):

- NTAG215 stickers embedded in / stuck on whatever physical form works best. Options to explore in Phase 5+:
  - Laminated printed cards with movie poster art (cheapest, fastest, blog-post style)
  - 3D-printed "coins" with a recess for the sticker and a printed character on the face
  - Mini 3D-printed figurines (still possible; just no magnetic mating to the box)
- Form factor decision is **deferred to Phase 5** — any NTAG215 anywhere works for development/testing. Final form is a UX decision for Von's hands, not a firmware decision.
- No ferrite shielding, no magnets in the token.

**Box top:**

- A clearly-marked tap zone (printed icon or color marker) where the NFC antenna sits directly underneath, so Von learns where to aim.
- PN532 NFC antenna centered directly under the tap zone, as close to the surface as possible (read range is short — millimeters to a few cm with NTAG215 stickers).
- NeoPixel 24-LED ring on top, around or near the tap zone, diffused through translucent PLA — the primary visual status surface.
- OLED display in a window on the front face (movie title, parent-readable error messages).
- Buzzer vented for clear sound.

> v1 has no rotary encoder (volume knob) and no play/pause button — those were dropped to keep the first build simple. See [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md). The top surface for v1 is just the tap zone + LED ring; volume and pause are handled by the Siri Remote.

**Materials:**

- Main box: standard PLA, any color
- Diffuser for LED ring: translucent/white PLA (Bambu makes one)
- Printed on Bambu Lab A1

---

## User feedback vocabulary

### NeoPixel ring states

The LED ring is the **primary visual status surface**. States below are listed in roughly the order Von will encounter them in a session.

| State | When | Animation | Color | Brightness |
|---|---|---|---|---|
| Off | Box unpowered, or parental "quiet" mode | All LEDs off | — | 0% |
| On (idle) | Box awake, no movie playing, ready for a tap | Slow breathing | Soft warm white | ~10% |
| Read accepted | A tap just produced a new event being sent to HA | Quick sparkle → settle | Green | ~25% |
| Already playing (same tag re-tapped) | Tag matches the currently active session — local no-op | Single soft pulse | Same as current state | brief +10% |
| Loading | HA event sent, waiting for Apple TV to start playing | Chase (single LED runs the ring) | Blue | ~30% |
| Playing | HA confirms movie is playing | Steady solid | Green | ~20% |
| Paused | HA reports the movie paused (e.g. via the Siri Remote — v1 has no on-box pause) | Slow breathing | Amber | ~15% |
| Standby | Apple TV is asleep (session ended) — box still on | Very slow breathing | Soft warm white | ~5% |
| Unknown tag / error | UID with no mapping, or HA reports an error | 3 flashes then back to prior state | Red | ~40% |

### Buzzer sounds

- **Tap accepted (new movie):** rising two-note chime ("got it")
- **Tap rejected, already playing:** single soft mid-note ("yeah I know")
- **Tap unknown UID:** soft low descending tone ("hmm?")
- **Keep it musical and gentle** — a 3.5-year-old will hear these a lot.

(v1 has no play/pause button, so there are no pause/resume button cues — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md).)

### OLED display

- **Idle / standby:** clock or cute animation
- **Tag detected:** movie title (briefly)
- **Playing:** movie title, optionally a progress bar
- **Paused:** "Paused — {movie title}"
- **Error:** human-readable error message (for the parent)

Useful for Von (magic factor), useful for dad (debugging).

### Pause / restart behavior (v1)

v1 has **no on-box pause control** — the play/pause button was dropped to keep the first build simple (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)).

- **Pause/resume:** use the Siri Remote. The box never originates a pause; if a movie is paused externally, HA reports it and the LED ring shows the "Paused" state.
- **Stopping a movie:** tap a different tag (switches movies) or let the Apple TV go to sleep (ends the session).
- **No restart-from-beginning behavior.** If Von wants to restart, he taps the tag again after the current session has ended (Apple TV asleep). Within an active session, the only way to start a movie over is to tap a different tag and then tap the original tag back — which Plex's resume window will still bias toward picking up mid-movie, so true "restart from beginning" is a Phase 6+ feature if it turns out to matter.
- **A future iteration may reintroduce a button** (pause/resume, and possibly a long-press for parental override / box reset). It is out of scope for v1.

---

## Technical decisions locked in

- **Raspberry Pi Pico 2 W** running **MicroPython**
- **Home Assistant** (on Raspberry Pi via Docker) + **pyatv** for Apple TV control
- **Plex API via HA** for movie triggering
- **MQTT** (Mosquitto broker on Synology) for Pico ↔ HA communication
- **PN532 NFC reader** with **NTAG215 stickers**
- **Tap-and-go interaction**: edge-triggered single read per UID, ~2s absence-based cooldown before the same UID can re-fire (see [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md))
- **Underlying poll rate ~10Hz** — gives ~100ms tap responsiveness; the polling itself is unchanged, only the event semantics shifted
- **No volume knob and no play/pause button in v1** — both dropped to keep the first build simple (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)). Volume and pause are handled by the Siri Remote; either control may return in a later iteration.
- **NeoPixels driven via PIO**, running at 25% brightness (safely powered from Pico's VSYS rail)
- **One tag per movie** (simple mental model)
- **No on-box resume timer.** Plex's native resume position handles "pick up where you left off"; HA does not manage a 1-hour clear cycle anymore.

---

## Phasing

### Phase 1: Prove the Apple TV + Plex pipeline (no hardware yet)

**Goal:** A curl command from your laptop plays Toy Story on the Apple TV via Plex.

**Why first:** This is the highest-risk integration in the whole project. If it doesn't work, nothing else matters. Do this before spending on hardware.

#### Step 1: Install Home Assistant on the Raspberry Pi via Portainer

The Pi 4 has Portainer already. Deploy HA as a new stack there.

1. SSH into the Pi or use Portainer's web UI
2. Create a folder for HA's config:
   ```bash
   mkdir -p /home/jim/docker/homeassistant
   ```
   (Adjust path to match your user/home directory on the Pi)
3. In Portainer on the Pi, go to Stacks → Add stack
4. Name it `homeassistant`
5. Paste this compose:

   ```yaml
   services:
     homeassistant:
       container_name: homeassistant
       image: ghcr.io/home-assistant/home-assistant:stable
       restart: unless-stopped
       network_mode: host
       volumes:
         - /home/jim/docker/homeassistant:/config
         - /etc/localtime:/etc/localtime:ro
       environment:
         - TZ=America/Phoenix
       privileged: true
   ```

6. Deploy. Wait 3–5 minutes for first-run setup (slower than Synology due to Pi's ARM CPU, but one-time).
7. Access at `http://<pi-lan-ip>:8123`, complete onboarding, set location to Mesa, AZ.

**Why `network_mode: host`** — HA needs to see mDNS/Bonjour traffic to auto-discover the Apple TV. Bridge networking breaks discovery. Also make sure your Pi is on the same network segment (VLAN) as the Apple TV.

**Why `privileged: true`** — harmless here, and prevents surprises if you later add Bluetooth/USB integrations.

**Why the Pi and not the Synology:** Synology Container Manager ships a frozen Docker version that has known issues extracting modern HA image layers (the error looks like `failed to register layer: ApplyLayer exit status 1 ... archive/tar: invalid tar header`). The Pi runs standard Docker that updates cleanly via `apt`, so HA updates work reliably long-term. Also, HA on Pi is the officially supported canonical deployment.

#### Step 1b (optional, after Phase 1 works): Add Tailscale for private remote access

Once HA is working locally, you probably want to access it from your phone when out of the house. **Tailscale** is the right tool for this — it creates a private mesh network between your devices with no public internet exposure and no reverse proxy complexity.

1. Install Tailscale on the Pi:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```
   Follow the auth link to connect the Pi to your tailnet.
2. Install Tailscale on your phone and laptop, sign in with the same account.
3. In the Tailscale admin console, enable **MagicDNS** for friendly hostnames.
4. Access HA from anywhere at `http://<pi-hostname>:8123` (or whatever your Pi is named in Tailscale).

**Why Tailscale over Cloudflare Tunnel for HA specifically:**
- HA controls your house — keeping it off the public internet entirely is materially safer than exposing it behind an auth layer
- No reverse proxy = no `trusted_proxies` config in HA
- Direct WireGuard connection is noticeably snappier than Cloudflare edge routing
- Setup is ~15 minutes vs. configuring tunnel ingress rules + Access policies

Keep your existing Cloudflare tunnel for services that make sense to be more publicly accessible (Radarr/Sonarr/etc. on Synology). HA goes on Tailscale. They coexist fine.

**Webhooks still work normally** — the Pico hits HA on the **Pi's LAN IP** directly, not through Tailscale. LAN traffic stays LAN. Tailscale is only for your browser when away from home.

**✅ Checkpoint:** HA dashboard loads in browser at `http://<pi-lan-ip>:8123`.

#### Step 2: Pair the Apple TV

1. Settings → Devices & services → Add Integration → "Apple TV"
2. Select your living room Apple TV from the discovered list
3. Enter the PIN shown on the TV
4. Complete **both pairing flows** if prompted (AirPlay + Companion — Companion is needed for app launching, uses a separate pairing)
5. If pairing fails: wake the Apple TV first, ensure both devices are on the same network/VLAN, retry. Apple TV pairing is finicky.

**✅ Checkpoint:** Developer Tools → Services → `media_player.turn_on` on the Apple TV entity wakes the TV.

#### Step 3: Connect Plex

1. Settings → Devices & services → Add Integration → "Plex Media Server"
2. Auto-discovery should find your Plex on the Synology (else enter `<synology-ip>:32400`)
3. Authenticate with Plex account
4. Browse Media → Plex in sidebar to confirm library is visible

**✅ Checkpoint:** Plex library visible in HA.

#### Step 4: Manually trigger a movie (warm-start)

This step proves the Plex → Apple TV play path on its own, with the Apple TV already awake and Plex already foregrounded. The cold-start case (asleep Apple TV, Plex not running) is handled in Step 6.

1. Open Plex app on the Apple TV **at least once** so HA can register the Plex client entity. The client entity only exists in HA while Plex is actively running.
2. With Plex foregrounded on the Apple TV, go to HA → Developer Tools → Services:
   - Service: `media_player.play_media`
   - Target: the Plex-on-AppleTV entity (name will contain "plex" and "apple")
   - Data:
     ```yaml
     media_content_type: movie
     media_content_id: '190'   # Plex rating key — see "Lessons learned" below
     ```
3. Click Call Service — the chosen movie plays.

**Why rating key, not title:** title-based lookups (`media_content_id: 'Toy Story'`) are exact-match and case-sensitive against the title Plex actually stored, which is often `Toy Story (1995)` or similar. Numeric rating keys are bulletproof. Find them by opening the movie's detail page in Plex web (`http://<synology-ip>:32400/web`) — the URL ends in `...details?key=%2Flibrary%2Fmetadata%2F<NUMBER>`.

**✅ Checkpoint:** A movie plays via Developer Tools when Plex is already open on the Apple TV.

#### Step 5: Verify HDMI-CEC end-to-end

The Apple TV is the device that wakes when HA calls `media_player.turn_on`. The TV and soundbar follow via HDMI-CEC — same path the physical Siri Remote uses. If CEC isn't enabled at every hop, HA can wake the Apple TV silently while the TV stays black, and you'll spend an hour blaming HA.

1. **On the Apple TV:** Settings → Remotes and Devices → **Control TVs and Receivers → ON**
2. **On the TV:** enable HDMI-CEC. Brand names vary: Samsung "Anynet+", Sony "Bravia Sync", LG "Simplink", Vizio "CEC", Hisense "HDMI-CEC", Panasonic "Viera Link".
3. **On the soundbar:** enable HDMI-CEC, and confirm the Apple TV's audio path runs through it (HDMI-ARC/eARC).
4. **Verify with the physical remote first.** Sleep the Apple TV (hold Home/TV button → Sleep), wait 10s, press any button on the Siri Remote. TV + soundbar + Apple TV should all wake together. If the physical remote doesn't do it, fix CEC before involving HA.

**✅ Checkpoint:** Physical Siri Remote wakes TV + soundbar + Apple TV from a fully asleep state.

#### Step 6: Cold-start webhook (the real thing)

This is the webhook the NFC trigger will eventually call. It has to handle the full asleep → playing path.

1. HA → Settings → Automations & Scenes → Create Automation → Create new automation
2. Top-right ⋯ → **Edit in YAML**, paste this (substituting your own movie title and rating key):

   ```yaml
   alias: Play Super Mario Bros Movie webhook
   description: Cold-start — wake Apple TV, launch Plex, play The Super Mario Bros. Movie
   triggers:
     - webhook_id: play_super_mario_movie
       allowed_methods:
         - POST
       local_only: true
       trigger: webhook
   actions:
     # 1. Wake Apple TV (also wakes TV + soundbar via HDMI-CEC)
     - target:
         entity_id: media_player.living_room
       action: media_player.turn_on

     # 2. Wait until Apple TV reports awake
     - wait_template: |-
         {{ states('media_player.living_room') not in
            ['off', 'standby', 'unknown', 'unavailable'] }}
       timeout: "00:00:15"
       continue_on_timeout: true

     # 3. Buffer — Apple TV reports ready slightly before the launcher is responsive
     - delay: "00:00:02"

     # 4. Launch Plex
     - target:
         entity_id: media_player.living_room
       data:
         source: Plex
       action: media_player.select_source

     # 5. Wait for the Plex client entity to come up. Note: NO continue_on_timeout —
     #     if the entity never reaches a usable state, fail loudly so the logbook
     #     surfaces the real problem (often a stale Plex client UUID, see lesson #10).
     - wait_template: >-
         {{ states('media_player.plex_plex_for_apple_tv_apple_tv') in ['idle',
         'paused', 'playing'] }}
       timeout: "00:00:30"

     # 6. Settle so Plex finishes foregrounding
     - delay: "00:00:08"

     # 7. Warm up the Plex Companion session — sending any command forces the
     #     control channel to re-establish before play_media. Without this, a stale
     #     session will silently swallow the play_media call (see lesson #6).
     - target:
         entity_id: media_player.plex_plex_for_apple_tv_apple_tv
       action: media_player.media_play
       continue_on_error: true
     - delay: "00:00:02"

     # 8. Play the movie, with event-driven retry — wait_template confirms playback
     #     actually started before exiting; only retry on real timeout (see lesson #9).
     - repeat:
         sequence:
           - target:
               entity_id: media_player.plex_plex_for_apple_tv_apple_tv
             data:
               media_content_id: "190"   # rating key, not title
               media_content_type: movie
             action: media_player.play_media
           - wait_template: >-
               {{ states('media_player.plex_plex_for_apple_tv_apple_tv') == 'playing'
               and state_attr('media_player.plex_plex_for_apple_tv_apple_tv',
               'media_content_id') | string == '190' }}
             timeout: "00:00:15"
             continue_on_timeout: true
           - if:
               - condition: template
                 value_template: >-
                   {{ states('media_player.plex_plex_for_apple_tv_apple_tv') == 'playing'
                   and state_attr('media_player.plex_plex_for_apple_tv_apple_tv',
                   'media_content_id') | string == '190' }}
             then:
               - stop: Movie is playing
         until:
           - condition: template
             value_template: "{{ repeat.index >= 3 }}"
   mode: single
   ```

   The working copy of this YAML lives at `test/home-assistant/play_mario.yaml` in the repo and is the canonical source. If you tune timing or fix a bug, update there first; this inline version is for narrative reference and may lag behind.

3. Save, sleep the Apple TV, wait 10s, then from your laptop:
   ```bash
   curl -i -X POST http://<pi-lan-ip>:8123/api/webhook/play_super_mario_movie
   ```
4. Watch: TV on → soundbar on → Apple TV wakes → Plex opens → movie plays. Single command from full cold.

**Why this YAML works:**
- `media_player.turn_on` (rather than `remote.send_command turn_on`) uses the Companion protocol from Step 2 — same mechanism the physical remote uses; TV and soundbar follow via CEC.
- `media_player.select_source: Plex` is cleaner than `remote.send_command launch_app` for opening Plex from cold — the source list comes from pyatv's discovery and doesn't depend on bundle-ID strings.
- **The Companion warm-up poke (step 7) is the most important reliability fix.** Plex Companion sessions go stale after periods of inactivity; the HA entity keeps reporting `idle` even when the underlying control channel is dead. Sending *any* command (here, `media_player.media_play` with `continue_on_error: true`) forces the session to re-establish before `play_media` lands. Without this, the automation behaves "sometimes works, sometimes the home screen sits there" — see lesson #6.
- **Event-driven retry (step 8), not time-driven.** Each `play_media` call is followed by a `wait_template` that watches for `state == 'playing'` for up to 15s. We only retry if the wait truly times out, meaning the previous call actually didn't take. A naive fixed-delay retry caused duplicate `play_media` calls when the state hadn't propagated yet, which Plex interpreted as "restart the movie" — see lesson #9.
- **No `continue_on_timeout: true`** on the post-`select_source` wait_template. Failures fail loudly into the HA logbook instead of silently moving on. See lesson #8.

**Cold-start gotcha — Apple ID picker.** If the Apple TV has multiple user accounts, tvOS shows a "Who's watching?" picker before any app gets foreground. Plex launches behind it; `play_media` fires into nothing. **Fix:** Settings → Users and Accounts → switch to a single user (or set a default). Right call for a kid's movie box anyway — Von shouldn't be picking accounts. ✅ Resolved in this house — picker is disabled.

**✅ Checkpoint:** Single `curl` plays the movie from a fully asleep Apple TV.

#### Step 7: Pause webhook (dropped from v1)

This was originally a separate Phase 1 step, then planned to fold into the Phase 4 play/pause button automation. With v1 dropping the play/pause button entirely (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)), **v1 has no pause path at all** — pause is handled by the Siri Remote. There is no pause webhook to build for v1.

(The deferral chain: originally this pointed at the Phase 3 `nfc/removed` automation, which was struck when the interaction model changed — see [ADR 0001](./docs/adr/0001-tap-and-go-instead-of-continuous-presence.md) — then at the Phase 4 button automation, now also dropped per ADR 0002.)

If you want a manual pause for testing in the meantime, it's a one-action automation:
```yaml
- target:
    entity_id: media_player.plex_plex_for_apple_tv_apple_tv
  action: media_player.media_pause
```

#### Phase 1 troubleshooting

- **`media_player.turn_on` does nothing from HA:** Companion pairing didn't complete. Settings → Devices & services → Apple TV integration → Reconfigure → step through pairing again. Companion is a *separate* pairing flow from AirPlay; both must complete.
- **Apple TV wakes but TV/soundbar stay off:** HDMI-CEC is off somewhere in the chain. Test the physical Siri Remote first — if that also fails, fix CEC at the device level before touching HA.
- **Apple TV stops at "Who's watching?" picker:** multiple users configured on Apple TV. Settings → Users and Accounts → switch to a single user. *(Resolved in this house — picker is disabled. Leaving entry in case it ever re-appears after a tvOS update.)*
- **Apple TV sleeps too deeply during testing:** Settings → General → Sleep After → set a long interval (or Never) while debugging so sleep depth doesn't confound other failures.
- **Plex client entity missing from HA:** open Plex on the Apple TV once, then reload the Plex integration (Devices & services → Plex → ⋯ → Reload). The entity only registers while Plex is running.
- **Plex opens but `play_media` does nothing:** Plex client entity name may have shifted, or the rating key doesn't exist. Developer Tools → States, search "plex", confirm the entity ID. Verify the rating key by opening the movie's detail page in Plex web — the URL contains the key.
- **Plex opens but movie sits at home screen, especially after Plex has been idle for hours:** Plex Companion session went stale. The warm-up poke in step 7 of the working YAML is the fix. See lesson #6.
- **Movie starts playing then jumps back to the beginning a few seconds later:** retry loop double-fired `play_media` because state hadn't propagated within the fixed delay. The event-driven retry in step 8 of the working YAML is the fix. See lesson #9.
- **Automation worked for weeks then suddenly stopped, even though Plex looks fine:** Plex Media Server registered a new client UUID (often after a Plex app update on the Apple TV) and the YAML is now pointing at the old, ghosted entity. Check Devices & services → Plex Media Server for two "Plex (Plex for Apple TV ...)" devices; one will be greyed-out/disabled with `restored: true` state. See lesson #10.
- **Webhook returns 200 but nothing happens:** Developer Tools → Logbook (or Settings → System → Logs) shows the automation run and which action failed. Usually a misnamed entity.

#### Phase 1 done when

- [x] HA running on the Pi at `http://<pi-lan-ip>:8123`
- [x] Apple TV paired — both AirPlay *and* Companion auth completed
- [x] HDMI-CEC verified: physical remote wakes TV + soundbar + Apple TV
- [x] Plex integration connected, library visible
- [x] Plex-on-AppleTV `media_player` entity exists
- [x] `curl` webhook plays the movie from a fully asleep Apple TV (one command, full cold start)
- [x] Pause webhook — *dropped from v1 (no play/pause button — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)); Siri Remote covers pause*
- [ ] Tailscale set up — *optional, no blocker*

#### Phase 1 outcomes — values to reuse in Phase 3

These are the actual entity IDs and config strings that worked in this house. Phase 3 automations should target the same entities; treat this as the source of truth.

| Thing | Value |
|---|---|
| HA URL (LAN) | `http://192.168.0.122:8123` |
| Apple TV `media_player` entity | `media_player.living_room` |
| Plex-on-AppleTV `media_player` entity | `media_player.plex_plex_for_apple_tv_apple_tv` *(verify before trusting — see lesson #10; this entity ID is not guaranteed stable across Plex app updates)* |
| Plex source name (for `select_source`) | `Plex` |
| First proven movie (rating key) | The Super Mario Bros. Movie → `190` |
| Working webhook ID | `play_super_mario_movie` |

#### Lessons learned in Phase 1

Hard-won facts. Each of these cost time; capturing them so they don't have to be re-derived.

1. **Use Plex rating keys, not titles.** `media_content_id: 'Toy Story'` is exact-match against the stored title. Plex stores movies with metadata-fetched titles like `Toy Story (1995)`, and a single character mismatch fails silently — Plex opens, nothing plays. Numeric rating keys are permanent and unambiguous. Find one via the movie detail page URL in Plex web: `...details?key=%2Flibrary%2Fmetadata%2F190` → rating key `190`. Build the Phase 3 NFC mapping as `{uid: rating_key}`, not `{uid: title}`.
2. **Companion auth is separate from AirPlay auth.** When pairing the Apple TV integration, both flows must complete. Without Companion, `media_player.turn_on` does nothing.
3. **`media_player.select_source: Plex` beats `remote.send_command launch_app`.** Cleaner, doesn't depend on bundle IDs, uses the source list pyatv discovered for free.
4. **Plex client reports ready before its session is.** A short delay (~8s in the current YAML) between launching Plex and calling `play_media` is necessary but **not sufficient** — superseded in practice by lessons #6 (Companion warm-up) and #9 (event-driven retry), both of which were derived after the initial Phase 1 sign-off. The 5s number originally noted here was a first approximation; the real reliability comes from the warm-up + retry combo, not the delay alone.
5. **The Apple ID picker silently breaks automation.** Multiple users on Apple TV → tvOS shows a "Who's watching?" picker after wake → Plex launches behind it but never gets foreground → `play_media` lands in nothing. Single user account on Apple TV is the fix and is the right setting for a kid's box anyway. **Status:** picker disabled on this Apple TV (2026-05-06).
6. **Plex Companion sessions go stale after periods of inactivity.** The HA Plex client entity will keep reporting `idle` (cached) even after the underlying Plex Media Server ↔ Plex-on-Apple-TV control channel has died. `play_media` against a stale Companion session succeeds at the API level but never reaches the Apple TV — symptom: Plex opens to home screen, movie never starts. **Symptom pattern:** automation works right after the Apple TV's Plex app was last used, fails after hours of idle, then "magically" works again once you manually navigate Plex. **Fix:** before issuing `play_media`, send any harmless command to the Plex client entity (e.g. `media_player.media_play` with `continue_on_error: true`) to force the Companion session to re-establish. Then proceed with `play_media`. The warm-up poke is the difference between "works sometimes" and "works every time."
7. **`media_content_id` alone is a weak success check.** `state_attr(..., 'media_content_id')` can still match the previous movie's rating key for a moment after Plex stops — using it as the only retry-loop exit condition can cause the loop to falsely conclude playback started. Always pair it with `states(...) == 'playing'`.
8. **`continue_on_timeout: true` on a wait_template hides root causes.** It's tempting to add for "robustness," but it just makes failures invisible. Leave wait_templates failing loudly during development; only add it once the underlying timing issue is understood and the automation has its own retry/recovery path.
9. **Retry loops with fixed delays cause duplicate `play_media` calls.** A `repeat` with `play_media → fixed delay → check state` will fire `play_media` more than once whenever the entity's state hasn't propagated within the delay window — and the second call to Plex with the same rating key is interpreted as "restart the movie," visible as the movie playing then jumping back to the beginning a few seconds later. **Fix:** replace the fixed delay with a `wait_template` (timeout 10–15s) that waits for `state == 'playing'`. Retry only on timeout — i.e., only when there's real evidence the previous call didn't take. This converts a "fire-and-hope" retry into a "fire-and-confirm" retry.
10. **Plex registers multiple client UUIDs for one Apple TV over time.** When the Plex app on Apple TV updates, signs out/in, or otherwise re-registers, Plex Media Server creates a new client identity without removing the old one. HA's Plex integration faithfully creates a separate device entry for each UUID. Only one of them is what the live Plex app reports under at any given moment; the rest become ghost entities (`restored: true`, `unavailable`). **How to detect:** Settings → Devices & services → Plex Media Server shows two "Plex (Plex for Apple TV ...)" entries, often differing in firmware version or "by Plex" vs "by tvOS" manufacturer string. **Fix:** in Plex web (`http://<synology-ip>:32400/web`) → Account → Authorized Devices, find the duplicate Apple TV entries and remove the stale one (older "last seen"). Then reload the HA Plex integration. Periodic re-check is wise — automations that once worked can silently break this way.
6. **HA on Pi, not Synology.** Synology Container Manager's Docker has known issues extracting modern HA image layers (`failed to register layer ... archive/tar: invalid tar header`). The Pi runs vanilla Docker, updates cleanly. This is now baked into the architecture; not revisiting.

### Phase 2: NFC reading on the Pico (1 evening)

**Goal:** Pico detects a tag tap and prints the UID *once per tap* over USB serial.

- Use VS Code + MicroPico extension (already set up).
- MicroPython firmware is already flashed (sub-milestone 1 done).
- Wire up PN532 over I2C: 4 wires — VCC→3V3 (Pico pin 36), GND (pin 38), SDA→GP4 (pin 6), SCL→GP5 (pin 7). I2C0 peripheral, 100 kHz. **PN532 DIP switches must be set to I2C** (`SEL0 = OFF, SEL1 = ON`; ships in HSU/UART by default). — sub-milestone 2.
- Install `micropython-adafruit-pn532` or equivalent MicroPython NFC library (copy the `.py` file into the Pico's `lib/` — MicroPython doesn't have `pip install`). Library hunting was deferred during sub-milestone 2; raw-protocol `GetFirmwareVersion` bytes were enough to confirm the chip talks. Pick a library now for sub-milestone 3 (tag reading).
- Write a polling script that:
  - Polls the PN532 at ~10Hz for a present tag.
  - When a UID is read that wasn't present on the previous poll, prints `TAPPED: <UID>` once.
  - Suppresses further `TAPPED` lines for that UID until the tag has been absent for ~2s (or until a different UID is read).
  - That's it — no `PLACED`/`REMOVED` pair, no continuous-presence semantics.
- Program (or just note the UIDs of) several NTAG215 stickers — read-only is fine since mapping lives in HA.

**Why the absence cooldown:** a 3.5-year-old will hold a tag against the box for several seconds. We don't want one tap to produce ten events. The cooldown also gives the right semantics if Von leaves a tag sitting on the box: it fires once and stays quiet.

#### Lessons learned in Phase 2

1. **HiLetgo PN532 V3 (red board) DIP switches for I2C: `SEL0 = OFF, SEL1 = ON`.** Board ships in HSU/UART (both OFF). Without flipping switch 2 to ON the chip never appears on the I2C bus and you'll think wiring is wrong. Check the silkscreen on the back next to the switch block for the truth table — it varies by clone.
2. **The PN532's I2C address is `0x24`.** Some online references say `0x48` (the 8-bit shifted form) — MicroPython's `I2C.scan()` returns 7-bit addresses, so the correct hit is `0x24`. Anything else means wrong DIP setting or wrong wiring.
3. **Pico 2 WH on a standard breadboard straddles the center gap with pins in columns C and H** (board is ~0.7"/7-holes wide). Pin 1 (GP0) is the corner pin closest to USB; pin numbering goes down the left side 1→20, then up the right side 21→40. For pins 1–20, breadboard row = pin number. For pins 21–40, breadboard row = `41 − pin_number`.
4. **`GetFirmwareVersion` over raw I2C is the cleanest "is this chip alive" test.** Send `00 00 FF 02 FE D4 02 2A 00`; expect an ACK (`00 00 FF 00 FF 00`), then a response whose payload contains `D5 03 32 VV RR SS` — the `0x32` is the IC marker for PN532, `VV.RR` is the firmware version, `SS` is the supported-protocols bitfield. Confirmed this batch reports firmware **1.6** with support byte `0x07`. Using raw bytes here (instead of pulling in a library first) kept the variables isolated for debugging — recommend this for any future I2C peripheral bring-up.
5. **The PN532 asserts a status byte (`0x01` = ready) before each I2C read.** Poll the first byte; once it's `0x01`, the next read returns the actual frame. Skipping the ready check returns stale/garbage bytes.
6. **`InListPassiveTarget` blocks until a tag is found by default.** Set `MxRtyPassiveActivation = 0` via `RFConfiguration` (item 5) during init so the command returns immediately when no tag is in field. Without this, a 10Hz poll loop is impossible — the chip will sit in the command waiting forever. The default is `0xFF` (infinite retries).
7. **UID lengths identify the tag family at a glance.** ISO14443A: 4-byte UIDs are typically Mifare Classic / Ultralight; 7-byte UIDs starting with `0x04` are NXP NTAG (213/215/216 — the ones we'll be using). Useful for "is this the right kind of tag" debugging without a separate read step.
8. **The PN532's anticollision will alternate between multiple tags in field.** When two ISO14443A tags are simultaneously within range, successive `InListPassiveTarget` calls return whichever one the anticollision tree happened to settle on that cycle — often flipping between them. Edge-triggered "new UID" logic interprets each flip as a fresh tap and fires repeatedly. The fix is operational, not code: Von only ever taps one tag at a time. During bench testing, watch for tags stuck together (e.g. an NTAG sticker on the back of a kit card) — that was the first false-alarm in this house.
9. **2-second absence cooldown comfortably exceeds toddler tap cadence.** Empirically, the user can't physically tap-pull-tap fast enough to beat a 2s window. This validates the `ABSENCE_MS = 2000` constant — no need to tune it further until/unless Von tries something we haven't anticipated.

### Phase 3: Box talks to HA via MQTT (1 evening)

**Goal:** Tapping a tag plays the mapped movie. Tapping a different tag while one is playing switches movies. Tapping the same tag while it's already playing is a soft no-op.

**Pre-requisite:** Deploy Mosquitto MQTT broker as a Docker container on the Synology (compose shown in "Recommended order of operations" below). Add the MQTT integration to HA on the Pi, pointing at the Synology's LAN IP on port 1883. Configure credentials.

Note on network topology: HA on Pi, Mosquitto on Synology, Pico on Wi-Fi — all three communicate via the Synology's MQTT broker over LAN. The Pico's broker address is the Synology's LAN IP. HA connects to the broker at the Synology's LAN IP too.

**On the Pico:**

- Add Wi-Fi credentials (via `secrets.py`, gitignored).
- Use `umqtt.simple` (built into MicroPython) to connect to the broker.
- Extend the Phase 2 polling script: on each `tapped` event, publish to `vonbox/nfc/tapped` with payload `{"uid": "04A1B2C3"}`.
- Subscribe to `vonbox/state` for state updates from HA. The Pico uses these to:
  - Know whether a session is active and for which UID (so re-taps of the same UID stay local)
  - Drive the LED ring (off/idle/loading/playing/paused/standby/error)
- Implement automatic reconnection if Wi-Fi or MQTT drops.

**On HA:**

- Create a tag-UID-to-Plex-rating-key mapping. Recommended shape: a YAML config or an `input_text` helper holding a JSON blob, e.g. `{"04A1B2C3": "190", "04D5E6F7": "456"}`. **Rating keys, not titles** — see Phase 1 lesson #1.
- Automation on `vonbox/nfc/tapped` MQTT message (every `vonbox/state` publish uses the **tagged payload** — see "vonbox/state payload" below):
  1. Look up rating key from UID. If unknown → publish `vonbox/state` `{"state": "error", "uid": "<uid>", "title": null, "reason": "unknown_tag"}` and return.
  2. If the Apple TV is currently playing this rating key → publish `vonbox/state` `{"state": "already_playing", "uid": "<uid>", "title": "<title>", "reason": null}` and return. (Pico will produce the "already playing" local cue. This is a safety belt — the Pico should already have suppressed the event, but covers cases where the Pico's state got out of sync.)
  3. Otherwise, run the cold-start / switch-movie sequence: wake Apple TV if needed, select Plex source if needed, `play_media` with the new rating key. Same machinery as the Phase 1 webhook. (Optionally publish `{"state": "loading", "uid": "<uid>", ...}` while the wake/play sequence is in flight.)
  4. Publish `vonbox/state` `{"state": "playing", "uid": "<uid>", "title": "<title>", "reason": null}` once Apple TV reports `state == 'playing'` with the matching rating key.
- Watch the Apple TV `media_player.living_room` entity for state transitions and republish to `vonbox/state` accordingly (always the tagged payload):
  - Apple TV `playing` → `{"state": "playing", "uid": "<whichever>", "title": "<title>", "reason": null}`
  - Apple TV `paused` → `{"state": "paused", "uid": "<whichever>", "title": "<title>", "reason": null}`
  - Apple TV `standby` / `off` / `idle` for >N seconds → `{"state": "standby", "uid": null, "title": null, "reason": null}` (this is what tells the Pico the session has ended)

**No removal automation.** The `vonbox/nfc/removed` topic from the old design is gone. v1 has no on-box pause (the play/pause button was dropped — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)); pause is the Siri Remote's job, and session-end comes from the Apple TV going to sleep.

#### `vonbox/state` payload (canonical)

Every message on `vonbox/state` uses the same **tagged** JSON shape — never a
bare-key form like `{"playing": "<uid>"}`. All four keys are always present
(`uid` / `title` / `reason` are `null` when not applicable):

```json
{"state": "<NAME>", "uid": "<HEX|null>", "title": "<str|null>", "reason": "<str|null>"}
```

`<NAME>` is one of the state-vocabulary names, each mapping to a ring animation +
buzzer cue (full table in "User feedback vocabulary"):

| `state` | meaning | `reason` |
|---|---|---|
| `idle` | box awake, ready for a tap | `null` |
| `loading` | tap sent, waiting for playback to start | `null` |
| `playing` | movie confirmed playing | `null` |
| `already_playing` | same tag re-tapped, session active (transient cue) | `null` |
| `paused` | movie paused (e.g. Siri Remote) | `null` |
| `standby` | Apple TV asleep / session ended | `null` |
| `error` | unknown tag or playback failure (transient cue) | carries a short string, e.g. `"unknown_tag"` |

`tap_accepted` is **not** a `vonbox/state` value — it is purely local instant
feedback the Pico fires itself on a fresh tap, before any MQTT round-trip.

#### Lessons learned in Phase 3

1. **Mosquitto in Docker runs as in-container UID 1883, not root.** Bind-mounted directories created with `sudo mkdir` on the Synology host are owned by `root`, so the `mosquitto` user inside the container can't write logs or read the password file — the container ends up in a tight crash-loop with `Error: Unable to open log file` / `Unable to open pwfile`. Fix is one `chown -R 1883:1883 /volume1/docker/mosquitto` on the host after deploying the stack. Worth doing **before first start** if possible to skip the crash-loop entirely.
2. **Mosquitto's password file must be `0700` and not world-readable.** Earlier 1.x versions warned; current 2.x increasingly refuses. `sudo chmod 0700 /volume1/docker/mosquitto/config/passwd` (and `/data/mosquitto.db`) at create time skips a noisy warning that's easy to confuse with the real ownership error above.
3. **`mosquitto_passwd` lives inside the container, not on the Synology host.** Use `docker exec -it mosquitto mosquitto_passwd -b /mosquitto/config/passwd <user> <password>` to create/update users — saves an apt install on the host and avoids version skew. Restart the container after editing the password file so Mosquitto rereads it.
4. **Mosquitto 2.x silently drops unauthenticated TCP connections.** From a client this surfaces as `Bad file descriptor` (not the older 1.x-era `Connection Refused: not authorised`). If a `mosquitto_sub` with no `-u`/`-P` flags shows that error, the broker is actually up and rejecting you — supply credentials and retry. Real broker-down looks like `Connection refused` at the TCP layer.
5. **Port 1883 is the MQTT protocol, not HTTP.** Browsers can't speak to it, and `http://broker:1883` will sit there spinning. To test reachability use `mosquitto_pub`/`mosquitto_sub` or `nc -vz <host> 1883`. Worth flagging because "the URL doesn't load" was the first thing checked here and was a dead-end.
6. **`umqtt.simple` is the right MQTT client for the Pico.** Ships with MicroPython, ~one-screen surface area, no dependencies. The `client_id` should be a unique bytes value (we're using `b"vonbox-pico"`); the broker uses it for session resumption and to disambiguate connections.
7. **`from secrets import ...` requires `secrets.py` on the Pico's flash.** MicroPico's "Run current file on Pico" only sends the active file; imports resolve against the Pico's filesystem. Upload `secrets.py` once via "Upload current file" (or whatever your MicroPico version names it) before running any test that imports it. First place in the project where we stopped being fully ephemeral.
8. **`umqtt.simple` is *not* frozen into the `RPI_PICO2_W` MicroPython 1.28.0 build.** `import umqtt.simple` raises `ImportError: no module named 'umqtt'` straight from a fresh flash, despite older project notes (and a fair amount of community lore) treating it as built-in. The fix is one-shot: connect to Wi-Fi, then `import mip; mip.install("umqtt.simple")` — this writes `/lib/umqtt/simple.mpy` to the Pico's flash and survives reboots. `test/bench/install_umqtt.py` automates this; only needs to run once per fresh Pico. After install, the heartbeat publisher in `test/bench/mqtt_hello_test.py` ran clean and the laptop subscriber received every message.
9. **The PN532 retains in-flight I2C state across a MicroPico hot-restart.** When MicroPico's "Stop execution" interrupts a polling loop mid-frame, the chip's I2C buffer is left holding the tail of an unfinished response. The next script's first `SAMConfiguration` then *seems* to succeed at `_wait_ready` (the chip reports the leftover status byte as `0x01`) but the subsequent 7-byte ACK read NACKs with `OSError: [Errno 110] ETIMEDOUT`. Symptom is: orchestrator gets through Wi-Fi + MQTT, then immediately throws inside `PN532.init()`. **Manual fix:** unplug the Pico's USB for ~3s and re-run (full 3V3 cycle drains the chip). **Programmatic fix:** retry `SAMConfiguration` once with a 50ms gap inside `PN532.init()` — the first call's preamble forces the chip to discard the stale frame, the second call succeeds. Implemented in `lib/pn532.py` so day-to-day MicroPico use doesn't require unplugging.
10. **`lib/` modules need to be uploaded to the Pico's flash, separately from the running `test/` script.** MicroPico's "Run current file on Pico" only ships the active file; `from pn532 import PN532` resolves against the Pico's filesystem, not the project on disk. When `lib/pn532.py` is edited, re-upload it via MicroPico's "Upload current file" before re-running the orchestrator. Same rule that already applied to `secrets.py` (lesson #7) — anything that gets `import`ed must live on flash.

### Phase 4: NeoPixel ring + buzzer + OLED (1–2 evenings)

**Goal:** Full feedback vocabulary working on the bench-breadboarded box.

> **v1 scope (see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)):** the rotary encoder (volume) and play/pause button are dropped from v1, so this phase is now output-only — LED ring, buzzer, OLED. The deferred input bits (encoder → `vonbox/volume/*` + Apple TV volume automation; button → `vonbox/button/play_pause` + pause/resume automation) move to a later iteration if the controls come back.

- ✅ **NeoPixel ring — wired and bench-tested** (2026-06-08): `DIN`→GP28, `PWR`→VSYS, `GND`→shared ground (see the CLAUDE.md pin-allocation table). `test/bench/led_ring_test.py` confirms all 24 pixels, correct colors, no flicker, with brightness capped at 25% in firmware. It needs exactly **3 wires**: `PWR`→VSYS (5V), `GND`→Pico GND, `DIN`→a PIO-capable GPIO (any GPIO on the Pico can do PIO). Leave the `DOUT` (data-out) pad empty — it's only for chaining a second ring — and note the duplicate PWR/GND pads are bussed together, so wire just one of each. Data is directional: it must enter at `DIN`. Power considerations:
  - 24 LEDs at 25% brightness draw ~360mA — Pico's 3V3 regulator can't handle this. Power LEDs from VSYS (raw 5V from USB) and share ground with the Pico. All-white at full brightness would pull ~1.4A, which VSYS/USB can't supply either, so cap brightness in firmware and avoid sustained all-white.
  - Use a level shifter or 330Ω series resistor on the data line if color quality looks off (5V LEDs, 3.3V signal usually works fine in practice).
- ✅ **Buzzer — wired and bench-tested** (2026-06-08): KY-006 passive piezo on GP22 (signal) + GND, middle header pin unused, driven directly by PWM — no transistor or VCC. `test/bench/buzzer_test.py` auditions success / error / neutral cues plus a 150 Hz→4 kHz range sweep. Final cue picks (what becomes `play_success()` / `play_error()`) are still TBD.
- ⬜ Wire OLED to the same I2C bus as the PN532 (shared SDA/SCL, different I2C addresses — no conflict). MicroPython has `ssd1306` built in. *(Not yet wired — the remaining Phase 4 hardware.)*
- MicroPython animation functions for each LED state defined in "User feedback vocabulary."
- MicroPython tone-playing functions for each buzzer event.
- OLED renders current state (idle / playing / paused / error / movie title).

**State sync:** the Pico subscribes to `vonbox/state` MQTT topic. HA publishes state updates there using the canonical tagged payload (e.g. `{"state": "playing", "uid": "04A1B2C3", "title": "Toy Story", "reason": null}` — see "`vonbox/state` payload (canonical)" in Phase 3), and the Pico updates LEDs, OLED, and its own "session active" tracking accordingly. This is what lets the Pico tell "same tag = no-op" from "new tag = switch."

#### Testing the feedback loop away from home

The full `tap → local feedback → MQTT → state → ring/buzzer` choreography can be
exercised with **no home network, no Home Assistant, and no Apple TV** — because
the Pico only speaks MQTT, you swap just the broker (run Mosquitto on the laptop)
and the thing behind it (a fake HA). Pico firmware is unchanged except
`secrets.py`. Three layers, lowest-first ("one variable at a time"):

- **Layer 1 — pure hardware, no network:** `test/offline-harness/state_render_test.py` drives
  `lib/feedback.py` through every state on a timer. Tune animations and cues here.
- **Layer 2 — hand-publish state over MQTT:** run the laptop broker + the Pico
  loop and `mosquitto_pub` tagged `vonbox/state` payloads by hand to confirm the
  Pico reacts to messages off the wire.
- **Layer 3 — the full loop:** `test/offline-harness/full_loop_test.py` (Pico: Wi-Fi + MQTT +
  PN532; on tap fires `tap_accepted()`, publishes `vonbox/nfc/tapped`,
  optimistically sets `loading`, renders `vonbox/state`) talking to
  `test/offline-harness/mock_ha.py` (laptop: fake HA that subscribes to taps and publishes
  state), over the throwaway broker config `test/offline-harness/mosquitto.dev.conf`.

The harness uses the existing `ticks_ms` cooperative-loop pattern (`tick()`
advances at most one animation frame per main-loop pass, never blocks).
`asyncio` remains the intended approach for the final `main.py` — flagged here,
not yet adopted. Full runbook (iPhone-hotspot 2.4 GHz gotcha, laptop setup, run
order, troubleshooting): **`docs/testing-away-from-home.md`**.

### Phase 5: Enclosure v1 (prototype)

**Goal:** A physically usable box in the living room, however ugly.

**Wiring migration — breadboard → protoboard:**

- Move from breadboard to a **Pico-specific protoboard** (Pimoroni "Proto Board for Pico" or Adafruit "Perma-Proto for Pico", ~$3–5). These have the Pico's pinout labeled on the silkscreen so the layout is almost mechanical to transfer.
- Solder **female header sockets** onto the protoboard where the Pico's pins will go. The Pico 2 WH then plugs into these sockets — same as it did on the breadboard, just permanent.
- This keeps the Pico **removable and reprogrammable** without desoldering — critical for a toddler-facing device where you'll want to tweak firmware, debug Wi-Fi, or swap in a new Pico if one fries.
- Solder the rest of the connections (PN532 wires, NeoPixel ring, buzzer, OLED) to the protoboard with strain relief. Use JST or screw-terminal connectors where practical so individual components can be unplugged for maintenance. *(No encoder or button in v1 — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md).)*
- This trades ~15mm of vertical space (for the socket stack) for massively better reliability and serviceability. Not a meaningful tradeoff in a box this size.

**Enclosure design:**

- Design in Fusion 360 / OnShape / Tinkercad
- Box holds: Pico 2 WH on protoboard, PN532 under top surface (as close to the surface as possible — read range is short), NeoPixel ring just below top surface around the tap zone, OLED window on front face, USB cable out back for power, buzzer vented. *(No rotary encoder or play/pause button in v1 — see [ADR 0002](./docs/adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md); the top surface is just the tap zone + LED ring.)*
- The Pico is tiny (~21mm × 51mm) and runs cool — no heat management or ventilation needed
- **Tag token v1:** laminated cards with movie poster art and an NTAG215 sticker on the back. Cheapest, fastest, blog-post style. Lets you iterate on the box without committing to a 3D-printed token form.
- **Tag token v2+:** 3D-printed coins or mini figurines with a recess for the NTAG215 sticker. No magnet holes, no ferrite pocket — those were only needed for the old magnetic-mating design.
- **Print ring diffuser in translucent or white PLA**
- Keep v1 intentionally ugly — it's a functional prototype; aesthetics come later

### Phase 6+: Iteration

As you live with it:

- Custom tag-token designs — printed cards, 3D-printed coins, or mini figurines for Buzz, Lightning McQueen, etc.
- Battery + charging dock (pogo pins or magnetic connector) — Pico's low power means a modest LiPo should last days
- Parental controls in HA (no movies after bedtime, daily time limits)
- Richer OLED UI (movie poster thumbnails, time-remaining)
- Refined enclosure aesthetics
- Home Assistant dashboard view for dad to see what Von is watching / remotely pause / etc.

**The "v2 final form" — custom PCB:**

Once the design has been stable for 6+ months and you're confident nothing's going to change, graduate from protoboard to a **custom PCB** designed in KiCad (free). Order 5 boards from JLCPCB or OSHPark for ~$5 + shipping, ~2 week turnaround. Solder everything to your PCB, slide it into the enclosure — clean, professional, and fully replicable for anyone who wants to build their own via Coati.

The Pico 2 WH still plugs into sockets on the PCB — don't hardwire it even at this stage, for all the same reasons.

Prerequisite: ~1 weekend learning KiCad. Not required, but a genuinely useful skill for future maker projects.

---

## Open questions (explicitly deferred)

None currently. All clarifying questions have been resolved. New questions will emerge during each phase — track them there.

---

## Recommended order of operations

1. **Order parts** (2–5 day delivery)
2. **While waiting: do Phase 1 entirely** — no hardware needed, validates the highest-risk integration (Apple TV + Plex + HA). Deploy HA via Portainer on the Pi 4, pair Apple TV, trigger a test movie.
3. **While waiting: deploy Mosquitto MQTT broker** as a Portainer stack on the Synology so it's ready when you get to Phase 3:
   ```yaml
   services:
     mosquitto:
       container_name: mosquitto
       image: eclipse-mosquitto:latest
       restart: unless-stopped
       ports:
         - "1883:1883"
       volumes:
         - /volume1/docker/mosquitto/config:/mosquitto/config
         - /volume1/docker/mosquitto/data:/mosquitto/data
         - /volume1/docker/mosquitto/log:/mosquitto/log
   ```
   Create `mosquitto.conf` with `allow_anonymous false` and a password file. Create a user (e.g. `moviebox`) with `mosquitto_passwd`. Add the MQTT integration to HA pointing at the Synology's LAN IP on port 1883 with the credentials you created.

   Note: Mosquitto is a much simpler image than HA and Synology Docker handles it fine. If it happens to also fail, fall back to running Mosquitto on the Pi alongside HA.
4. **While waiting: install Tailscale on the Pi** (via `curl | sh` install script) + phone + laptop, so you can access HA privately from anywhere. Webhooks and MQTT still use LAN IPs — Tailscale is only for your browser.
5. **When parts arrive: Phase 2 → 3 → 4 → 5** in sequence
6. **Keep the Arduino/HERO board on the bench** throughout for bench-testing components (buzzer tones, LED patterns) before committing to Pico wiring — fastest dev loop for "does this component work?" is still an Arduino sketch

---

## Key references

- [Simply Explained: NFC Movie Library](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/) — original inspiration
- [Tonie Box 2](https://us.tonies.com/pages/toniebox2) — product inspiration
- [Raspberry Pi Pico 2 W](https://www.raspberrypi.com/products/raspberry-pi-pico-2/) — microcontroller docs
- [MicroPython on Pico docs](https://docs.micropython.org/en/latest/rp2/quickref.html) — PIO, networking, I2C reference
- [Thonny IDE](https://thonny.org/) — MicroPython dev environment
- Home Assistant Apple TV integration — uses `pyatv` under the hood
- Plex integration for HA — native support for `media_player.play_media` with movie titles
- HA MQTT integration + Mosquitto broker add-on
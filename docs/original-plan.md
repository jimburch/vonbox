# NFC Movie Box for Von — Project Plan

A Tonie-Box-inspired device that lets a 3.5-year-old start movies on the living room TV by placing 3D-printed figurines on top of a box. NFC identifies each figurine, Home Assistant translates that into commands for the Apple TV running Plex.

---

## Inspiration & Goal

Inspired by [Simply Explained's NFC movie library for kids](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/) and the [Tonie Box](https://us.tonies.com/pages/toniebox2).

Von (3.5 years old) already loves placing Cars and Toy Story figurines on his Tonie Box to play songs. This project brings that same physical-object-triggers-media experience to his movies. He should just put Buzz Lightyear on the box and Toy Story starts — no screens, no apps, no fuss.

---

## How it works (end-to-end flow)

1. Von places Buzz Lightyear figurine on the box
2. Box's NFC reader detects the tag, sends webhook to Home Assistant
3. HA wakes Apple TV, launches Plex, starts Toy Story
4. Apple TV plays on living room TV, audio through soundbar via HDMI-ARC/CEC
5. Von removes figurine → box sends "paused" webhook → HA pauses Plex
6. Von puts Buzz back within 1 hour → Plex resumes (native Plex behavior)
7. If >1 hour passes, HA clears Plex resume position → next placement starts from the beginning
8. Volume knob on box → sends Apple TV volume commands → soundbar adjusts via CEC
9. Replay button on box → restarts current movie from beginning

---

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Movie Box      │      │  Raspberry Pi 4  │      │  Apple TV       │
│  ─ Pico 2 WH    │◀───▶│  ─ Home Assistant│─────▶│  ─ Plex app     │
│  ─ PN532 NFC    │ MQTT │  ─ pyatv         │pyatv │  ─ Soundbar via │
│  ─ Rotary enc.  │      │  ─ Plex integr.  │      │    HDMI-CEC     │
│  ─ Replay btn   │      │  ─ Timer/state   │      │                 │
│  ─ NeoPixel ring│      │  ─ Cloudflared   │      │                 │
│  ─ Buzzer       │      │  (existing)      │      │                 │
│  ─ OLED display │      │                  │      │                 │
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

- **Brains live in Home Assistant, not on the box.** The Pico is a dumb input device that reads NFC and publishes events. HA owns all logic (tag-to-movie mapping, resume timers, Apple TV control). This means changing a movie mapping doesn't require reflashing the box.
- **Plex handles resume automatically.** The "resume within 1 hour" behavior is Plex's native behavior for free. HA only has to *clear* resume state if the hour elapses.
- **Volume passes through Apple TV → HDMI-CEC → soundbar.** Same path as the existing Apple TV remote.
- **NFC uses continuous polling** at ~10Hz for both placement AND removal detection (removal is what triggers pause).
- **MQTT for bidirectional Pico ↔ HA communication.** Event-driven, low-overhead, plays nicely with both sides. The Pico publishes events (placed, removed, volume, replay); HA publishes state updates back (playing, paused, error) so the Pico can update LEDs and the OLED.
- **Pico is immediately responsive**, HA confirms state. Some feedback is local (instant beep/LED on placement), some is HA-driven (confirmed "playing" state).

---

## Hardware

### From the Inventr "30 Days Lost in Space" Arduino kit (already owned)

- Rotary encoder module (KY-040 style)
- Passive buzzer module (can play actual tones via PWM)
- 0.96" OLED display (SSD1306, I2C)
- Tactile buttons
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
| NeoPixel ring, WS2812B, 16 LEDs | $8 | For the illuminated ring around the figurine zone |
| NTAG215 stickers, 50-pack | $10 | Any brand |
| NFC ferrite shielding stickers | $5 | Prevents magnet/metal RF interference |
| Neodymium disc magnets, 6mm x 2mm, 50-pack | $10 | For figurine/box connection |
| Mounting hardware (M2.5 screws, heat-set inserts) | $10 | For enclosure assembly |
| **Subtotal (Phases 1–4)** | **~$63** | Enough to prototype everything |
| Pico-specific protoboard (Pimoroni or Adafruit) | $5 | For Phase 5 — transfers breadboard layout to permanent wiring |
| Female header sockets (2x20 pin) | $3 | Pico plugs into these on the protoboard, stays removable |
| JST or screw-terminal connectors (optional) | $5 | For swappable component wiring |
| **Total (through Phase 5)** | **~$76** | |

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

## Figurine & box physical design

**Figurine base:**

- Custom 3D-printed characters (Buzz, Lightning McQueen, etc.) — one figurine per movie, 1:1 mapping
- Central recess holds an NTAG215 sticker
- Ferrite shield between NFC tag and any metal/magnets
- 3–4 neodymium magnets arranged in a ring around the NFC tag (geometry matters — tag centered, magnets offset to the sides to avoid RF detuning)

**Box top:**

- Flat zone where figurine sits, only big enough for one figurine at a time (prevents ambiguity)
- PN532 NFC antenna centered directly under the figurine placement zone
- Matching magnets in the top of the box to snap figurine into place
- NeoPixel 16-LED ring around the figurine zone, diffused through translucent PLA
- Rotary encoder through the top surface (volume)
- Replay button (tactile, easy for a toddler)
- OLED display in a window on the front face
- Buzzer vented for clear sound

**Materials:**

- Main box: standard PLA, any color
- Diffuser for LED ring: translucent/white PLA (Bambu makes one)
- Printed on Bambu Lab A1

---

## User feedback vocabulary

### NeoPixel ring states

| State | Animation | Color | Brightness |
|---|---|---|---|
| Idle (no figurine) | Slow breathing | Soft warm white | ~10% |
| Figurine placed | Quick sparkle → solid | Green | ~20% |
| Loading / contacting HA | Chase (single LED runs the ring) | Blue | ~30% |
| Playing | Steady solid | Green | ~20% |
| Paused (within 1hr resume window) | Slow breathing | Amber | ~15% |
| Unknown tag / error | 3 flashes | Red | ~40% |
| Replay pressed | White spiral, then back to green | White → Green | ~30% |
| Resume window expired | Single slow fade to off | Amber | → 0 |

### Buzzer sounds

- **Placement:** rising two-note chime ("got it")
- **Removal:** descending two-note chime ("paused")
- **Replay:** distinct "reset" chime (different from placement)
- **Error:** soft low tone, not harsh
- **Keep it musical and gentle** — a 3.5-year-old will hear these a lot

### OLED display

- **Idle:** clock or cute animation
- **Figurine detected:** movie title
- **Playing:** progress bar, elapsed time
- **Error:** human-readable error message (for the parent)

Useful for Von (magic factor), useful for dad (debugging).

### Replay button behavior

- **Press while playing:** restart from beginning of current movie
- **Press while paused (figurine still on, within resume window):** restart from beginning, clear resume state
- **Press while idle (no figurine):** do nothing, soft error beep
- **Long press (3s):** reserved for future use (parental override, box reset, etc.)

---

## Technical decisions locked in

- **Raspberry Pi Pico 2 W** running **MicroPython**
- **Home Assistant** (on Synology via Docker) + **pyatv** for Apple TV control
- **Plex API via HA** for movie triggering
- **MQTT** (Mosquitto broker on Synology) for Pico ↔ HA communication
- **PN532 NFC reader** with **NTAG215 stickers**
- **Continuous polling at 10Hz** for presence detection (~100ms responsiveness)
- **Rotary encoder** on PIO for volume (better than a pot for infinite rotation)
- **NeoPixels driven via PIO**, running at 25% brightness (safely powered from Pico's 3V3 or VSYS rail depending on final design)
- **One figurine per movie** (simple mental model)
- **Resume window: 1 hour**

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

#### Step 4: Manually trigger a movie

1. Open Plex app on the Apple TV **at least once** so HA can register the client entity (this step is required; client won't appear otherwise)
2. In HA: Developer Tools → Services:
   - Service: `media_player.play_media`
   - Target: the Plex-on-AppleTV entity (name will contain "plex" and "apple")
   - Data:
     ```yaml
     media_content_type: movie
     media_content_id: 'Toy Story'
     ```
3. Click Call Service — Apple TV should wake, Plex should open, Toy Story should play

**If the movie doesn't start:** add a pre-step that launches Plex via `remote.send_command` with `command: launch_app, device: com.plexapp.plex`, then delay 2s, then call `play_media`.

**✅ Checkpoint:** Toy Story plays on the living room TV, triggered from HA. 🎉

#### Step 5: Wrap it in a webhook

1. Settings → Automations & scenes → Create Automation → Empty
2. Configure:
   - Name: `Play Toy Story webhook`
   - Trigger: Webhook, ID `play_toy_story_test`
   - Actions:
     1. `remote.send_command` — launch Plex app
     2. Delay 2s
     3. `media_player.play_media` — Toy Story
3. Test from laptop:
   ```bash
   curl -X POST http://<synology-ip>:8123/api/webhook/play_toy_story_test
   ```

**✅ Checkpoint:** A single curl starts Toy Story on the Apple TV.

#### Step 6: Pause webhook

1. Create second automation, webhook ID `pause_playback`, action `media_player.media_pause`
2. Test:
   ```bash
   curl -X POST http://<synology-ip>:8123/api/webhook/pause_playback
   ```
3. Re-curl the play webhook — should resume from pause point (native Plex behavior)

**✅ Checkpoint:** Pause and resume both work via webhooks.

#### Phase 1 troubleshooting

- **Apple TV sleeps too deeply:** Settings → General → Sleep After → set long interval during testing
- **Plex client entity missing:** open Plex on Apple TV once, then reconfigure the Plex integration in HA
- **Movie starts on wrong device:** verify you're targeting the Apple TV Plex client, not a phone/iPad client
- **Webhook returns 200 but nothing happens:** check HA Logbook (sidebar) for automation execution errors, usually a misnamed entity

#### Phase 1 done when

- [ ] HA running on Synology at `http://<synology-ip>:8123`
- [ ] Apple TV paired, wakeable from HA
- [ ] Plex integration connected, library visible
- [ ] Plex-on-AppleTV `media_player` entity exists
- [ ] `curl` webhook plays Toy Story
- [ ] `curl` webhook pauses
- [ ] Re-triggering play resumes from pause

### Phase 2: NFC reading on the Pico (1 evening)

**Goal:** Pico detects figurine placement and removal, prints tag UIDs over USB serial.

- Install [Thonny](https://thonny.org/) on your laptop — easy MicroPython IDE with built-in Pico support
- Flash MicroPython firmware onto the Pico 2 W (Thonny can do this in a couple clicks, or flash the UF2 manually)
- Wire up PN532 over I2C (4 wires: 3V3, GND, SDA on GP0, SCL on GP1 — or any I2C-capable pair)
- Install `micropython-adafruit-pn532` or equivalent MicroPython NFC library (may need to copy a `.py` file to the Pico manually — MicroPython doesn't have `pip install`, it has `mpremote` or file copy)
- Write a polling script (10Hz) that prints `PLACED: <UID>` / `REMOVED: <UID>` over the USB serial REPL
- Program several NTAG215 stickers (or just note their UIDs — read-only works fine since we're mapping in HA)

### Phase 3: Box talks to HA via MQTT (1 evening)

**Goal:** Placing a figurine plays the movie; removing it pauses; 1-hour timeout restart works.

**Pre-requisite:** Deploy Mosquitto MQTT broker as a Docker container on the Synology (compose shown in "Recommended order of operations" below). Add the MQTT integration to HA on the Pi, pointing at the Synology's LAN IP on port 1883. Configure credentials.

Note on network topology: HA on Pi, Mosquitto on Synology, Pico on Wi-Fi — all three communicate via the Synology's MQTT broker over LAN. The Pico's broker address is the Synology's LAN IP. HA connects to the broker at the Synology's LAN IP too (not localhost, since they're on different devices now).

On the Pico:
- Add Wi-Fi credentials (via `secrets.py` or similar, never commit to git)
- Use `umqtt.simple` (built into MicroPython) to connect to the broker
- Extend NFC polling script: on place/remove events, publish to MQTT topics like:
  - `moviebox/nfc/placed` with payload `{"uid": "04A1B2C3"}`
  - `moviebox/nfc/removed` with payload `{"uid": "04A1B2C3"}`
- Subscribe to `moviebox/state` for incoming state updates from HA (used later in Phase 4)
- Implement automatic reconnection if Wi-Fi or MQTT drops

On HA:
- Create a tag-UID-to-movie-title mapping (YAML config, input_select helpers, or a custom lookup in automations)
- Automation on `moviebox/nfc/placed` MQTT message:
  - Look up movie from UID
  - If same UID as last placement AND within 1-hour window → `media_player.media_play` (resumes)
  - Else → launch Plex app + `play_media` with the mapped title
- Automation on `moviebox/nfc/removed` MQTT message:
  - `media_player.media_pause`
  - Start 1-hour timer (HA timer helper)
  - Remember last UID and timestamp
- On timer expiry: clear Plex resume state for that movie (via Plex API call) OR just forget last-UID so next placement starts fresh

### Phase 4: Rotary encoder + replay button + NeoPixel ring + buzzer + OLED (1–2 evenings)

**Goal:** Full feedback vocabulary working on the bench-breadboarded box.

- Wire rotary encoder using **PIO** (the Pico's killer feature for encoders — zero missed pulses). Publishes `moviebox/volume/up` or `moviebox/volume/down` on detent changes.
- Wire replay button (with debouncing) → publishes `moviebox/replay`
- HA automations handle volume (send Apple TV volume commands) and replay (`media_seek` to 0, or re-issue `play_media` with the same movie to restart)
- Wire NeoPixel ring data pin to a PIO-capable GPIO (any GPIO on the Pico can do PIO). Power considerations:
  - 16 LEDs at 25% brightness draw ~240mA — Pico's 3V3 regulator can't handle this. Power LEDs from VSYS (raw 5V from USB) and share ground with the Pico.
  - Use a level shifter or 330Ω series resistor on the data line if color quality looks off (5V LEDs, 3.3V signal usually works fine in practice).
- Wire buzzer to a PWM-capable GPIO (any Pico GPIO supports PWM)
- Wire OLED to the same I2C bus as the PN532 (shared SDA/SCL, different I2C addresses — no conflict). MicroPython has `ssd1306` built in.
- MicroPython animation functions for each LED state
- MicroPython tone-playing functions for each buzzer event
- OLED renders current state (idle / placed / playing / error)

**State sync:** the Pico subscribes to `moviebox/state` MQTT topic. HA publishes state updates there (e.g. `{"state": "playing", "movie": "Toy Story"}`), and the Pico updates LEDs and the OLED accordingly. This is cleaner than HTTP-back-to-the-device and comes essentially for free once the MQTT broker is set up in Phase 3.

### Phase 5: Enclosure v1 (prototype)

**Goal:** A physically usable box in the living room, however ugly.

**Wiring migration — breadboard → protoboard:**

- Move from breadboard to a **Pico-specific protoboard** (Pimoroni "Proto Board for Pico" or Adafruit "Perma-Proto for Pico", ~$3–5). These have the Pico's pinout labeled on the silkscreen so the layout is almost mechanical to transfer.
- Solder **female header sockets** onto the protoboard where the Pico's pins will go. The Pico 2 WH then plugs into these sockets — same as it did on the breadboard, just permanent.
- This keeps the Pico **removable and reprogrammable** without desoldering — critical for a toddler-facing device where you'll want to tweak firmware, debug Wi-Fi, or swap in a new Pico if one fries.
- Solder the rest of the connections (PN532 wires, NeoPixel ring, encoder, button, buzzer, OLED) to the protoboard with strain relief. Use JST or screw-terminal connectors where practical so individual components can be unplugged for maintenance.
- This trades ~15mm of vertical space (for the socket stack) for massively better reliability and serviceability. Not a meaningful tradeoff in a box this size.

**Enclosure design:**

- Design in Fusion 360 / OnShape / Tinkercad
- Box holds: Pico 2 WH on protoboard, PN532 under top surface, rotary encoder through top, replay button through top, NeoPixel ring just below top surface around figurine zone, OLED window on front face, USB cable out back for power, buzzer vented
- The Pico is tiny (~21mm × 51mm) and runs cool — no heat management or ventilation needed
- Figurine base template: centered NFC sticker recess, ferrite shield pocket, 3–4 magnet holes arranged around
- Top of box has matching magnets with correct polarity
- **Print ring diffuser in translucent or white PLA**
- Keep v1 intentionally ugly — it's a functional prototype; aesthetics come later

### Phase 6+: Iteration

As you live with it:

- Custom figurine designs (Buzz, Lightning McQueen, others)
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
6. **Keep the Arduino/HERO board on the bench** throughout for bench-testing components (buzzer tones, LED patterns, encoder behavior) before committing to Pico wiring — fastest dev loop for "does this component work?" is still an Arduino sketch

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
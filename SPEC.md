---
created: 2026-04-20, 3:48 PM
updated: 2026-04-29
tags:
---
# NFC Movie Box for Von — Project Plan

A Tonie-Box-inspired device that lets a 3.5-year-old start movies on the living room TV by placing 3D-printed figurines on top of a box. NFC identifies each figurine, Home Assistant translates that into commands for the Apple TV running Plex.

---

## Inspiration & Goal

Inspired by [Simply Explained's NFC movie library for kids](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/) and the [Tonie Box](https://us.tonies.com/pages/toniebox2).

Von (3.5 years old) already loves placing Cars and Toy Story figurines on his Tonie Box to play songs. This project brings that same physical-object-triggers-media experience to his movies. He should just put Buzz Lightyear on the box and Toy Story starts — no screens, no apps, no fuss.

---

## Current status

**✅ Phase 1 done — Apple TV + Plex pipeline working end-to-end.** A single curl from the laptop wakes the TV + soundbar + Apple TV from full sleep, opens Plex, and starts a chosen movie. Tested with The Super Mario Bros. Movie (Plex rating key `190`).

**▶️ Phase 2 in progress — NFC reading on the Pico.** Sub-milestone 1 done: MicroPython v1.28.0 flashed onto the Pico 2 WH, VS Code + MicroPico extension connected over USB serial, `blink.py` runs and toggles the onboard LED. Next: wire the PN532 over I2C and read its firmware version.

> **Tooling note:** switched from Thonny (mentioned in Phase 2 plan below) to **VS Code + MicroPico extension** — same MicroPython workflow, fits the existing editor. Phase 2 instructions still apply, just substitute MicroPico's "Run current file on Pico" for Thonny's run button.

**Deferred from Phase 1** (intentional — will fold into later work):
- Pause webhook — naturally falls out of the Phase 3 `nfc/removed` automation; no need to build it standalone.
- Tailscale remote access — works any time, not blocking anything.

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
- **Home Assistant** (on Raspberry Pi via Docker) + **pyatv** for Apple TV control
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
   description: Cold-start — wake Apple TV, launch Plex, play movie
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

     # 5. Settle — Plex client entity registers in HA before its session is fully usable
     - delay: "00:00:05"

     # 6. Play the movie via the Plex client entity (rating key, not title)
     - target:
         entity_id: media_player.plex_plex_for_apple_tv_apple_tv
       data:
         media_content_id: '190'
         media_content_type: movie
       action: media_player.play_media
   mode: single
   ```

3. Save, sleep the Apple TV, wait 10s, then from your laptop:
   ```bash
   curl -i -X POST http://<pi-lan-ip>:8123/api/webhook/play_super_mario_movie
   ```
4. Watch: TV on → soundbar on → Apple TV wakes → Plex opens → movie plays. Single command from full cold.

**Why this YAML works where the original "launch_app" approach didn't:**
- `media_player.turn_on` (rather than `remote.send_command turn_on`) uses the Companion protocol from Step 2 — same mechanism the physical remote uses; TV and soundbar follow via CEC.
- `media_player.select_source: Plex` is cleaner than `remote.send_command launch_app` for opening Plex from cold — the source list comes from pyatv's discovery and doesn't depend on bundle-ID strings.
- The 5-second settle delay in step 5 is the difference between "Plex is open" and "Plex's playback session is actually ready to receive a command". Without it, `play_media` lands in dead air.

**Cold-start gotcha — Apple ID picker.** If the Apple TV has multiple user accounts, tvOS shows a "Who's watching?" picker before any app gets foreground. Plex launches behind it; `play_media` fires into nothing. **Fix:** Settings → Users and Accounts → switch to a single user (or set a default). Right call for a kid's movie box anyway — Von shouldn't be picking accounts.

**✅ Checkpoint:** Single `curl` plays the movie from a fully asleep Apple TV.

#### Step 7: Pause webhook (deferred — will fold into Phase 3)

This was originally a separate Phase 1 step. Skipping it standalone — when the NFC `removed` automation is built in Phase 3, it'll call `media_player.media_pause` as one of its actions, which is the same thing. No reason to build a parallel test webhook that won't survive into the final design.

If you ever want it for manual testing in the meantime, it's a one-action automation:
```yaml
- target:
    entity_id: media_player.plex_plex_for_apple_tv_apple_tv
  action: media_player.media_pause
```

#### Phase 1 troubleshooting

- **`media_player.turn_on` does nothing from HA:** Companion pairing didn't complete. Settings → Devices & services → Apple TV integration → Reconfigure → step through pairing again. Companion is a *separate* pairing flow from AirPlay; both must complete.
- **Apple TV wakes but TV/soundbar stay off:** HDMI-CEC is off somewhere in the chain. Test the physical Siri Remote first — if that also fails, fix CEC at the device level before touching HA.
- **Apple TV stops at "Who's watching?" picker:** multiple users configured on Apple TV. Settings → Users and Accounts → switch to a single user.
- **Apple TV sleeps too deeply during testing:** Settings → General → Sleep After → set a long interval (or Never) while debugging so sleep depth doesn't confound other failures.
- **Plex client entity missing from HA:** open Plex on the Apple TV once, then reload the Plex integration (Devices & services → Plex → ⋯ → Reload). The entity only registers while Plex is running.
- **Plex opens but `play_media` does nothing:** Plex client entity name may have shifted, or the rating key doesn't exist. Developer Tools → States, search "plex", confirm the entity ID. Verify the rating key by opening the movie's detail page in Plex web — the URL contains the key.
- **First play call sometimes fails, second works:** Plex client reports ready slightly before its playback session is. The 5s settle delay covers most of this; if it's still flaky in the field, wrap step 6 in a `repeat: ... until:` block with up to 3 retries (worth doing in the production Phase 3 automation for reliability under Von's hands).
- **Webhook returns 200 but nothing happens:** Developer Tools → Logbook (or Settings → System → Logs) shows the automation run and which action failed. Usually a misnamed entity.

#### Phase 1 done when

- [x] HA running on the Pi at `http://<pi-lan-ip>:8123`
- [x] Apple TV paired — both AirPlay *and* Companion auth completed
- [x] HDMI-CEC verified: physical remote wakes TV + soundbar + Apple TV
- [x] Plex integration connected, library visible
- [x] Plex-on-AppleTV `media_player` entity exists
- [x] `curl` webhook plays the movie from a fully asleep Apple TV (one command, full cold start)
- [ ] Pause webhook — *deferred to Phase 3 (rolls into `nfc/removed` automation)*
- [ ] Tailscale set up — *optional, no blocker*

#### Phase 1 outcomes — values to reuse in Phase 3

These are the actual entity IDs and config strings that worked in this house. Phase 3 automations should target the same entities; treat this as the source of truth.

| Thing | Value |
|---|---|
| HA URL (LAN) | `http://192.168.0.122:8123` |
| Apple TV `media_player` entity | `media_player.living_room` |
| Plex-on-AppleTV `media_player` entity | `media_player.plex_plex_for_apple_tv_apple_tv` |
| Plex source name (for `select_source`) | `Plex` |
| First proven movie (rating key) | The Super Mario Bros. Movie → `190` |
| Working webhook ID | `play_super_mario_movie` |

#### Lessons learned in Phase 1

Hard-won facts. Each of these cost time; capturing them so they don't have to be re-derived.

1. **Use Plex rating keys, not titles.** `media_content_id: 'Toy Story'` is exact-match against the stored title. Plex stores movies with metadata-fetched titles like `Toy Story (1995)`, and a single character mismatch fails silently — Plex opens, nothing plays. Numeric rating keys are permanent and unambiguous. Find one via the movie detail page URL in Plex web: `...details?key=%2Flibrary%2Fmetadata%2F190` → rating key `190`. Build the Phase 3 NFC mapping as `{uid: rating_key}`, not `{uid: title}`.
2. **Companion auth is separate from AirPlay auth.** When pairing the Apple TV integration, both flows must complete. Without Companion, `media_player.turn_on` does nothing.
3. **`media_player.select_source: Plex` beats `remote.send_command launch_app`.** Cleaner, doesn't depend on bundle IDs, uses the source list pyatv discovered for free.
4. **Plex client reports ready before its session is.** A 5-second delay between launching Plex and calling `play_media` is the difference between reliable and not. For production Phase 3 use, wrap the play action in a 2–3-attempt retry — the first call occasionally still loses the race and the second always succeeds.
5. **The Apple ID picker silently breaks automation.** Multiple users on Apple TV → tvOS shows a "Who's watching?" picker after wake → Plex launches behind it but never gets foreground → `play_media` lands in nothing. Single user account on Apple TV is the fix and is the right setting for a kid's box anyway.
6. **HA on Pi, not Synology.** Synology Container Manager's Docker has known issues extracting modern HA image layers (`failed to register layer ... archive/tar: invalid tar header`). The Pi runs vanilla Docker, updates cleanly. This is now baked into the architecture; not revisiting.

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
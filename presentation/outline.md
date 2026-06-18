# NFC Movie Box — talk outline

**Audience:** dev coworkers (tech-savvy — can move fast).
**Length:** 10–15 minutes, live, with the physical box on the table.
**Format when built:** HTML deck, tab/arrow-key navigation. Planned framework: **reveal.js** (canonical for HTML dev talks, minimal setup — drop in CSS+JS, write `<section>` per slide). If we want lighter-weight, plain HTML + CSS scroll-snap is a fallback.

**Talk thesis (the through-line, not a slide):** *"I thought the hardware would be the hard part. The hardware was easy. Home Assistant orchestration was where I spent the time."*

---

## Section arc

1. **Why** — physical media, curated choices, kid autonomy
2. **How it works** — demo video + architecture + real payloads
3. **Parts & software** — only the decisions that actually had alternatives
4. **Dev process** — de-risking strategy + the plan-vs-reality shift
5. **Breadboard → prototype** — photo evolution
6. **Biggest challenges** — three deep war stories, all HA-flavored
7. **What's next** — v1 enclosure, v2 brings back what got cut, plus a countdown timer

---

## Slide-by-slide

### 1. Title

- **Vonbox**
- Subtitle: *"An NFC-reading movie player"*

### 2. The why

- "My 3.5-year-old can't read or navigate Plex."
- "I was tired of him scrolling through endless choices on Disney+ and YouTube."
- Three goals: **physical media** • **curated choices** • **kid autonomy**
- Smaller line: inspired by the Tonie Box + [simplyexplained.com NFC movie library article](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/)
- *(Optional photo: Von with the Tonie Box, or a still from the demo video.)*

---

### 3. How it works — demo video

- Embedded video (IMG_2619.MOV or IMG_2638.MOV — whichever is the "son taps blu-ray box → movie plays" end-to-end).
- Set the frame in one sentence before hitting play: *"Cold start. Watch what happens after the tap."*
- Let the video carry the explanation.

### 4. How it works — the flow

- **Sequence diagram**, top-to-bottom:

  ```
  Tap (NTAG215 on box)
      │
      ▼
  Pico polls PN532 → debounce → publish vonbox/nfc/tapped
      │
      ▼
  MQTT broker (Mosquitto on Synology)
      │
      ▼
  Home Assistant automation
    • UID → Plex rating key lookup
    • Unscrobble (clear resume)
    • turn_on → wake TV + soundbar via CEC
    • remote home → Apple TV home
    • play_media (Plex deep link)
      │
      ▼
  Apple TV launches Plex → movie plays
      │
      ▼
  HA publishes vonbox/state ← Pico renders feedback (LED + buzzer)
  ```

- Verbal beat: *"Everything past the Pico happens in Home Assistant. The Pico is intentionally dumb."*

### 5. How it works — what flies on the wire

Two concrete artifacts on one slide:

**1. The MQTT payloads:**

```
vonbox/nfc/tapped  →  {"uid": "045AED5ECD2A81"}
vonbox/state       →  {"state": "loading",  "uid": "...", "title": "Mario", "reason": null}
vonbox/state       →  {"state": "playing",  "uid": "...", "title": "Mario", "reason": null}
```

**2. The Plex deep link** HA actually calls (this is the punchline for the tvOS challenge later):

```
plex://play/?metadataKey=/library/metadata/<key>&metadataType=1&server=<machine_id>
```

- Verbal beat: *"Adding a new movie = one line in a YAML map. No reflash, no rebuild."*

---

### 6. Parts & software — Pico, not Pi Zero

- Heading: **"Microcontroller, not a tiny Linux box."**
- Three bullets, each a reason this matters:
  - **~10× battery life** (Pico ~50 mA active vs. Pi Zero ~400 mA) — aligns with "eventually battery-powered"
  - **Instant boot** — milliseconds vs. ~20 s. A toddler won't wait for Linux.
  - **No SD card** — the #1 reliability failure mode in hobby Pi projects, deleted
- Footer: *"Tradeoff: slower dev loop (flash + reboot vs. ssh + run). Worth it."*

### 7. Parts & software — Home Assistant is the brain

- Heading: **"HA owns logic. Pico is a dumb input."**
- Why HA over custom orchestration:
  - Apple TV + Plex integrations already exist (pyatv, Plex API)
  - Webhooks, automations, state — all free
  - Changing a movie mapping = edit YAML, not flash firmware
- Why MQTT over HTTP webhooks:
  - **Bidirectional** — Pico publishes taps, HA publishes state back; LED feedback comes for free
  - Broker handles reconnect; `umqtt.simple` on the Pico is tiny
- *(Tiny topology graphic on the side: `Pico ──MQTT──▶ Mosquitto ◀──MQTT──▶ HA ──▶ Apple TV + Plex`)*

---

### 8. Dev process — Phase 1 had zero hardware

- Heading: **"Prove the riskiest integration first."**
- Phase 1 was *just* `curl → HA webhook → Apple TV wakes → Plex plays Toy Story`. No Pico, no NFC, no soldering.
- *Why:* If the Apple TV + Plex pipeline didn't work, nothing else would have mattered. De-risk before spending on hardware.
- Verbal beat: *"By the time the parts arrived I already knew the integration worked end-to-end."*

### 9. Dev process — plan vs. reality

- Heading: **"The plan was a Tonie clone. What shipped is not."**
- Two-column compare (original-plan.md vs. v1 shipped):

  | Planned (Tonie-style) | Shipped (v1) |
  |---|---|
  | 3D-printed figurines | Blu-ray cases with NFC tags |
  | Continuous presence (place=play, remove=pause) | **Tap-and-go** (tap fires once) |
  | Volume knob + replay button on the box | Siri Remote does it |
  | OLED display | LED ring + buzzer only |
  | 1-hour resume-window timer | Always start fresh (unscrobble) |

- Verbal beat: *"Each cut had a reason — most lived in an ADR. Tap-and-go was the big one — interaction model, not a feature cut."*

---

### 10. Breadboard → prototype (photo evolution)

Four photos, in order, one-line captions. **Photo IDs are placeholders — drop in the right `IMG_*.JPG` from `presentation/media/` when assembling.**

- **Photo A** — *"First light: PN532 on a breadboard, talking I²C to the Pico, printing UIDs to USB serial."*
- **Photo B** — *"Pico on Wi-Fi, publishing taps to MQTT. Now the laptop sees every tap."*
- **Photo C** — *"LED ring + buzzer added. Local feedback before HA even responds."*
- **Photo D** — *"Today's state — full breadboard, transparent-lid box, living-room-deployable."*

*(May need 3 slides instead of 4 if photos are dense. Aim for one photo full-bleed per slide with caption overlay.)*

---

### 11. Challenges — tvOS 26.5 broke `select_source`

- Heading: **"Someone else's OS update broke my automation. Silently."**
- The setup: HA's normal way to open Plex on Apple TV is `media_player.select_source('Plex')`.
- The symptom: tvOS 26.5 broke the Companion app-list. `select_source` returned success and did nothing.
- The diagnosis: a [GitHub issue](https://github.com/home-assistant/core/issues/171666) led me to the answer — the Companion source list went empty.
- The fix: bypass `select_source` entirely. Call `play_media` with a **Plex deep link URL** directly. (Show the URL we saw on slide 5.)
- Recorded in [ADR 0004](../docs/adr/0004-play-plex-via-deep-link-instead-of-select-source.md).
- Verbal beat: *"This is the cost of integration projects. Three vendors in the chain — Apple, Plex, HA — and any of them can break your weekend."*

### 12. Challenges — what I cut, and why

- Heading: **"The things I designed in, then deleted before I built them."**
- Cut list with one-line reasons:
  - **Volume knob (KY-040 rotary encoder)** — Siri Remote already does it. Why duplicate? [ADR 0002]
  - **Play/pause button** — same. [ADR 0002]
  - **OLED display** — non-readers don't read. Output budget belongs to the LED ring + buzzer. [ADR 0003]
  - **Continuous presence (Tonie-style)** — fragile (tag detune, hand-shadows), and the "movie pauses when you put your toy down" UX wasn't actually what I wanted. [ADR 0001]
- Verbal beat: *"Cutting features takes more discipline than adding them. v1 ships smaller. v2 brings most of these back — with a reason."*

### 13. Challenges — Plex doesn't start from the beginning

- Heading: **"'Play Mario' actually meant 'resume Mario at 47 minutes in.'"**
- The bug: tapping the Mario card replayed *from the last resume point*, not from the start. Confusing for a 3-year-old.
- The diagnosis: Plex tracks resume position server-side; `play_media` honors it. No flag to override.
- The fix: a `rest_command` calling Plex's `/:/unscrobble` endpoint **before** `play_media` clears the resume state.
- Verbal beat: *"This one took longer to find than to fix. The fix is ~6 lines of YAML. Finding it was an afternoon."*

### 14. Challenges — and also…

Rapid-fire one-liners (one slide):

- **iPhone hotspot is 5 GHz by default.** Pico CYW43 radio is 2.4 GHz only. Silent never-associates. Fix: "Maximize Compatibility" in iOS settings.
- **`umqtt.simple` is not frozen** into the official Pico 2 W MicroPython build. One-time `mip install` to flash.
- **LED ring all-white at full brightness pulls ~1.4 A** — more than VSYS/USB can supply. Hard-cap brightness at 25% in firmware.
- **PN532 ships in HSU/UART mode** by default. Two DIP switches on the back of the board switch to I²C. Easy to miss.

---

### 15. What's next

- **v1 finish:** design + 3D print a proper enclosure. Currently using a pre-existing transparent-lid box.
- **v2 brings back what v1 cut, with reasons:**
  - **Volume knob** — for when the Siri Remote isn't nearby (kid use case)
  - **Play/pause button** — same
  - **Countdown timer / auto-shutoff** — *new* — TV-time enforcement. Movie ends or limit hits, TV powers off. Parent-coded.
- (Optional: KiCad-designed PCB, custom 3D-printed figurines per movie — "future maybe.")

### 16. Questions?

- Just the word. Optional: a small photo of the box, or a QR code to the GitHub repo if it's public.

---

## Media inventory (`presentation/media/`)

14 photos + 2 videos. Need to map each to a slide. Pending — will do in a follow-up pass with you.

**Videos:**
- `IMG_2619.MOV` (~325 MB) — ?
- `IMG_2638.MOV` (~264 MB) — ?
  - One of these is the "son taps blu-ray case, movie plays" demo for slide 3.
  - The other (if substantive) could be a B-roll moment for slide 5 (wire format) or one of the breadboard slides.

**Photos:** 14 `IMG_*.JPG` files. Candidates by slide:
- Slide 2 (Why) — optional: a "Von with the Tonie Box" or "Von with the demo card" shot.
- Slides 10a–d (breadboard evolution) — 4 photos showing PN532 alone → +Pico/Wi-Fi → +LED+buzzer → today.
- Slide 16 (Questions) — optional: hero shot of the current box.

*Action item: walk through the 14 photos together, label each, and assign to slides.*

---

## Open questions to resolve before building the deck

1. **Photo mapping** — we'll use placeholders in the deck for now and walk through the 14 photos together later.
2. **Visual tone** — clean/minimal dev-talk aesthetic (recommended), or something more playful given it's a kid's toy?
3. **Closing-slide QR code** — decide at the end whether the repo gets shared with coworkers. Worth doing if the repo is in a reasonable state.

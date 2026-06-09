# ADR 0002 — Drop the volume knob and play/pause button for v1

- **Status:** Accepted
- **Date:** 2026-06-08
- **Amends:** [ADR 0001](./0001-tap-and-go-instead-of-continuous-presence.md) — which introduced the physical play/pause button as the box's only pause mechanism

## Context

ADR 0001 settled the *interaction* model (tap-and-go) and, in doing so, added a physical **play/pause button** as the sole way to pause a movie once the removal-pauses semantics were dropped. The earlier design also carried a **rotary encoder** (KY-040) on the box top for volume, sending Apple TV volume commands over MQTT.

As the first physical build approaches, the goal for v1 is to ship the smallest thing that delivers the core magic: **Von taps a tag, the movie plays.** Every additional control is another hole in the enclosure, another wire to solder, another MQTT topic and HA automation to maintain, and another moving part that can fail in a toddler's hands. The two controls that earn the least in v1 are the ones that don't touch the core loop:

- **Volume knob** — volume already works the way it always has: the Siri Remote (and the soundbar) adjust volume through the same Apple TV → HDMI-CEC path. The knob is a convenience, not a requirement.
- **Play/pause button** — pausing is an occasional need, and the Siri Remote already does it. It is not part of "tap a tag, movie plays."

## Decision

For v1, the box hardware is:

- PN532 NFC reader (tap input)
- WS2812 NeoPixel ring — 24 LEDs, DIYMalls (visual status)
- Passive buzzer (audio feedback)
- SSD1306 OLED (movie title / parent-readable errors)

**Dropped from v1:**

- **Rotary encoder (volume knob)** and its `vonbox/volume/up` / `vonbox/volume/down` MQTT topics and HA volume automations.
- **Play/pause button** and its `vonbox/button/play_pause` MQTT topic and HA pause/resume automation. The long-press "reserved for future use" gesture goes with it.

## Consequences

**v1 has no on-box pause.** A movie plays until either a *different* tag is tapped (switches movies) or the Apple TV goes to sleep (ends the session). This is exactly "Alternative 3 — tap-to-start, no pause at all" that ADR 0001 considered and rejected; we are **accepting it for v1** as a deliberate simplification, with the escape hatch that the Siri Remote can always pause in the meantime. ADR 0001's reasoning still holds for the long term — real living-room interruptions exist — so pause is expected to return in a later iteration (a button, or a long-press gesture on a future control).

**v1 has no on-box volume control.** Volume is the Siri Remote / soundbar / CEC path, unchanged. No regression — that path was always the source of truth; the knob would only have duplicated it.

**The Pico stays even dumber.** It publishes one topic (`vonbox/nfc/tapped`) and subscribes to one (`vonbox/state`). No encoder PIO program, no button debouncing.

**Phase 4 shrinks** to LED ring + buzzer + OLED only. The `media_pause` / `media_play` and volume automations planned for Phase 4 are deferred along with the hardware.

**The LED ring can still show a "paused" state** if HA reports the Apple TV as paused (e.g. someone paused with the Siri Remote) — the box simply never *originates* a pause itself.

## Alternatives considered

1. **Keep both controls (the ADR 0001 design).** Rejected for v1 only — more enclosure complexity and firmware surface than the first build should carry. Not rejected forever.
2. **Drop the knob, keep the button.** Rejected because the button is the more complex of the two (debounce + bidirectional pause/resume state + an HA automation that has to reason about current playback state), and the Siri Remote already covers pause. If one control survives into v1.x it will be reconsidered on its own merits.
3. **Drop the OLED too, for maximum minimalism.** Rejected — the OLED costs nothing in the interaction model (it's output-only, shares the existing I2C bus with the PN532, no new GPIO) and earns its keep as both Von-facing magic and a parent-facing debug surface.

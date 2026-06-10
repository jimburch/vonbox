# ADR 0003 — Drop the OLED for v1

- **Status:** Accepted
- **Date:** 2026-06-09
- **Amends:** [ADR 0002](./0002-drop-volume-knob-and-play-pause-button-for-v1.md) — which kept the OLED when the v1 controls were cut, explicitly rejecting "drop the OLED too" (its alternative 3)

## Context

ADR 0002 cut v1 down to tap input plus three output devices, keeping the SSD1306 OLED because it looked nearly free (output-only, shares the PN532's I²C bus, no new GPIO) and promised both Von-facing magic and a parent-facing debug surface.

Two things changed since:

1. **The feedback vocabulary got built without it.** Phase 4 bench work brought up the LED ring and buzzer, and `lib/feedback.py` renders the entire v1 state vocabulary (idle / loading / playing / already_playing / paused / standby / error) on those two devices alone — proven end-to-end against the mock HA in the offline harness. The OLED was never wired; nothing in the working loop misses it.
2. **Production-hardware planning made its real cost visible** (`docs/production-hardware.md`). "No new GPIO" was true but incomplete: in the enclosure the OLED costs a 4-pin JST lead, mounting, and a window in the front face — plus the firmware surface of a display module (fonts, layout, title rendering) that doesn't exist yet.

Meanwhile its two jobs are already covered elsewhere. The movie title appears on the TV itself seconds after a tap — the OLED would announce the thing the much bigger screen is about to show. And parent-readable errors live in HA (system log / logbook) plus the ring's red error animation.

## Decision

The SSD1306 OLED is **cut from v1**. The v1 device list is final: **Pico 2 WH, PN532, 24-px WS2812 ring, KY-006 buzzer** — tap input, light + sound output, nothing else.

## Consequences

**v1 hardware is fully bench-tested.** With the OLED gone, every v1 device is already wired and verified by a `test/bench/` script. Phase 4's remainder is purely software (binding `lib/feedback.py` to the real `vonbox/state` feed, final buzzer cue picks).

**No `display.py` module in v1 firmware.** One less thing for `main.py` to orchestrate.

**The MQTT contract is unchanged.** `title` stays a required key in the canonical `vonbox/state` payload — it costs nothing, the mock HA already sends it, and a future OLED consumes it without a protocol change.

**The enclosure loses its front-face window.** The lid carries the tap zone + ring, the base carries the rest (see `docs/production-hardware.md`). No display window to design, align, or diffuse.

**Re-adding it later stays cheap by design.** It joins the existing I²C bus on GP4/GP5 (different address than the PN532 — no conflict, no new pins); the cost is a 4-pin JST lead and an enclosure window. Listed under Phase 6+ iteration in `spec.md`.

## Alternatives considered

1. **Keep the OLED (ADR 0002's position).** Rejected for v1: both of its jobs are already served better elsewhere (the TV shows the title; HA shows the errors), it is the only v1 device not yet wired or bench-tested, and it is the only one demanding a designed feature on the enclosure's most visible face. ADR 0002's "costs nothing in the interaction model" remains true — which is exactly why cutting it costs nothing in the interaction model either.
2. **Wire it now, add the enclosure window in a later revision.** Rejected — pays the wiring and firmware cost up front for zero user-facing payoff, and carries an unexercised device into the build, against the bench-test-before-integrating rule.

# ADR 0001 — Tap-and-go interaction model, not continuous presence

- **Status:** Accepted (amended in part by [ADR 0002](./0002-drop-volume-knob-and-play-pause-button-for-v1.md))
- **Date:** 2026-05-15
- **Supersedes:** the original Tonie-Box-style interaction sketched in early SPEC.md drafts

> **Amendment (2026-06-08):** [ADR 0002](./0002-drop-volume-knob-and-play-pause-button-for-v1.md) drops the physical **play/pause button** (and the rotary volume knob) from **v1**. The tap-and-go interaction model below is unchanged, but for the first build there is no on-box pause — a movie plays until a different tag is tapped or the Apple TV sleeps (i.e. "Alternative 3" below is accepted for v1). Pause is expected to return in a later iteration.

## Context

The original design (April 2026) modeled this box on the Tonie Box: a figurine, magnetically mated to the top of the box, would be held there by Von while the movie played. The PN532 NFC reader would poll continuously at 10 Hz; *placement* of the figurine started the movie, *removal* paused it. A 1-hour "resume window" was maintained by Home Assistant: if Von put the figurine back within an hour, Plex would resume; if not, HA would clear the resume position so the next placement started fresh.

That design carried several pieces of implied hardware and firmware complexity:

- **Magnets** in both the figurines and the box top to physically mate them.
- **Ferrite shielding stickers** in each figurine to prevent the magnets from detuning the NFC antenna.
- **Continuous polling semantics** in the firmware — track `PLACED` *and* `REMOVED` edge events, debounce both, handle flickery reads where the tag momentarily drops out without Von actually lifting it.
- **A 1-hour resume timer** in HA, with bookkeeping per UID, including a Plex API call to clear resume position on timeout.
- **A "removed" automation** in HA that pauses Plex.
- **Custom 3D-printed figurine geometry** with a centered NFC recess, a ferrite pocket, and a ring of magnet pockets offset to avoid RF detuning.

## Decision

Switch to a **tap-and-go** interaction model, closely matching the [Simply Explained "NFC Movie Library for My Kids"](https://simplyexplained.com/blog/how-i-built-an-nfc-movie-library-for-my-kids/) blog post:

- A tag is briefly tapped against the box. The Pico's PN532 reads the UID and fires a *single* event.
- The tag goes away. The movie continues regardless.
- Re-tapping the same tag while its movie is playing or paused is a local no-op (soft "already playing" chime + LED pulse), not a new event.
- Tapping a *different* tag switches movies immediately.
- A physical play/pause button on the box is the *only* mechanism for pausing during playback.
- A session ends when the Apple TV goes to sleep. After that, the next tap of any tag — including the previous one — is a fresh start, and Plex's own native resume position (independent of HA) handles "pick up where I left off" within Plex's own window.

## Consequences

**Removed from the project:**

- Neodymium magnets and ferrite shielding stickers — no longer in the BOM.
- Figurine/box mating geometry — the top of the box just needs a marked tap zone, not a recess.
- The "removed" event and its HA automation.
- The 1-hour HA-managed resume timer and the Plex resume-clear API call.
- Continuous-presence firmware semantics (debouncing flickery presence reads, etc.).

**Added or strengthened:**

- A local "session active per UID" piece of state on the Pico, driven by `moviebox/state` MQTT updates from HA. This is what lets the Pico distinguish "new tag → switch" from "same tag → no-op."
- A physical play/pause button on the box.

**Trade-offs accepted:**

- *Less Tonie-magical.* Tonie's continuous-presence model is part of why kids find it satisfying — the object *is* the playback. The tap-and-go model is a little more transactional. We are betting that "tap a card, movie plays, walk away" is at least as good for Von as "carry a figurine around with you and put it back to resume," and probably better for the actual living-room use case (which is "start the movie and watch it").
- *Restart-from-beginning is no longer a first-class affordance.* In the old model, the replay button restarted the movie. In the new model, the play/pause button is a pure toggle and there is no in-session restart. Restart only happens implicitly by ending the session (letting the Apple TV sleep) and tapping again, and even then Plex's native resume position will usually bias toward picking up mid-movie. If true "start over" turns out to matter, it becomes a Phase 6+ feature (long-press of the button, or a new dedicated gesture).
- *The box now has a moving part (button) that can fail.* The original design only had the rotary encoder (also a moving part, but with no hard-coded semantic load — you can lose volume and the box still works). The button is functionally load-bearing for pause.

## Alternatives considered

1. **Keep the Tonie-style continuous-presence model.** Rejected because the magnets/ferrite complexity and the removal-pauses semantics turned out to be more enclosure-design pain than they were worth, and the use case ("Von wants to watch a movie") doesn't really benefit from "the object lives on the box for the whole movie." Movies are 90 minutes; Tonie's "the figurine is the playback" model works better for the 3-minute songs it was designed for.
2. **Hybrid: tap-to-start, but a long-hold pauses.** Rejected as too clever for a 3.5-year-old to discover and too easy to trigger accidentally if he leaves a tag near the reader.
3. **Tap-to-start, no pause at all** (movie always plays to completion). Rejected because real-world living-room interruptions exist (dinner, bedtime, doorbell) and Von needs a way to stop the movie without learning the Siri Remote.

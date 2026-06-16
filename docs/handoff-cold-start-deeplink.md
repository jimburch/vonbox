# Handoff — cold-start playback fixed (Plex deep link); state-watcher is next

- **Date:** 2026-06-15
- **Status of the box:** a tap plays the mapped movie from cold sleep, end to end.
  The last fix (start-from-the-beginning) was just re-wired and is being
  confirmed with one live tap as this is written.

## TL;DR

tvOS 26.5 silently broke the Apple TV Companion app-list, which killed
`select_source: Plex` and with it the whole previously-working cold-start path.
It is **fixed**: the HA automation now plays via a **Plex deep link** and clears
the resume point with a Plex `/:/unscrobble` `rest_command`.

**Read these first — the full story is already written down, don't re-derive it:**

- `docs/adr/0004-play-plex-via-deep-link-instead-of-select-source.md` — the
  decision, the tvOS 26.5 root cause, and every ruled-out alternative (re-pair,
  patient-retry, `media_seek`, URL `viewOffset`, `/:/progress`).
- `spec.md` Phase 3 **lessons #13–#17** — the specifics (the regression, the
  deep-link play, the wake→home→deep-link order, server-side unscrobble, the
  "`rest_command` must be defined or the automation aborts" trap).
- `CLAUDE.md` → "Phase 1 reference values" — canonical entity IDs, the deep-link
  format, the Plex machine ID, and where the token lives.
- `test/home-assistant/vonbox_play_movie.yaml` — the live automation.
- `test/home-assistant/configuration.yaml` — reference copy of the Pi's config
  (the `rest_command`; token redacted to `MY_TOKEN_HERE`).

This doc only carries the **live state** not in those artifacts.

## What's true right now

- **Cold tap → movie works:** `turn_on` (wakes TV+soundbar via CEC) → `remote
  send_command: home` → deep-link `play_media` (url) on `media_player.living_room`.
  Verified from full cold sleep with Mario (`045AED5ECD2A81` → rating key `190`).
- **Guards work:** unknown UID → `error`/`unknown_tag`; re-tap of the
  already-playing movie → `already_playing` no-op (never restarts). The box's
  `already_playing` cue (single soft mid-note + pulse) is in `lib/feedback.py` and
  fired live.
- **Start-from-the-beginning** is done at the mechanism level: the
  `rest_command.plex_mark_unwatched` (Plex `/:/unscrobble`) is **verified loaded
  and working standalone** — a manual unscrobble URL + tap started Mario at 0:00,
  and a Developer Tools → Actions test-call cleared the resume point.

## The one open verification (in progress)

The `rest_command` call was just wired **into** the automation
(`vonbox_play_movie.yaml`, before the wake step, with `continue_on_error: true`).
Only the standalone `rest_command` has been confirmed — the **re-wired automation
end-to-end** has not yet had a live tap. The user is running it now:

> deploy the file → Reload Automations → give Mario a resume point → tap → confirm
> it starts at **0:00** and nothing breaks.

If it passes, start-from-the-beginning is fully done. If a tap does nothing,
first suspect the `rest_command` isn't loaded (Developer Tools → Actions →
`plex_mark_unwatched`); a missing action aborts the automation *before* `turn_on`
and is **not** caught by `continue_on_error` (spec.md lesson #17).

## Open items, priority order

1. **Confirm the re-wire** (the tap above).
2. **Build the paused/standby state-watcher automation** — the main remaining
   Phase 3 work. A separate HA automation that watches `media_player.living_room`
   and publishes the tagged `vonbox/state` for `paused` (Siri-Remote pause) and
   `standby` (Apple TV asleep / session end). The play automation only covers the
   tap→play branch. The Pico already renders both states (`lib/feedback.py`,
   proven in the offline harness) — only the real-HA publisher is missing. Payload
   shape: CLAUDE.md / spec.md "`vonbox/state` payload (canonical)".
3. **Verify Guard 2's `media_content_id` format** on a live re-tap — bare `190` vs
   `/library/metadata/190`. The guard tolerates both via `split('/') | last`;
   confirm and tighten if you can.
4. **Phase 4/5 remainder:** final buzzer cue picks (`CHIME_*` constants atop
   `lib/feedback.py`), `main.py` orchestration (today everything runs as ephemeral
   scripts; `test/offline-harness/full_loop_test.py` is the de-facto orchestrator),
   and the enclosure (`docs/production-hardware.md`).

## Deploy workflow (file-based — do not use the HA UI editor)

The automation lives **only** as a file; the HA visual editor rewrites
`play_media` into a broken `media: {…}` wrapper (passes the rating key as an int).

- Repo source: `test/home-assistant/vonbox_play_movie.yaml` ↔ Pi
  `/config/automations_vonbox/vonbox_play_movie.yaml`.
- Deploy: edit the repo file → on the Mac `pbcopy < test/home-assistant/vonbox_play_movie.yaml`
  → on the Pi (in `~/docker/homeassistant`) `cat > automations_vonbox/vonbox_play_movie.yaml`,
  paste, **Ctrl-D** → Developer Tools → YAML → **Reload Automations**.
- `configuration.yaml` edits (e.g. the `rest_command`) need a **full HA restart**,
  not just a reload. Deploy them the same `cat >` way (avoids nano auto-indent,
  which silently breaks YAML — spec.md lesson #17).
- HA: `http://192.168.0.122:8123`, Docker on the Pi, SSH `jim@raspberrypi`, config
  dir `~/docker/homeassistant`. Traces: Settings → Automations → "Play movie from
  NFC tap" → ⋮ → Traces (works even though it's file-based/read-only).

## Environment facts worth keeping in mind

- **tvOS 26.5, pyatv 0.17.0, HA 2026.4.4, Python 3.14** (bleeding edge). The
  Companion app-list bug ([home-assistant/core#171666](https://github.com/home-assistant/core/issues/171666),
  [#168210](https://github.com/home-assistant/core/issues/168210)) is **open and
  unfixed**. If a future HA/pyatv update fixes it, `select_source` could be revived
  (it would give a faster cold start than the deep link's wake→home→launch), but
  the deep-link path is solid and doesn't depend on it.
- Plex server (WOPR) on Synology `192.168.0.123:32400`; machine ID
  `e665330f66bf4ac955231fdb44f95287341d2864` (constant; from `/identity`).
  X-Plex-Token lives in `configuration.yaml` on the Pi — full-access credential,
  never commit it.
- `media_player.plex_plex_for_apple_tv_apple_tv` is still used as the playing /
  already-playing signal, but is **not** used to *initiate* play anymore (it only
  registers once a movie is actively playing — lesson #14). Its entity ID is not
  guaranteed stable across Plex app updates (Phase 1 lesson #10).

## Suggested skills for the next session

None required. The remaining work is HA automation (the state-watcher) plus
MicroPython (`main.py`, final buzzer cues). Use the `handoff` skill again at the
end if context fills up.

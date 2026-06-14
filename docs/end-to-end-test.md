# End-to-end test — tap a tag, the movie plays (the real thing)

- **Status:** Living runbook
- **Date:** 2026-06-10
- **Applies to:** the full production path at home — real Pico, real Mosquitto
  on the Synology, real Home Assistant driving the real Apple TV + Plex. Phase 3
  step 6 / Phase 4 sign-off.

> This is the at-home companion to `docs/testing-away-from-home.md`. That doc
> fakes the back end (`mock_ha.py`) so you can exercise the box on a kitchen
> table; **this** doc wires the box to the genuine stack and proves that tapping
> a tag actually starts a movie on the living-room TV under every starting
> condition — cold, warm, and already-playing.

## What this proves

The whole loop, nothing mocked:

```
NTAG215 tap
   │
   ▼
Pico 2 WH ──vonbox/nfc/tapped──▶ Mosquitto (Synology) ──▶ Home Assistant (Pi)
   ▲                                    │                       │ media_player.turn_on
   │                                    │                       │ select_source: Plex
   └──────── vonbox/state ◀─────────────┘                       │ play_media: rating key
   (LED ring + buzzer follow the real Apple TV state)           ▼
                                                        TV + soundbar + Apple TV + Plex
```

When it passes: Von taps Mario, the box chimes and sparkles, the TV and soundbar
wake, Plex opens, the movie starts, and the ring settles to solid green with the
"movie starting" triad — all from one tap, from cold sleep. And tapping Mario
again while it's already on does **nothing** but a soft "yeah, I know" pulse — it
never restarts the movie.

## Prerequisites (one-time, verify before each session)

This test only exercises code; everything below must already be true. If any
box is unchecked, fix it in its own bench/Phase test first — don't debug it
through the full loop.

**On the Pico's flash** (write with MicroPico "Upload project to Pico" or
`mpremote cp`; "Run current file" alone does *not* persist these):

- [ ] `lib/pn532.py` and `lib/feedback.py` uploaded.
- [ ] `umqtt.simple` installed under `/lib` (run `test/bench/install_umqtt.py` if missing).
- [ ] `secrets.py` present with **home** values (table below).

**Home Assistant** (`http://192.168.0.122:8123`):

- [ ] MQTT integration configured and **connected to the Synology broker**
      (`192.168.0.123:1883`, user `vonbox`). Settings → Devices & services → MQTT
      should say "connected."
- [ ] `test/home-assistant/play_from_tap.yaml` loaded as an automation and
      enabled. (Settings → Automations, or include the YAML and reload
      automations.) This is the brain — it owns the UID→rating-key map, the
      already-playing guard, and every `vonbox/state` publish.
- [ ] The Apple TV + Plex Phase 1 path works on its own — the
      `play_mario.yaml` / Step-6 webhook plays Mario from cold sleep. If the
      bare play sequence is flaky, the tap loop will be too; that's a Phase 1
      problem, not this test's.
- [ ] Entity IDs still match: `media_player.living_room` (Apple TV) and
      `media_player.plex_plex_for_apple_tv_apple_tv` (Plex on Apple TV). The Plex
      one is **not** guaranteed stable across Plex app updates — see Phase 1
      lesson #10. Confirm in Developer Tools → States.

**Broker** (Synology): Mosquitto container up, user `vonbox` exists.

**Tag:** the production NTAG215 `045AED5ECD2A81` (inside the Mario Blu-ray box) → Plex rating key `190` (The Super
Mario Bros. Movie), already in `play_from_tap.yaml`'s map.

## `secrets.py` — home values

Mirror image of the away-from-home table. If you've been testing on a hotspot,
swap these **back** before running this test.

| Key | Home value |
|---|---|
| `WIFI_SSID` | `Jabby` |
| `WIFI_PASSWORD` | (home Wi-Fi password) |
| `MQTT_HOST` | `192.168.0.123` (Synology) |
| `MQTT_PORT` | `1883` |
| `MQTT_USER` | `vonbox` |
| `MQTT_PASSWORD` | (the broker's `vonbox` password) |

> Unlike the dev broker, the **production** broker authenticates. The credentials
> the Pico sends in `secrets.py` must match what `mosquitto_passwd` set, and the
> `mosquitto_pub`/`sub` commands below need `-u vonbox -P …` too.

## Run order

The Pico firmware is the **same** `full_loop_test.py` used away from home — it
doesn't know or care that there's a real HA behind the broker. With home
`secrets.py` on flash, just run it.

From a Mac on the home LAN, watch the bus first (substitute the real password —
or `export VONBOX_PW=…` once and reuse it):

```bash
# Watch BOTH directions of the conversation: taps going up, state coming back.
mosquitto_sub -h 192.168.0.123 -u vonbox -P "$VONBOX_PW" -t 'vonbox/#' -v
```

Then in VS Code: MicroPico **"Run current file on Pico"** on
`test/offline-harness/full_loop_test.py`. On the serial console you should see,
in order:

1. `Wi-Fi ok, ip= 192.168.0.80` (or similar)
2. `MQTT connected, subscribed to vonbox/state`
3. `PN532 ready`
4. the **boot flourish** — rising-fifth chime + a warm-white comet lap around the ring
5. `ready. tap a tag.` and the ring settles to the soft idle breathe

The box is now live on the real broker. (HA's MQTT integration may also publish a
retained `vonbox/state` of `idle`/`playing` that the Pico renders the instant it
subscribes — that's expected and is how a mid-movie reboot recovers the right
ring color.)

## The happy path — one tap, full cold start

Put the TV, soundbar, and Apple TV fully **asleep**. Tap the Mario NTAG215 to
the reader and watch all three places at once (the box, the bus watcher, the TV):

| # | On the box | On `vonbox/#` | On the TV |
|---|---|---|---|
| 1 | green **sparkle** + rising two-note **tap chime** (instant, local — before any network) | `-> vonbox/nfc/tapped {"uid":"045AED5ECD2A81"}` | — |
| 2 | ring → blue **loading** chase (if HA takes >0.4s to answer) | `<- vonbox/state {"state":"loading",…}` | TV + soundbar wake, Apple TV wakes |
| 3 | still loading | — | Plex opens, Mario begins to play |
| 4 | "movie starting" **triad** + ring → **solid green** | `<- vonbox/state {"state":"playing",…}` *(retained)* | Mario playing |

That's the entire contract working in one shot. The `playing` message is
retained, so a box that reboots mid-movie comes straight back to green.

## Scenario matrix — battle-test every entry condition

You don't have to physically re-tap to exercise each branch: a `mosquitto_pub` of
a tap event hits `play_from_tap.yaml` exactly like a real tap does. Use real taps
to prove the PN532 path, and `mosquitto_pub` to drive the branches quickly and
repeatably.

```bash
# Fire a tap for the known Mario tag:
mosquitto_pub -h 192.168.0.123 -u vonbox -P "$VONBOX_PW" \
  -t vonbox/nfc/tapped -m '{"uid":"045AED5ECD2A81"}'
```

| # | Set up this state first | Then tap (or pub) | Expect on `vonbox/state` | Expect on the TV | Box feedback |
|---|---|---|---|---|---|
| 1 | TV / soundbar / Apple TV **all asleep** | Mario tag | `loading` → `playing` | wakes all, opens Plex, Mario plays | sparkle+chime → green + triad |
| 2 | Apple TV **on**, at Plex/tvOS home or a *different* movie | Mario tag | `loading` → `playing` | switches to Mario | sparkle+chime → green + triad |
| 3 | **Mario already playing** | Mario tag | single `already_playing` (no `loading`) | keeps playing — **no restart** | soft amber/green pulse + single mid-note |
| 4 | **Mario paused** (Siri Remote) | Mario tag | single `already_playing` | stays paused | soft pulse + single mid-note |
| 5 | any | bogus UID `{"uid":"04DEADBEEF0000"}` | immediate `error` / `unknown_tag` (no `loading`) | nothing happens | 3 red flashes + descending wah-wah |

**The one that bit us before:** scenario 3. Without the already-playing guard in
`play_from_tap.yaml`, a re-tap re-issued `play_media` and Plex **restarted the
movie from the beginning** (Phase 1 lesson #9). The guard reads the live Plex
entity and bails *before* touching anything — so the only correct outcome for a
re-tap is the soft `already_playing` cue and the movie carrying on untouched.

**Before trusting scenarios 3 & 4,** open Developer Tools → States while Mario
plays and confirm `media_player.plex_plex_for_apple_tv_apple_tv` reports
`media_content_id: 190`. The guard's match is `media_content_id | string == '190'`
*and* `state in (playing, paused)` — the same comparison the retry loop already
relies on, but it's the single assumption the guard rides on, so eyeball it once.

## Driving / observing `vonbox/state` directly

To test the **box's** reaction to a state independent of HA (e.g. force a
`standby` or `paused` the automation won't naturally produce yet), publish a
tagged-form payload by hand. All four keys must be present:

```bash
mosquitto_pub -h 192.168.0.123 -u vonbox -P "$VONBOX_PW" -t vonbox/state \
  -m '{"state":"paused","uid":"045AED5ECD2A81","title":"The Super Mario Bros. Movie","reason":null}'
```

Swap `"state"` for any of `idle`, `loading`, `playing`, `already_playing`,
`paused`, `standby`, `error`. Retain sustained states (`-r`) if you want a
late-joining box to pick them up; leave transients un-retained.

> Pausing/standby aren't published by `play_from_tap.yaml` — that automation only
> covers the tap → play path. The separate state-watcher automation (watch the
> Apple TV entity, republish `paused`/`standby` on external changes) is the next
> step after this matrix passes; until then, use the manual publish above to
> exercise those two ring states.

## Buzzer + LED reference (what each milestone looks and sounds like)

These live in `lib/feedback.py` and are the picks to confirm by ear/eye during
this test. The four "milestone" cues ladder low→high so good climbs and bad
falls:

| Moment | Trigger | Buzzer | LED ring |
|---|---|---|---|
| **Boot** | Pico starts (`fb.boot()`) | calm rising fifth (A4→E5) | warm-white comet lap, then idle breathe |
| **Tap accepted** | local, the instant a tag reads (`fb.tap_accepted()`) | quick bright two-note (B5→E6) | green sparkle, settles |
| **Playing confirmed** | `vonbox/state` → `playing` (genuine entry) | bright rising triad (C6-E6-G6) | solid green fill |
| **Error** | `vonbox/state` → `error` | low descending wah-wah (A3→F3) | 3 red flashes, reverts to prior state |
| idle / loading / paused / standby / already_playing | sustained/transient states | (none / single mid-note for already_playing) | breathe / blue chase / amber breathe / slow breathe / soft pulse |

To audition just the cues with no network or tag, run
`test/offline-harness/state_render_test.py` (Layer 1) — it now leads with the
boot flourish and fires the playing triad on the loading→playing step.

If a cue isn't right, swap it at the named constants atop `feedback.py`
(`CHIME_BOOT`, `CHIME_TAP`, `CHIME_PLAYING`, `TONE_ERROR_DESCENDING`) and re-run
Layer 1 — they're isolated there precisely so the picks are one-line changes.
(The big celebratory `success_level_up` jingle from `buzzer_test.py` is available
if you want a longer "movie starting!" — it runs ~660ms, over the renderer's
300ms cue budget, so it'd block the loop a touch longer; fine for the playing
transition since nothing time-critical is happening then. Say the word and I'll
wire it.)

## Troubleshooting (real-stack specific)

- **Tap publishes but nothing happens on the TV.** Check the automation actually
  triggered: HA → Settings → Automations → "Play movie from NFC tap" → traces. If
  it didn't fire, the MQTT integration isn't subscribed to the broker (or is
  pointed at the wrong one). If it fired but Plex sat at the home screen, that's
  the stale Companion session — the warm-up poke is already in the YAML; see
  Phase 1 lesson #6.
- **Movie plays, then jumps back to the start a few seconds later.** Duplicate
  `play_media` from the retry loop firing before state propagated (lesson #9).
  The YAML's event-driven retry is the fix; if you see this, the
  `wait_template`/`continue_on_timeout` shape was probably altered.
- **A re-tap restarts Mario instead of being ignored.** The already-playing guard
  isn't matching — verify `media_content_id` really is `190` while playing (see
  the note under the matrix). If Plex reports a path instead of a bare key, the
  `| string == '190'` comparison needs adjusting.
- **`mosquitto_sub`/`pub` shows `Bad file descriptor`.** Mosquitto 2.x silently
  drops *unauthenticated* TCP — you forgot `-u vonbox -P …` (Phase 3 lesson #4).
  Real broker-down looks like `Connection refused` instead.
- **Pico won't associate / connect.** This is the home LAN, not a hotspot — the
  2.4 GHz gotcha doesn't apply, but double-check `secrets.py` was actually written
  to flash and points at the **Synology** (`192.168.0.123`), not a leftover
  laptop IP from away-from-home testing.
- **Ring/buzzer wrong but the bus looks correct.** Drop to Layer 1
  (`state_render_test.py`) to isolate the renderer from the network, exactly as
  in the away-from-home runbook.

## See also

- `test/home-assistant/play_from_tap.yaml` — the automation under test.
- `test/offline-harness/full_loop_test.py` — the Pico firmware (same one used here and away).
- `lib/feedback.py` — the LED + buzzer renderer; cue constants at the top.
- `docs/testing-away-from-home.md` — the mocked-back-end version of this loop.
- `SPEC.md` Phase 1 "Lessons learned" (#6, #9, #10) — the reliability fixes baked into the YAML.

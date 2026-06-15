# ADR 0004 — Play Plex via a deep link, not `select_source` (tvOS 26.5 Companion break)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Supersedes:** the `select_source: Plex` + Plex-client `play_media` step at the
  heart of the Phase 1 cold-start sequence (`spec.md` Phase 1 Step 6,
  `test/home-assistant/play_mario.yaml`) and the Phase 3 tap automation.

## Context

The whole playback path — Phase 1 webhook and the Phase 3 NFC automation — relied
on `media_player.select_source: Plex` to foreground the Plex app on the Apple TV.
Once Plex was foregrounded, the Plex client registered with the Plex Media Server,
and `media_player.play_media` (rating key) on the **Plex client** entity started
the movie. This worked end-to-end from cold sleep (it's the documented Phase 1
success).

Then the Apple TV updated to **tvOS 26.5**, and the HA Apple TV integration's
**Companion protocol broke**: `FetchLaunchableApplicationsEvent` (the app list)
and `FetchAttentionState` (power state) now time out. This is a known, **open,
unfixed upstream bug** — see [home-assistant/core#171666](https://github.com/home-assistant/core/issues/171666)
and [#168210](https://github.com/home-assistant/core/issues/168210). It affects
pyatv 0.17.0 / HA 2026.4.4 *and newer* (a reporter on 2026.5.3 still has it).

The break is narrow but fatal to the old path:

- `select_source` reads from the (now empty) app list, so it **silently no-ops**.
- On a cold tap the Apple TV wakes to the home screen; nothing foregrounds Plex.
- The Plex client only registers with the server while a movie is **actively
  playing** — opening Plex idle does **not** register it (confirmed by hand). So
  `play_media` on the Plex client has no target, and cold playback fails entirely.

This was diagnosed over a long session: a clean Apple-TV integration re-pair did
**not** fix Companion (rules out stale credentials); `media_player.turn_on` and
`remote.send_command` still work (Companion HID and power are unaffected — only
app-list and attention-state broke).

## Decision

Launch Plex **and** start the specific movie in **one** call, via Plex's
deep-link URL scheme through `media_player.play_media` on the **Apple TV** entity
(`media_player.living_room`):

```yaml
action: media_player.play_media
target: { entity_id: media_player.living_room }
data:
  media_content_type: url
  media_content_id: "plex://play/?metadataKey=/library/metadata/<RATING_KEY>&metadataType=1&server=<MACHINE_ID>"
```

This routes through pyatv's `launch_app` — a **different** Companion command that
tvOS 26.5 did **not** break — and needs **no** Plex client registration at all.

Supporting decisions that fall out of it:

- **Wake first, then `home`, then the deep link.** The deep link only fires from
  an *awake, foregrounded* Apple TV; it can't wake a sleeping box and is a no-op
  from idle/screensaver. So the automation runs `media_player.turn_on` (which
  wakes the TV + soundbar over CEC) → `remote.send_command: home` (Companion HID,
  still works) → the deep link.
- **Start-from-the-beginning is a server-side reset, not a URL param.** tvOS Plex
  ignores `viewOffset` in the deep link and resumes from the server's stored
  progress. Clear that progress first with a `rest_command` calling Plex
  `/:/unscrobble` (mark unwatched, which clears `viewOffset`).
- **Success is still read from the Plex client entity.** Once a movie is actually
  playing, `media_player.plex_plex_for_apple_tv_apple_tv` registers and reports
  `playing` — the automation waits on that to publish `vonbox/state: playing`, and
  the already-playing guard reads the same entity.

## Consequences

- **Cold playback works again,** with no dependency on the broken Companion
  app-list, the Plex source list, or Plex client registration to *initiate* play.
- **One-time tvOS permission prompt.** The first deep-link launch shows an "Open
  Plex?" dialog requiring the Siri Remote once; granting it is permanent (until an
  Apple TV factory reset / re-pair, where it must be re-granted once).
- **Two new external constants live on the Pi, not the repo:** the Plex server
  **machine identifier** (`server=…`, constant, from
  `curl http://<plex>:32400/identity`) and an **X-Plex-Token** (for the unscrobble
  `rest_command`), both in `configuration.yaml` on the HA Pi. The token is a
  full-access Plex credential — keep it out of git.
- **Start-from-beginning marks the movie unwatched** on every fresh play (a side
  effect of `/:/unscrobble`). Acceptable — even desirable — for a kid's
  repeat-watch box; noted so the reset watched-state isn't a surprise.
- **The `rest_command` must be defined or the automation aborts.** A missing
  `rest_command` raises an unknown-action error that `continue_on_error` does
  **not** swallow (it's a config error, not a runtime one). Verify
  `rest_command.plex_mark_unwatched` appears in Developer Tools → Actions before
  the automation depends on it.
- **The Phase 1 webhook and the `select_source` instructions are superseded** for
  tvOS 26.5+. `test/home-assistant/play_mario.yaml` and the `select_source` steps
  in `spec.md` / `docs/end-to-end-test.md` are left as historical reference with
  pointers here.

## Alternatives considered

1. **Fix / restore Companion (re-pair, update HA/pyatv).** Rejected: it's an open
   upstream bug with no fixed version; a clean re-pair didn't help; tvOS can't be
   downgraded on the family's Apple TV.
2. **Patient retry of `play_media` on the Plex client.** Rejected: on a cold tap
   there is no registered client to retry against — an idle Plex never registers,
   only an active session does. Retrying into `unavailable` can never land.
3. **`media_player.media_seek` to 0 after playback (no token/config).** Tried and
   rejected: this Plex-for-Apple-TV client doesn't accept seek (its
   `supported_features` advertises only browse + play_media), so the seek is a
   no-op and the movie keeps resuming.
4. **Deep-link `viewOffset=0` / Plex `/:/progress?time=0`.** Rejected: tvOS Plex
   ignores the URL `viewOffset`; `/:/progress` enforces a 60-second minimum, so
   `time=0` is silently dropped. Only `/:/unscrobble` reliably clears the resume
   point.
5. **`remote.send_command` UI navigation to open Plex.** Rejected as fragile
   (depends on the app's icon position) and unnecessary once the deep link worked.

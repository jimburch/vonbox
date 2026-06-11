# Going to production — deployment strategy

**Status:** planning only. Nothing here is built yet. This is the roadmap for the
moment we leave development mode (Pico tethered to the laptop, scripts run
ephemerally via MicroPico) and seal the box up as an appliance that lives by the
TV, plugged into the wall.

This doc is the *what* and the *why*. The actual `main.py`, watchdog wiring, and
boot-guard get written when we execute it — not before. Read `CLAUDE.md` for the
always-on context and `spec.md` for the full project history.

---

## 1. What "production" means here

The success criterion, in the dad's words: **plug the box into the wall by the
TV, and Von can tap a tag to start a movie — no laptop, no REPL, no babysitting.**

Concretely, the box in production must:

- **Boot unattended.** Power-on → connect Wi-Fi → connect MQTT → show "ready" on
  the ring, with zero human interaction.
- **Survive the house.** Router reboots, the Synology broker restarting, a Wi-Fi
  blip, a transient code hang — none of these should require a human to walk over
  and pull the plug. It recovers on its own.
- **Fail visibly, not silently.** With no screen and no serial console attached,
  the LED ring + buzzer are the *only* console. Every failure mode the kid or dad
  could hit needs a distinguishable light/sound.
- **Stay easy to take back into dev.** Updating code = bring the box to the
  laptop, drop to the REPL, re-upload. That path must stay frictionless (see §6).

Out of scope for v1 production: OTA updates, battery operation, a real-time clock,
remote logging/telemetry. All noted in §9 as future work.

---

## 2. Dev vs. production: the boot-guard model

### The core fact

On a Pico, **`main.py` auto-runs on boot regardless of power source.** Wall power
and laptop USB boot identically. So "wall = prod, USB = dev" is *not* something
the hardware gives us — we have to build the distinction.

### Decision: interruptible startup guard (not USB auto-detect)

We considered auto-detecting the host (sense USB VBUS, or look for a serial
connection) and branching. **Rejected**, for two reasons specific to this board:

1. On the Pico **2 W**, VBUS sense is not a plain GPIO — it's routed through the
   CYW43 wireless chip, so reading it is awkward and fragile.
2. The signal is *ambiguous*. The production box will very likely be powered by a
   **USB wall charger** (see §7). "USB power present" would then falsely read as
   "dev mode." There's no clean electrical signal that distinguishes "my laptop"
   from "a wall wart."

Instead: **`main.py` always boots toward production, but opens a short, quiet
window at the very start where a connected MicroPico session can interrupt it and
drop to the REPL.** Dev mode only ever happens when a human is sitting at the
laptop — and that human can just hit "Stop execution." No sensing, no ambiguity,
zero friction on the wall path (the window elapses in a second or two and the box
runs).

### Boot sequence (the critical ordering)

```
power on
  │
  ├─ 1. import, construct Feedback, light a dim "booting" color on the ring
  │
  ├─ 2. QUIET INTERRUPTIBLE WINDOW  (~2-3 s)
  │       - watchdog is NOT armed yet
  │       - a short sleep loop that a KeyboardInterrupt (MicroPico "Stop")
  │         breaks cleanly out of → falls through to the REPL = DEV MODE
  │       - if the window elapses untouched → continue to production
  │
  ├─ 3. ARM THE WATCHDOG  (only now — see the gotcha below)
  │
  ├─ 4. connect Wi-Fi  (retry loop, watchdog fed each attempt)
  ├─ 5. connect MQTT + subscribe  (retry loop, watchdog fed)
  ├─ 6. fb.boot() flourish, fb.set_state("idle"), "ready"
  │
  └─ 7. main loop  (the full_loop_test.py loop, hardened — see §3)
```

> **⚠️ Watchdog ordering gotcha — this is *why* the window comes first.**
> On the RP2350, **once `machine.WDT` is started it cannot be stopped or
> disabled.** If we armed it before the interrupt window, then broke into the
> REPL for dev work, the watchdog would reboot the Pico every few seconds while we
> tried to type. So the watchdog is armed **after** the dev-escape window closes —
> i.e. only on the committed production path. Breaking in during the window means
> the watchdog is never armed, and the REPL is stable. (Documented here so we
> don't "tidy up" by hoisting the WDT init and silently break dev mode.)

### What dev mode looks like after this lands

Same as today, with one extra step:

1. Plug the box into the laptop.
2. MicroPico → **Stop execution** (within the boot window) to halt `main.py` and
   get the REPL. *(If we miss the window, just Stop again — once at the REPL the
   watchdog was never armed, so it stays put.)*
3. Run individual bench/harness scripts via "Run current file on Pico" exactly as
   we do now.

`main.py` sitting on flash does **not** interfere with "Run current file" — that
command runs the *current editor file*, not `main.py`. The only thing `main.py`
changes is boot behavior, which the window neutralizes.

---

## 3. The production `main.py`

**Good news: we've already written most of it.** `test/offline-harness/full_loop_test.py`
is the complete tap → feedback → MQTT → state → ring/buzzer loop, and it already
does the hard parts:

- edge-triggered tap detection with the 2 s absence cooldown
- instant local `tap_accepted()` feedback before the broker round-trip
- the deferred optimistic-`loading` grace window so HA replies always win
- guarded `check_msg()` / `publish` / `ping` with reconnect-and-retry on `OSError`
- self-pinging at half the keepalive so an idle box isn't dropped
- `finally:` cleanup that clears the ring and silences the buzzer

`main.py` is **that loop, promoted to flash and hardened** with the four things
below. The plan is to *derive* `main.py` from `full_loop_test.py`, not rewrite it
— and to keep the harness pointed at the mock HA so we still have a dev rig.

What production adds on top of the harness loop:

1. **The boot-guard window** (§2) wrapping the whole thing.
2. **A hardware watchdog**, armed after the window, **fed once per main-loop
   iteration.** Since the loop ticks every ~30 ms and the longest legitimate
   blocking call is a ~380 ms buzzer cue, a watchdog timeout of a few seconds is
   safe — it only trips on a genuine hang. The connect retry loops (§2 steps 4-5)
   must feed the watchdog too, or a slow Wi-Fi association would reboot us
   mid-connect.
3. **Connect phases wrapped in their own retry loops** rather than the single-shot
   `connect_wifi()` / `connect_mqtt()` the harness uses. A box that boots while the
   router is still coming up (e.g. after a whole-house power blip) must keep
   trying, not give up. See §4.
4. **Production `secrets.py`** values — home SSID + the **Synology** broker
   (`192.168.0.123:1883`, user `vonbox`), *not* the laptop/hotspot dev values.
   (Reminder from `CLAUDE.md`: `secrets.py` is gitignored; the swap is just
   editing the file on flash.)

What `main.py` does **not** get: any new "brains." The architecture stays
HA-owns-the-logic, Pico-is-a-dumb-input (per `CLAUDE.md`). The watchdog and retry
loops are resilience, not intelligence.

---

## 4. Resilience: how it recovers on its own

Decision: **hardware watchdog + infinite auto-reconnect.** This is a kid-facing,
daily-use, unattended device — it should never need a manual power-cycle for a
recoverable fault.

| Fault | Detection | Recovery |
|---|---|---|
| Wi-Fi never comes up at boot (router still booting) | connect loop times out | keep retrying with backoff; ring shows a distinct "no Wi-Fi" pattern; watchdog fed throughout |
| Wi-Fi drops mid-session | next socket op raises `OSError` / `wlan.isconnected()` false | reconnect Wi-Fi, then MQTT, then re-subscribe |
| Broker (Synology) restarts | `check_msg`/`publish`/`ping` raises `OSError` | reconnect + re-subscribe (the harness already does this; promote it to an unbounded retry with backoff) |
| Main loop hangs (driver wedge, infinite loop, memory) | watchdog not fed in time | hardware reboot → clean boot-guard → reconnect |
| Unhandled exception escapes the loop | top-level `try/except` | log, brief pause, **reboot** (`machine.reset()`) rather than dropping dead to the REPL — in production there's no one at the REPL |

Key principle: **in production, "fall through to the REPL" is the same as "dead."**
Nobody is watching the serial console. So the top-level posture is: catch, show a
red error on the ring, and `machine.reset()` into a fresh boot. The watchdog is
the backstop for the hangs that *can't* be caught.

Backoff: a simple capped backoff (e.g. 1 s → 2 s → 5 s → 10 s, cap 10 s) on the
reconnect loops keeps us from hammering a down router while still recovering
within seconds once it's back. The watchdog must be fed inside any wait longer
than its timeout.

---

## 5. Headless observability — the ring/buzzer *is* the console

With no laptop attached, `print()` goes nowhere. The LED ring and buzzer are the
entire diagnostic surface, so the **boot and failure states need to be legible to
the dad standing in the living room.** `lib/feedback.py` already gives us a rich
sustained-state vocabulary; production needs a few **pre-network boot/diagnostic
signals** layered on, because `feedback.py`'s states are about the *session*, not
the *box's connectivity*.

Proposed boot/diagnostic visual language (to be finalized when we build it):

| Condition | Ring | Buzzer |
|---|---|---|
| Booting / in interrupt window | dim solid (a neutral color) | silent |
| Connecting to Wi-Fi | slow pulse | silent |
| Connecting to MQTT | faster pulse | silent |
| Ready (idle) | `feedback.py` idle breathe | — |
| **Can't get Wi-Fi** (stuck retrying) | distinct slow red/amber pattern | optional periodic low blip |
| **Can't reach broker** (Wi-Fi ok) | a *different* distinct pattern | — |
| Normal session states | `feedback.py` (loading/playing/paused/etc.) | its cues |

The two "stuck" patterns must be visually distinct from each other and from the
session `error` flash, so a glance tells the dad *which* leg is down (router vs.
broker) without plugging in. This is the headless equivalent of a log line.

Open question for build time: do these boot signals live in `feedback.py` (extend
its vocabulary) or in a tiny separate `boot_status` helper so `feedback.py` stays
purely about sessions? Leaning toward a small separate helper to keep
`feedback.py`'s contract clean — decide when we write it.

---

## 6. Update strategy: re-plug into the laptop

Decision: **updates mean bringing the box to the laptop and re-uploading.** No OTA
in v1. Rationale: tag→movie mappings already live in HA (changing what a tag plays
*never* touches the Pico), so the only reason to update Pico code is a genuine
firmware/logic change — rare, and worth the two-minute walk to the desk. OTA's
extra failure surface (a half-flashed `main.py` that won't boot, by the TV, with a
toddler) isn't worth it yet.

Implications this places on the build:

- **Keep the box physically easy to open / unplug.** Whatever enclosure we end up
  with, the USB port stays accessible. Don't epoxy it shut.
- **The flash layout is the deployable artifact.** Production upload = MicroPico
  "Upload project to Pico" writing:
  - `main.py` (the orchestrator)
  - `lib/pn532.py`, `lib/feedback.py` (and the boot-status helper if we add one)
  - `lib/umqtt/simple.mpy` — **reminder: not frozen into the build.** If a Pico is
    ever reflashed, re-run `test/bench/install_umqtt.py` first (`CLAUDE.md` gotcha).
  - `secrets.py` with **production** values
- **`secrets.py` is the dev/prod config switch.** Dev = hotspot SSID + laptop
  broker IP; prod = home SSID + Synology broker. It's gitignored, so we just keep
  the prod values in the on-flash copy and the harness docs note the dev swap.
- **Update procedure (write it as a checklist when we ship):** plug in → Stop into
  REPL → upload project → power-cycle → watch the boot sequence on the ring → tap a
  known tag to confirm end-to-end → unplug, return to TV.

---

## 7. Power

The box is "plugged into the wall," which on a Pico means a **USB power supply**,
not bare mains. Considerations to lock down at build time:

- **Use a quality 5 V USB supply with adequate current headroom.** The LED ring is
  the load that matters: ~360 mA at the 25% brightness cap, and the `BRIGHTNESS`
  cap in `feedback.py` exists precisely because all-white at full tilt (~1.4 A)
  exceeds what USB/VSYS can supply. A 5 V / ≥1 A (comfortably 2 A) supply is the
  target. **Do not** rely on a random low-amp phone charger.
- **Brownout behavior:** an undersized supply sagging under an LED animation can
  brown the Pico out and cause spurious resets. The watchdog will recover it, but
  it'll look like flakiness — so size the supply right and treat repeated
  unexplained reboots as a power-supply suspect first.
- **Cable quality matters** at these currents — a thin/long cable adds resistance
  and worsens sag.
- The box should **come up clean from a dead-cold power cut** (whole-house outage):
  power returns → boot-guard window → reconnect loop patiently waits for the router
  → ready. This is the "survive the house" requirement from §1, and §4's connect
  retry loops are what make it true.

Out of scope for v1: battery / UPS operation (noted in §9).

---

## 8. Pre-deployment checklist (fill in when we execute)

A go/no-go list to run *before* the box goes to the TV for real. Draft:

- [ ] `main.py` derived from `full_loop_test.py`, boot-guard + watchdog + retry
      loops added
- [ ] Boot-guard verified: power-on runs the app; MicroPico "Stop" within the
      window reliably drops to a *stable* REPL (watchdog confirmed not armed)
- [ ] Watchdog verified: deliberately wedge the loop → box reboots itself
- [ ] Wi-Fi recovery verified: kill the router mid-session → box reconnects when
      it returns, no manual intervention
- [ ] Broker recovery verified: restart the Synology Mosquitto container → box
      reconnects + re-subscribes
- [ ] Cold-power recovery verified: pull power entirely → box comes up to "ready"
      on its own
- [ ] Headless diagnostics verified: each boot/failure state shows a distinct,
      legible ring/buzzer signal with no laptop attached
- [ ] `secrets.py` holds **production** values (home SSID + Synology broker)
- [ ] `umqtt.simple` present on flash (or installer re-run after any reflash)
- [ ] End-to-end on the real home network: tap a known tag from cold sleep →
      movie plays; tap an unknown tag → error signal; re-tap an active tag →
      `already_playing` signal
- [ ] Power supply is adequately rated; no brownout resets under LED animation
- [ ] USB port stays physically accessible for re-plug updates

---

## 9. Out of scope for v1 (future work)

Captured so they're not forgotten, explicitly *not* being built now:

- **OTA updates** — push code over MQTT/HTTP without re-plugging. Revisit if
  re-plugging proves annoying in practice.
- **Battery / UPS** — ride out power blips without a cold reboot. VSYS is already
  the future battery rail per `CLAUDE.md`.
- **Remote telemetry/logging** — publish health/heartbeat to an MQTT topic HA can
  surface, so the dad can check box health from his phone instead of reading the
  ring. (Cheap to add later; a natural first extension.)
- **Real-time clock / scheduled behavior** — e.g. a "no movies after bedtime"
  window. Would likely live in HA, not the Pico.

---

## 10. Open questions for the dad (resolve at build time)

1. **Boot-status signals:** extend `feedback.py`'s vocabulary, or a separate
   `boot_status` helper? (Leaning separate — §5.)
2. **Watchdog timeout value:** a few seconds is the working assumption; confirm it
   clears the longest legitimate blocking path (the ~380 ms boot/cue plus any
   connect step that *isn't* in a fed loop).
3. **Enclosure:** does the chosen box keep the USB port reachable for updates and
   keep the LED ring visible/diffused? (Constrains §6 and §5.)
4. **Auto-reset on unhandled exception** in production — confirm we want
   `machine.reset()` (no human at the REPL) vs. parking on a red error and waiting.
   Current recommendation: reset, since nobody's watching.

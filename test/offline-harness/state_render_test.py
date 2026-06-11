# Feedback bring-up (LAYER 1): prove lib/feedback.py renders every state's LED
# animation + buzzer cue, with NO network and NO NFC in the loop. This is the
# "can the box express itself?" test — pure local output. Layers 2/3 add MQTT
# and the PN532 on top of this same Feedback object.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   LED ring DIN -> GP28 (R7/pin34)   buzzer S -> GP22 (R12/pin29)
#   (Feedback() defaults to these pins; no args needed here.)
#
# Run ephemerally via MicroPico "Run current file on Pico". The current step
# name prints as it changes so the serial log lines up with what you see/hear.
# Ctrl-C (MicroPico "Stop execution") clears the ring + silences the buzzer.
#
# Why a dwell helper instead of plain sleep: the state animations (breathing,
# chase, comet) are non-blocking — they advance one frame per fb.tick() call.
# Sleeping through a dwell would freeze the ring on a single frame. So every
# dwell is a tight ticks_ms loop that keeps calling tick() the whole time.

import time

from feedback import Feedback

# How long to sit in each state so a human can eyeball/ear it. Units in the name.
TICK_SLEEP_MS = 15  # pacing between tick() calls; the actual frame rate is
                    # self-limited inside feedback.py, this just yields the CPU.


def dwell(fb, ms):
    # Hold the current state for `ms`, animating the whole time by pumping
    # tick() on a short cadence. The ONLY way to dwell — never bare sleep.
    deadline = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        fb.tick()
        time.sleep_ms(TICK_SLEEP_MS)


# --- the scripted walk --------------------------------------------------------

def run_sequence(fb):
    # One full pass through the whole state vocabulary, in the order the box
    # would naturally move through a tap-to-play session, plus the transients.

    # Boot flourish first — the power-on cue + warm-white comet lap. One-shot and
    # blocking by design (see Feedback.boot); here it heads each looped pass so
    # you can re-audition it without re-running the script.
    print("boot (rising fifth + warm-white comet lap)")
    fb.boot()

    print("idle (breathing soft-warm-white)")
    fb.set_state("idle")
    dwell(fb, 3000)

    # Simulate a fresh tap: LOCAL instant feedback fires first (sparkle + chime),
    # THEN we optimistically go to loading — exactly what LAYER 3 does on a tap,
    # minus the MQTT publish.
    print("tap! tap_accepted() -> loading (blue chase)")
    fb.tap_accepted()
    fb.set_state("loading")
    dwell(fb, 2500)

    # Entering playing from loading fires the "movie starting!" confirm triad
    # (rising C6-E6-G6) on top of the solid-green fill.
    print("playing (movie-starting triad -> solid green)")
    fb.set_state("playing", title="The Super Mario Bros. Movie")
    dwell(fb, 3000)

    # Transient: plays its cue then auto-reverts to the prior sustained state
    # (playing). Watch for the soft pulse + mid-note, then back to green.
    print("already_playing (transient pulse -> revert to playing)")
    fb.set_state("already_playing")
    dwell(fb, 2000)

    print("paused (breathing amber)")
    fb.set_state("paused")
    dwell(fb, 3000)

    # Transient: 3 red flashes + descending tone, then reverts to the prior
    # sustained state (paused). carry a reason like a real unknown-tag failure.
    print("error (transient 3 red flashes -> revert to paused)")
    fb.set_state("error", reason="unknown_tag")
    dwell(fb, 2000)

    print("standby (very slow breathing soft-warm-white)")
    fb.set_state("standby")
    dwell(fb, 4000)


# --- run ----------------------------------------------------------------------

print("state render test: walking the full feedback vocabulary (no net, no NFC)")

fb = Feedback()
try:
    while True:
        run_sequence(fb)
        print("--- sequence complete, looping ---")
except KeyboardInterrupt:
    pass
finally:
    fb.off()
    print("feedback cleared. done.")

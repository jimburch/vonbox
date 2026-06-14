# Bench: eyeball the headless boot/connectivity diagnostics on the ring.
#
# What this proves: the pre-network signals main.py shows when no laptop is
# attached are legible across the room AND visually distinct from one another —
# in particular the two "stuck" looks (Wi-Fi unreachable vs. broker unreachable)
# must be tellable apart at a glance, and neither should be confusable with the
# red session-error flash. No network, no NFC, no MQTT — just lib/feedback.py's
# booting() / connecting_wifi() / connecting_mqtt() / net_error() rendered on a
# timer, looping so you can compare them side by side.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   LED ring : DIN->GP28 (R7) PWR->VSYS (R2) GND->GND (R3)
#   Buzzer   : S->GP22 (R12)  -(GND)->GND (R13)   (diagnostics are silent)
#
# Pre-flight: lib/feedback.py uploaded to the Pico via MicroPico "Upload project
# to Pico" (otherwise the import below ImportErrors).
#
# Run ephemerally via MicroPico "Run current file on Pico". Ctrl-C (MicroPico
# "Stop execution") clears the ring on the way out.

import time

from feedback import Feedback

LED_PIN = 28
NUM_PIXELS = 24
BUZZER_PIN = 22

# ~25 fps, matching the cadence main.py drives these at inside its
# feed-the-watchdog connect wait — so what you see here is what prod looks like.
FRAME_MS = 40
SECONDS_PER_PHASE = 5

fb = Feedback(led_pin=LED_PIN, num_pixels=NUM_PIXELS, buzzer_pin=BUZZER_PIN)

# (label, render-one-frame callable) in the order main.py would escalate through.
PHASES = (
    ("booting (dim warm-white solid)", fb.booting),
    ("connecting_wifi (slow blue breathe)", fb.connecting_wifi),
    ("connecting_mqtt (blue dot chasing the ring)", fb.connecting_mqtt),
    ("net_error('wifi') (amber double-blink = no router link)", lambda: fb.net_error("wifi")),
    ("net_error('broker') (purple slow breathe = broker down)", lambda: fb.net_error("broker")),
)

print("boot-diagnostics walk-through, looping. Ctrl-C to stop.")
frames_per_phase = (SECONDS_PER_PHASE * 1000) // FRAME_MS

try:
    while True:
        for label, render in PHASES:
            print("->", label)
            for _ in range(frames_per_phase):
                render()
                time.sleep_ms(FRAME_MS)
except KeyboardInterrupt:
    print("\nstopping.")
finally:
    fb.off()
    print("ring cleared.")

# LED ring bring-up: prove the 24-pixel WS2812 ring lights and animates.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   PWR(5V) -> VSYS (R2/pin39)   GND -> GND (R3/pin38)   DIN -> GP28 (R7/pin34)
#
# Run ephemerally via MicroPico "Run current file on Pico". Ctrl-C (MicroPico
# "Stop execution") clears the ring on the way out so it doesn't stay lit.
#
# WS2812 detail: the neopixel driver handles GRB ordering internally, so every
# color below is plain (R, G, B). The driver is frozen into the official
# RPI_PICO2_W build — no install step needed.

from machine import Pin
from neopixel import NeoPixel
import time

LED_PIN = 28          # GP28, the ring's DIN (R7/pin34)
NUM_PIXELS = 24

# Brightness is a hard safety cap, not a preference. All-white at full
# brightness is ~60mA/pixel -> ~1.4A for 24 pixels, more than VSYS/USB can
# supply. At 0.25 the worst case (all white) is ~360mA, well within budget.
# Every color is scaled through this before it hits the strip.
BRIGHTNESS = 0.10

# Named colors in full-intensity RGB; dim() applies the brightness cap.
WHITE  = (255, 255, 255)
YELLOW = (255, 200, 0)
RED    = (255, 0, 0)
BLUE   = (0, 0, 255)
GREEN  = (0, 255, 0)
OFF    = (0, 0, 0)

ring = NeoPixel(Pin(LED_PIN), NUM_PIXELS)


# --- helpers ------------------------------------------------------------------

def dim(color):
    return tuple(int(c * BRIGHTNESS) for c in color)


def fill(color):
    c = dim(color)
    for i in range(NUM_PIXELS):
        ring[i] = c
    ring.write()


def clear():
    fill(OFF)


def wheel(pos):
    # Map 0..255 to a smooth R->G->B->R color wheel. Used for rainbow effects.
    pos &= 0xFF
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


# --- animations ---------------------------------------------------------------

def solid_color_test(hold_ms=900, gap_ms=250):
    # Each named color in turn across the whole ring, with a brief blackout
    # between so two colors never blur together.
    for name, color in (("white", WHITE), ("yellow", YELLOW),
                        ("red", RED), ("blue", BLUE)):
        print("  solid:", name)
        fill(color)
        time.sleep_ms(hold_ms)
        clear()
        time.sleep_ms(gap_ms)


def color_wipe(color, wait_ms=30):
    # Paint the ring one pixel at a time, then wipe back to off the same way.
    c = dim(color)
    for i in range(NUM_PIXELS):
        ring[i] = c
        ring.write()
        time.sleep_ms(wait_ms)
    for i in range(NUM_PIXELS):
        ring[i] = OFF
        ring.write()
        time.sleep_ms(wait_ms)


def spin(color, tail=6, revolutions=3, wait_ms=35):
    # A comet: a bright head with a fading tail chasing it around the ring.
    head_rgb = dim(color)
    for step in range(NUM_PIXELS * revolutions):
        for i in range(NUM_PIXELS):
            ring[i] = OFF
        for t in range(tail):
            # Each tail pixel sits `t` steps behind the head and is dimmer.
            idx = (step - t) % NUM_PIXELS
            falloff = (tail - t) / tail
            ring[idx] = tuple(int(c * falloff) for c in head_rgb)
        ring.write()
        time.sleep_ms(wait_ms)
    clear()


def rainbow_cycle(revolutions=3, wait_ms=15):
    # Full spectrum smeared around the ring, rotating. The classic "is it
    # working?" eye candy — every pixel and every color channel exercised.
    for j in range(256 * revolutions // NUM_PIXELS):
        for i in range(NUM_PIXELS):
            pixel_hue = (i * 256 // NUM_PIXELS + j * NUM_PIXELS) & 0xFF
            ring[i] = dim(wheel(pixel_hue))
        ring.write()
        time.sleep_ms(wait_ms)
    clear()


def theater_chase(color, cycles=6, wait_ms=60):
    # Marquee: every 3rd pixel lit, the lit set stepping forward each frame.
    c = dim(color)
    for _ in range(cycles):
        for offset in range(3):
            for i in range(NUM_PIXELS):
                ring[i] = c if (i % 3 == offset) else OFF
            ring.write()
            time.sleep_ms(wait_ms)
    clear()


def breathe(color, cycles=2, steps=40, wait_ms=20):
    # Smooth fade in/out — confirms per-pixel intensity control, not just on/off.
    base = color
    for _ in range(cycles):
        for s in list(range(steps)) + list(range(steps, -1, -1)):
            level = (s / steps) * BRIGHTNESS
            c = tuple(int(ch * level) for ch in base)
            for i in range(NUM_PIXELS):
                ring[i] = c
            ring.write()
            time.sleep_ms(wait_ms)
    clear()


# --- run the suite ------------------------------------------------------------

print("LED ring test: %d pixels on GP%d, brightness %d%%" %
      (NUM_PIXELS, LED_PIN, int(BRIGHTNESS * 100)))

try:
    while True:
        print("1/6 solid colors (white, yellow, red, blue)")
        solid_color_test()

        print("2/6 color wipe (green)")
        color_wipe(GREEN)

        print("3/6 spin / comet (blue)")
        spin(BLUE)

        print("4/6 rainbow cycle")
        rainbow_cycle()

        print("5/6 theater chase (white)")
        theater_chase(WHITE)

        print("6/6 breathe (red)")
        breathe(RED)

        print("--- suite complete, looping ---")
        time.sleep_ms(500)
except KeyboardInterrupt:
    pass
finally:
    clear()
    print("ring cleared. done.")

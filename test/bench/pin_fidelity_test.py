"""
Solder-joint fidelity test for the freshly soldered Pico headers on the proto board.

Board orientation: Pico sits in proto rows 6 through 25, USB end at row 6.
So physical Pico pin N maps to proto row:
  - left side  (pins 1-20):  proto_row = pin + 5
  - right side (pins 21-40): proto_row = 46 - pin

Method:
  All 26 user GPIOs (GP0-22, GP26-28) are configured INPUT + PULL_UP, so they
  rest at HIGH. Touch a wire connected to any GND pin against a GPIO header pin;
  if the solder joint conducts and the GPIO is functional, the script sees it go
  LOW and ticks it off the "remaining" list.

  Power and ground pins (VBUS/VSYS/3V3/GND/RUN/AGND/3V3_EN/ADC_VREF) can't be
  tested this way -- use a multimeter against the printed checklist below.

Run via MicroPico "Run current file on Pico", then walk a GND jumper across every
GPIO header pin in order. Ctrl-C when done.
"""

from machine import Pin
import time

# (GP number, physical pin, breadboard notation from CLAUDE.md, proto row)
GPIOS = [
    (0,  1,  "L1",  6),
    (1,  2,  "L2",  7),
    (2,  4,  "L4",  9),
    (3,  5,  "L5",  10),
    (4,  6,  "L6",  11),
    (5,  7,  "L7",  12),
    (6,  9,  "L9",  14),
    (7,  10, "L10", 15),
    (8,  11, "L11", 16),
    (9,  12, "L12", 17),
    (10, 14, "L14", 19),
    (11, 15, "L15", 20),
    (12, 16, "L16", 21),
    (13, 17, "L17", 22),
    (14, 19, "L19", 24),
    (15, 20, "L20", 25),
    (16, 21, "R20", 25),
    (17, 22, "R19", 24),
    (18, 24, "R17", 22),
    (19, 25, "R16", 21),
    (20, 26, "R15", 20),
    (21, 27, "R14", 19),
    (22, 29, "R12", 17),
    (26, 31, "R10", 15),
    (27, 32, "R9",  14),
    (28, 34, "R7",  12),
]

# Non-GPIO pins -- check these with a multimeter, probe to a known-good GND.
POWER_PINS = [
    # (label, expected, physical pin, notation, proto row)
    ("VBUS",     "~5.0 V",  40, "R1",  6),
    ("VSYS",     "~4.7 V",  39, "R2",  7),
    ("3V3_EN",   "3.3 V",   37, "R4",  9),
    ("3V3(OUT)", "3.3 V",   36, "R5",  10),
    ("ADC_VREF", "3.3 V",   35, "R6",  11),
    ("AGND",     "0 V",     33, "R8",  13),
    ("RUN",      "3.3 V",   30, "R11", 16),
    ("GND",      "0 V",     3,  "L3",  8),
    ("GND",      "0 V",     8,  "L8",  13),
    ("GND",      "0 V",     13, "L13", 18),
    ("GND",      "0 V",     18, "L18", 23),
    ("GND",      "0 V",     38, "R3",  8),
    ("GND",      "0 V",     28, "R13", 18),
    ("GND",      "0 V",     23, "R18", 23),
]


def print_preamble():
    print("Pico header solder-joint fidelity test")
    print("======================================")
    print()
    print("All 26 user GPIOs are now INPUT + PULL_UP. They rest HIGH.")
    print("Touch a GND jumper to each GPIO header pin in turn -- the script")
    print("will report it going LOW and tick it off the remaining list.")
    print()
    print("Multimeter checklist (these pins can't be tested via GPIO):")
    print()
    print("  pin | label    | expect  | notation | proto row")
    print("  ----+----------+---------+----------+----------")
    for label, expected, pin, notation, row in POWER_PINS:
        print(f"  {pin:>3} | {label:<8} | {expected:<7} | {notation:<8} | {row}")
    print()
    print("Place black probe on a verified-good GND row, red probe on each pin")
    print("above. For GND pins, you're checking continuity to another GND (0 V).")
    print()
    print("Now walking GPIO state. Ctrl-C to stop.")
    print("=" * 40)
    print()


def main():
    print_preamble()
    pins = [(gp, Pin(gp, Pin.IN, Pin.PULL_UP), notation, row) for (gp, _, notation, row) in GPIOS]
    seen_low = set()
    last_low = set()
    start_ms = time.ticks_ms()
    total = len(pins)

    while True:
        now_low = {gp for (gp, p, _, _) in pins if p.value() == 0}
        if now_low != last_low:
            t = time.ticks_diff(time.ticks_ms(), start_ms) / 1000
            new = now_low - seen_low
            seen_low |= now_low
            # Describe current touches
            if now_low:
                desc = ", ".join(
                    f"GP{gp}(row {row},{notation})"
                    for (gp, _, notation, row) in pins if gp in now_low
                )
                tag = " [NEW]" if new else ""
                print(f"[t={t:6.1f}s] LOW: {desc}{tag}")
            else:
                print(f"[t={t:6.1f}s] (all high)")
            # Coverage summary
            remaining = sorted({gp for (gp, _, _, _) in pins} - seen_low)
            print(f"           covered {len(seen_low)}/{total}. remaining: "
                  + (", ".join(f"GP{gp}" for gp in remaining) if remaining else "none -- all GPIOs verified"))
            last_low = now_low
        time.sleep_ms(80)


main()

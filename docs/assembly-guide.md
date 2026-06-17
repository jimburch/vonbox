# Assembly guide — breadboard → soldered Perma-Proto prototype

Step-by-step build of the **final v1 electronics**: Pico 2 WH on socket headers,
PN532 + LED ring + buzzer on detachable JST leads, all on an Adafruit
Perma-Proto Half-sized PCB. When you finish this guide you have a soldered board
that passes every `test/bench/` script — the same hardware, just permanent.

**This is a 1:1 transfer of your working breadboard.** The Perma-Proto's rows
are bussed exactly like a breadboard's, so every wire lands on the same Pico pin
it sits on now — including grounds, which go straight into the Pico's GND-pin
rows. **No power rail, no bridge wire** (the edge rails stay unused, same as on
the breadboard today).

**Scope.** Board + harness + bring-up verification. The *enclosure* fit-out
(heat-set inserts, standoffs, lid/base, USB panel inlet) comes after, once the
box is printed around the assembled stack's real measurements — that sequence
lives in
[`production-hardware.md` → "Final assembly"](./production-hardware.md#final-assembly--how-it-all-fits-in-the-enclosure).
Don't print the enclosure until this board is built and measured.

> **Golden rule, same as bring-up:** one variable at a time. Solder a stage,
> verify it, then move on. Never power the board with the Pico installed until
> the continuity checks in [Step 5](#step-5--continuity-checks-before-first-power) pass.

---

## What this build uses

From the Adafruit order (PIDs in parens):

| Part | PID | Role in this build |
|---|---|---|
| Perma-Proto Half-sized PCB, 3-pack | 571 | The board. Bussed like a half-size breadboard, so the pin map transfers hole-for-hole. You have 3 — the first one is allowed to go wrong. |
| Socket headers for Pico, 2×20 female (long) | 5583 | A **pair of 1×20 strips**. Solder one per Pico edge; the Pico plugs in and stays removable. |
| ~~Silicone wire 26 AWG — red / black / green / blue~~ | ~~1877 / 1881 / 1880 / 1878~~ | **Not used in this build.** Bought to extend lid leads + swap mismatched JST-pigtail colors, but the shipped JST pigtails are long enough to reach lid → base on their own. Stays on the shelf for a future build. |
| JST-XH matching pairs — 4-pin / 3-pin / 2-pin | 4874 / 4873 / 4872 | Detachable joints: 4-pin = PN532, 3-pin = LED ring, 2-pin = buzzer. Each pair = a plug pigtail + a receptacle pigtail, wires pre-crimped. |
| Kapton (polyimide) tape | 3057 | Insulate/mask near joints and the antenna. Optional polish. |

**Board facts (#571, confirmed from the Adafruit listing):** 3.2" × 2.0"
(81 × 51 mm), 0.063" FR4 · main grid **30 rows × columns A–J** (each row = a
5-hole node on each side of the center channel) · **2× M3 (3.2 mm) mounting
holes, 2.9" apart** (plain clearance, sized to pass an M3 standoff screw). The
Pico's 20-pin footprint sits in **rows 6–25** in this build (GP0 at row 6 — see
[Step 0](#step-0--dry-fit-no-iron) for the offset), leaving rows 1–5 and 26–30
clear at either end. The board's **edge power rails are unused in this build** —
every wire lands in a row node, exactly like your breadboard — so the rails'
mid-board split (each breaks around row 15) never matters here.

On hand: Pico 2 WH, PN532 (red HiLetgo), 24-px WS2812 ring, KY-006 buzzer, NTAG
tags, soldering gear, heat-shrink, **a multimeter**, flush cutters, wire
strippers.

> **Verify you have a USB-A → Micro-B _data_ cable.** It powers the board now and
> reflashes the closed box later. Must carry data, not charge-only.

The heat-set inserts (#4255), standoff kit (#4685), and panel-mount USB inlet
(#3258) are **enclosure** parts — set them aside until the box is printed.

---

## Chart 1 — Pico 2 W pinout (physical pin → function)

The anchor for everything below. Physical pin 1 (GP0) is top-left next to the
USB connector; pins go down the left edge to 20, then **up** the right edge from
21 to 40. **Every 5th pin is GND** (3, 8, 13, 18, 23, 28, 33, 38) — eight of
them, so each device's ground gets its own dedicated GND pin; no sharing needed.

```
                          ┌───────────  USB (Micro-B)  ───────────┐
                 GP0   1 ●│                                        │● 40  VBUS
                 GP1   2 ●│                                        │● 39  VSYS      ◀── LED ring  5V
                 GND   3 ●│                                        │● 38  GND       ◀── PN532 GND
                 GP2   4 ●│                                        │● 37  3V3_EN  ⚠ NEVER ground this
                 GP3   5 ●│            Raspberry Pi                 │● 36  3V3(OUT)  ◀── PN532  3V3 (VCC)
   PN532 SDA ──▶ GP4   6 ●│              Pico 2 WH                  │● 35  ADC_VREF
   PN532 SCL ──▶ GP5   7 ●│                                        │● 34  GP28      ◀── LED ring  DIN
                 GND   8 ●│        (USB end = protoboard row 6)      │● 33  GND (AGND)   ← spare (analog gnd)
                 GP6   9 ●│                                        │● 32  GP27
                 GP7  10 ●│                                        │● 31  GP26
                 GP8  11 ●│                                        │● 30  RUN
                 GP9  12 ●│                                        │● 29  GP22      ◀── buzzer  S
                 GND  13 ●│                                        │● 28  GND       ◀── buzzer  −
                 GP10 14 ●│                                        │● 27  GP21
                 GP11 15 ●│                                        │● 26  GP20
                 GP12 16 ●│                                        │● 25  GP19
                 GP13 17 ●│                                        │● 24  GP18
                 GND  18 ●│                                        │● 23  GND       ◀── LED ring  GND
                 GP14 19 ●│                                        │● 22  GP17
                 GP15 20 ●│                                        │● 21  GP16
                          └────────────────────────────────────────┘
                          LEFT edge = pins 1–20            RIGHT edge = pins 21–40
                          (GP0 side, "L" rows)             (VBUS/VSYS side, "R" rows)
```

Only **six GPIOs + three power nets** are wired in v1. Everything else stays
free (GP26/27/28 ADCs included — the buzzer is on plain-digital GP22).

---

## Chart 2 — the connection map (the single source of truth for wiring)

`L<n>` / `R<n>` is the protoboard-row notation: row `n` counted from the USB
end, on the **L**eft (GP0) or **R**ight (VBUS) side of the center channel. This
build seats the Pico with **GP0 in row 6** (offset +5 from the row-1 baseline
used in `CLAUDE.md`'s breadboard pin table) — the map below is already
shifted, so the numbers are literal: solder where it says.

**Grounds land directly in the Pico's GND-pin rows.** With eight GND pins all on
one net, each device gets its own: PN532 → **R8 (pin 38)**, LED ring → **R23
(pin 23)**, buzzer → **R18 (pin 28)**. No shared row, no edge rail, no bridge.

| Device | JST pin | Wire | Net | Pico pin | Label | Land it at |
|---|---|---|---|---|---|---|
| **PN532** (4-pin) | 1 | red | 3V3 | 36 | 3V3(OUT) | **R10**, R-half, free hole |
| | 2 | black | GND | 38 | GND | **R8**, R-half |
| | 3 | green | SDA | 6 | GP4 | **L11**, L-half, free hole |
| | 4 | blue | SCL | 7 | GP5 | **L12**, L-half, free hole |
| **LED ring** (3-pin) | 1 | red | VSYS (5V) | 39 | VSYS | **R7**, R-half, free hole |
| | 2 | black | GND | 23 | GND | **R23**, R-half, free hole |
| | 3 | green | DIN | 34 | GP28 | **R12**, R-half, free hole |
| **Buzzer** (2-pin) | 1 | green | S | 29 | GP22 | **R17**, R-half, free hole |
| | 2 | black | − (GND) | 28 | GND | **R18**, R-half, free hole |

Notes that save a rebuild:
- **Each device ground gets its own GND pin.** All eight GND pins are one net, so
  this is purely for tidiness: PN532 → R8 (pin 38), ring → R23 (pin 23), buzzer →
  R18 (pin 28). The high-current ring (~360 mA) deliberately sits on a *plain*
  GND, not the `AGND` pin (33). Spare GND rows remain for a future device:
  R13/pin 33 (AGND — prefer a plain GND for anything that draws current) plus
  the left-side GND rows L8/L13/L18/L23.
- **R9 (pin 37) = `3V3_EN`. Never put ground or 5 V here** — it disables the 3.3 V
  regulator and the PN532 goes dark. It sits one row from both the R8 ground and
  the PN532 3V3 (R10), so it's the easiest hole to hit by mistake. Mark it.
- **SCL is L12, DIN is R12 — same row number, opposite halves.** The center
  channel isolates them; they are *not* the same node. Don't "tidy" them
  together.
- **Only 4 PN532 conductors matter here** (3V3/GND/SDA/SCL); its other pads stay
  unused. The buzzer's middle module pin (VCC) is unused, so the 2-pin JST is
  correct.
- **The edge power rails are not used.** Leave them empty, like the breadboard.

---

## Chart 3 — Perma-Proto landing map (top view, rows 1–20)

The Pico straddles the center channel: left legs in one column, right legs 7
columns over. Each numbered row, **on one side of the channel**, is a 5-hole
node tied to the Pico leg in it — so a wire soldered into any *free* hole in that
row (same side) is electrically the same as that Pico pin. That's the whole
mechanism: ground wires in a GND-pin row = grounded; no rail needed.

```
         L-edge rails           A B C D E ║ F G H I J        R-edge rails
         [ + ][ − ]  (UNUSED)             ║                  [ + ][ − ]  (UNUSED)
                                          ║
 rows 1–5 .........   (free, USB-end overhang)              .................
 row 6   ...........   GP0  ─[L pin]──┐   ║   ┌──[R pin]─ VBUS  ...........
 row 7   ...........   GP1            │   ║   │           VSYS ●──── red→ring 5V
 row 8   ...........   GND            │   ║   │           GND  ●──── black→PN532 GND
 row 9   ...........   GP2            │   ║   │         3V3_EN ⚠ leave empty
 row 10  ...........   GP3            │   ║   │         3V3OUT ●──── red→PN532 3V3 (VCC)
 row 11  ●green SDA→PN532          GP4│   ║   │        ADCVREF
 row 12  ●blue  SCL→PN532          GP5│   ║   │           GP28 ●──── green→ring DIN
 row 13  ...........   GND            │   ║   │           GND   · (spare GND — AGND)
 row 14–16 ..........   (free)        │   ║   │      GP27/26/RUN
 row 17  ...........   GP9            │   ║   │           GP22 ●──── green→buzzer S
 row 18  ...........   GND            │   ║   │           GND  ●──── black→buzzer −
 row 19–22 .........   (free)         │   ║   │          (free)
 row 23  ...........   GND            │   ║   │           GND  ●──── black→ring GND
 row 24–25 .........   (free)         ▼   ║   ▼          (free)
 rows 26–30 ........   (free)                              .................
                            Pico LEFT legs     Pico RIGHT legs
                            (cols ~A–E half)    (cols ~F–J half)
```

Each `●` is one wire soldered into a free hole of that row, same side of the
channel as the Pico leg = same node as the pin. Exact column (A/C/D/E vs
F/G/H/J) doesn't matter — pick whichever hole is easiest to reach. Each device
ground now sits on its own GND row (R8, R23, R18), so no row holds two grounds.

---

## Tools & consumables

Soldering iron (~340 °C for leaded, ~370 °C lead-free) + fine tip · solder ·
flux pen · solder wick + pump (for fixes) · **multimeter (continuity + DC
volts)** · flush cutters · wire strippers · helping-hands/PCB vise · heat-shrink
assortment + heat source · Kapton tape (#3057) · the three JST pairs · the
silicone wire spools.

---

## Step 0 — dry fit, no iron

1. Take **one** Perma-Proto board. Find on the silkscreen: rows 1–30, columns
   `A–J`, and the center channel. (The `+`/`−` edge rails exist but this build
   leaves them empty.)
2. Press the two female socket strips onto the Pico's header pins (one per edge).
   This Pico+sockets sandwich is your alignment jig. Lower it onto the board so
   the socket tails drop through holes with **GP0 in row 6** (offset +5 from the
   row-1 baseline — gives the USB jack room to overhang rows 1–5 without
   fouling the standoff). Confirm the legs straddle the channel and land
   cleanly — 7 columns apart, one row of free holes outside each. Mark row 6 and
   the **R9 / 3V3_EN** hole with a dab of marker.

> The charts above (Charts 2 and 3) are already written for the row-6 offset, so
> the row numbers in them are literal: solder where they say. If a future build
> ever changes the offset, every row number in Charts 2–3 and in Steps 2 / 5
> shifts together by the same amount.

---

## Step 1 — solder the female sockets

The sockets are the only thing soldered *to* the Pico's footprint, so get them
straight; a skewed strip means the Pico won't seat.

1. With the Pico+sockets jig still seated in the board, **tack one pin at each of
   the four corners** (both ends of both strips). Heat the pad + tail together,
   feed a little solder, ~1 s.
2. Lift gently — does the Pico still slide out of the sockets? Are both strips
   flush and parallel? If a strip tilted, reheat the one tacked pin and press it
   flat. Fix alignment **now**, while only 4 joints exist.
3. **Pull the Pico out.** Solder every remaining socket pin with the Pico
   removed — full, shiny, volcano-shaped joints, no heat into the Pico.
4. Reseat and unseat the Pico once to confirm fit. Then pull it back out — it
   stays out until [Step 6](#step-6--bring-up-one-device-at-a-time).

---

## Step 2 — board-side JST pigtails

Each JST pair has two pigtails. The **board-side** one solders into the
protoboard; the **device-side** one (Step 3) solders to the device. Pick which
pigtail of the pair is "board side" per connector and stay consistent (e.g.
always solder the **receptacle** to the board, **plug** to the device — so every
device plugs the same way).

For each connector, strip ~3 mm off each board-side wire, tin it, and solder it
into the hole from Chart 2. Work one connector at a time; tug-test each joint.

1. **PN532 (4-pin):** red → R10 (R-half) · black → **R8** (R-half) · green → L11
   (L-half) · blue → L12 (L-half).
2. **LED ring (3-pin):** red → R7 (R-half) · black → **R23** (R-half, pin 23 GND)
   · green → R12 (R-half).
3. **Buzzer (2-pin):** green → R17 (R-half) · black → **R18** (R-half, pin 28 GND).

> **No extensions in this build.** The JST pigtails ship long enough to span
> lid → base on their own, so you solder the pigtail wires straight into the
> protoboard holes — no splicing, no silicone-wire extensions, and whatever
> colors the pigtails ship with are what the harness wears. (If a future
> revision moves a device farther from the board or the colors bother you, the
> 4-color silicone wire is on the shelf — splice in with a soldered joint and
> heat-shrink, never a twist.)

---

## Step 3 — device-side leads

On the bench each device ends in **bare male header pins** — there's no
connector to preserve. Snip those pins off and solder the device-side JST
pigtail directly to the leads/pads.

> Your current breadboard jumper colors are arbitrary (orange/white/purple/grey
> in the photo) — **don't try to preserve them.** Identify each connection by the
> device's *pad label*, and adopt the clean red/black/green/blue scheme on the
> new harness.

1. **PN532:** snip the bench header. Solder the device-side 4-pin pigtail to the
   **`VCC / GND / SDA / SCL`** pads — `VCC` is the power pad, fed from the Pico's
   **3V3** (pin 36, R10 per Chart 2). Colors: red→VCC, black→GND, green→SDA,
   blue→SCL. Heat-shrink each joint. (The board's remaining pads — `RSTO`, `IRQ`,
   and the SPI/UART pins — stay open; the driver polls over I²C and uses no
   interrupt or reset line.) Keep this lead long enough to reach from the lid down
   to the base.
2. **LED ring:** solder the device-side 3-pin pigtail to the **`5V (PWR)` / `GND`
   / `DIN`** pads — leave `DOUT` empty. Red→PWR, black→GND, green→DIN. The pads
   are spread around the ring, not inline; that's fine — one wire per pad, JST
   end stays a tidy 3-position plug. Heat-shrink. Lid-length lead.
3. **Buzzer (KY-006):** solder the device-side 2-pin pigtail to **`S`** and
   **`−`** (green→S, black→−); the middle `VCC` pin is unused — leave it. Short
   lead (buzzer lives in the base). Heat-shrink.

> Strain-relief everything: heat-shrink over each joint, and leave a little slack
> so lifting the lid never pulls a solder pad off a device.

---

## Step 4 — Kapton & tidy

Lay Kapton tape over any joints near the board edge or where leads cross, and
keep a clear, metal-free zone for the PN532 antenna face. Don't bundle leads so
tight they can't flex when the lid lifts.

---

## Step 5 — continuity checks BEFORE first power

Pico still **out** of the sockets. Multimeter on continuity (beep). This is the
step that prevents a magic-smoke moment.

1. **Each ground reaches its Pico GND pin:** PN532 black ↔ socket R8 (pin 38) ·
   ring black ↔ socket R23 (pin 23) · buzzer black ↔ socket R18 (pin 28). All
   three should also beep to each other — they're the same ground net.
2. **No power-to-power shorts** (must NOT beep):
   - R8 (GND) ↔ R7 (VSYS)  → silent
   - R8 (GND) ↔ R10 (3V3)  → silent
   - R7 (VSYS) ↔ R10 (3V3) → silent
3. **3V3_EN is clear:** R9 must NOT beep to GND, to VSYS, or to 3V3. If it does,
   you've bridged into row 9 — fix before anything else.
4. **Signals reach their pins** (beep): PN532 green ↔ socket L11 · PN532 blue ↔
   socket L12 · ring green ↔ socket R12 · buzzer green ↔ socket R17.
5. **Power reaches its pins** (beep): PN532 red ↔ socket R10 · ring red ↔ socket
   R7.
6. Eyeball every joint under light for bridges/cold joints; reflow any dull or
   blobby ones.

Only when all of the above pass: seat the Pico.

---

## Step 6 — bring-up, one device at a time

Plug the Pico into the sockets, connect **one** device by its JST, and run that
device's bench script via MicroPico's *Run current file on Pico*. Same
one-variable rule as the original bring-up — if it fails, the fault is in that
one device's harness, nowhere else.

| Order | Connect | Run | Pass = |
|---|---|---|---|
| 1 | PN532 only | `test/bench/i2c_scan.py` | device answers at `0x24` |
| 2 | PN532 only | `test/bench/nfc_firmware_test.py` | reports PN532 firmware 1.6 |
| 3 | PN532 only | `test/bench/nfc_tap_test.py` | `TAPPED: <UID>` once per tap, 2 s cooldown |
| 4 | + LED ring | `test/bench/led_ring_test.py` | all 24 px, every animation, no flicker |
| 5 | + buzzer | `test/bench/buzzer_test.py` | clean tones, full sweep |
| 6 | all three | `test/bench/wifi_test.py` → `mqtt_hello_test.py` | Wi-Fi assoc + heartbeat received |
| 7 | all three | `test/offline-harness/full_loop_test.py` (+ laptop `mock_ha.py`) | tap → ring/buzzer feedback → state render, full loop |

> **Power sanity on the ring:** brightness is capped at 25 % in firmware
> (`BRIGHTNESS = 0.25`) — a hard current limit. Don't raise it; all-white at full
> tilt (~1.4 A) exceeds what VSYS/USB supplies. If the ring glitches over the new
> longer leads (it ran fine on the bench), the first cheap fix is a 300–500 Ω
> resistor in the DIN line — see the WS2812 note in `production-hardware.md`.

If a stage fails, unplug back to the last passing stage, fix that one harness,
re-test. Don't proceed with two unknowns.

---

## Done when

- [ ] Female sockets soldered; Pico seats and removes cleanly.
- [ ] Each device ground lands in its own Pico GND-pin row (PN532 R8/pin 38, ring R23/pin 23, buzzer R18/pin 28) — confirmed by continuity.
- [ ] All continuity checks in Step 5 pass — including R9/3V3_EN clear of GND/5V/3V3.
- [ ] Each of the three devices on its own JST lead, heat-shrunk, strain-relieved.
- [ ] Every Step 6 bench script passes, in order, ending with the full offline loop.

At that point the prototype is electrically final. **Next:** measure the
assembled stack, then print and fit the enclosure following
[`production-hardware.md` → "Final assembly"](./production-hardware.md#final-assembly--how-it-all-fits-in-the-enclosure)
(heat-set inserts → standoffs → base → USB inlet → lid → close-up).

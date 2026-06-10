# Production hardware — breadboard → enclosure shopping list

What to buy to move the working breadboard prototype into the final printed
enclosure. The wiring-migration *strategy* is in `spec.md` → Phase 5; this is
the concrete parts list. Prices are rough 2026 US hobby-retail (Adafruit /
Pimoroni / Amazon).

> **📦 Status: ORDERED — 2026-06-10.** Whole list placed as a single Adafruit
> order (~$52.90 + USPS Ground Advantage $8.78 = **~$61.70 all-in**). Shipping
> ETA ~5–8 business days → roughly **Jun 17–22**. Going all-Adafruit beat an
> all-Amazon cart (~$73) because Amazon forces larger multipacks on wire,
> inserts, headers, and JST — the multipack premium dwarfed the shipping saved.
> Enclosure assembly (Phase 5) is blocked on delivery; **software work continues
> in the meantime** — see ["While the parts ship"](#while-the-parts-ship) below.

## What stays (already owned, moves into the box as-is)

| Component | Notes |
|---|---|
| Raspberry Pi Pico 2 WH | Plugs into sockets on the protoboard — never soldered down, so it stays removable for reflashing |
| HiLetgo PN532 NFC module | Mounts directly under the top surface (read range is short) |
| WS2812 24-px LED ring | Sits just below the top surface around the tap zone |
| KY-006 passive buzzer | Needs a small vent hole or slot in the enclosure |
| NTAG215 stickers/cards | Tag tokens, unchanged |

That's the complete device list for v1: **Pico, PN532, LED ring, buzzer.**
Power is a USB cable plugged straight in — no battery.

## The "refined breadboard" — yes, it exists

The breadboard's permanent replacement is a **Pico-specific protoboard**: a
solderable board with the Pico's footprint and pin labels on the silkscreen, so
transferring the layout from the pin-allocation table in `CLAUDE.md` is almost
mechanical.

| Item | ~Price | Notes |
|---|---|---|
| **Adafruit Perma-Proto Half-sized Breadboard PCB** (3-pack, **#571**) — *ordered* | $12.50 | An exact PCB clone of a half-size breadboard: same bussed rows of 5, same power rails, same hole spacing. The `CLAUDE.md` pin map is written in breadboard rows, so the layout transfers hole-for-hole. Two **M3** mounting holes built in (plain clearance holes — sized to pass an M3 screw, not tapped). 3-pack = spares for botched solder jobs. *Skip the cheaper Amazon clones — their layout may not match the bussed breadboard map the pin table depends on.* |
| **Adafruit Socket Headers for Raspberry Pi Pico — 2×20 pin Female, "long" (#5583)** — *ordered* | $0.95 | A matched pair of single-row 1×20 female sockets (one per Pico edge). Soldered to the protoboard; the Pico 2 WH's pre-soldered headers plug into these and stay removable. **"Long" (#5583, $0.95), not "short" (#5585)** — cheaper, and the extra clearance under the Pico lets a jumper tuck beneath it. The "2×20" in the name means *a pair of* 1×20 strips, **not** a double-row block — a double-row socket can't straddle the Pico |

Alternative: **Pimoroni Pico Proto** (~$3) — smaller, with the Pico's pinout
labeled on the silkscreen, but its 6×20 grid is *unbussed* (every connection is
a hand-soldered bridge), there's less room for the JST headers, and the
breadboard row map doesn't transfer directly. The Perma-Proto is the easier
build for this project.

> **Note on the half-size Perma-Proto's power rails:** unlike a full-size board,
> it has 4 *shorter* rail segments rather than two full-length rails per side.
> With only ~9 conductors that's plenty, but lay out the shared GND rail with
> that in mind.

## Connectors and wiring

Replace jumper wires with soldered runs + detachable connectors, so each
device can be unplugged for maintenance (per the Phase 5 plan). On the bench,
every device currently terminates in **bare male header pins** (what plugs into
the breadboard jumpers) — there's no existing connector standard to preserve, so
snip those pins and solder a JST pigtail to each device lead.

| Item | ~Price | Notes |
|---|---|---|
| **JST-XH "Cable Matching Pair" — Adafruit #4874 (4-pin), #4873 (3-pin), #4872 (2-pin)** — *ordered* | $0.95 ea | 4-pin for the PN532 (3V3/GND/SDA/SCL), 3-pin for the ring (VSYS/GND/DIN), 2-pin for the buzzer (S + −; the module's middle VCC pin is unused, so only 2 conductors). Each is a **plug pigtail + receptacle pigtail with wires pre-crimped** — no crimp tool. $2.85 for all three. *Not the #4423 560-pc "Connector Kit" — that's empty housings + loose pins that need a ~$25 crimper* |
| **Silicone stranded hookup wire, 2 m × 26 AWG** — Adafruit **#1877 red / #1881 black / #1880 green / #1878 blue** — *ordered* | $3.80 | One 2 m length per color (~$0.95 ea). 2 m each is plenty for ~9 short conductors with re-do slack. Red=power, black=GND, green+blue=signal. Flexible silicone won't fight the enclosure; 26 AWG handles the ring's ~360 mA fine |
| Heat-shrink tubing assortment | — | *On hand.* Strain relief at every solder joint |
| Solid-core wire | $0 | *On hand* — cut existing breadboard jumpers for the short on-protoboard bridges (solid-core sits flatter in the channels than the silicone stranded). Spool option if wanted: Adafruit 22 AWG solid hook-up wire |

> **The JST junction is a soldered cable-to-cable splice, not a header that
> mates with the device's pins.** Each matching pair is two pigtails with bare
> wire ends — you *solder* those wires to the device leads/pads, and the two JST
> halves latch together in the middle of the run. So the physical arrangement of
> a device's pins is irrelevant; only the **conductor count** picks the connector
> size. (The LED ring's three pads are spaced apart, not in an inline header —
> doesn't matter: one wire solders to each, the JST end stays a tidy 3-position
> plug.) JST-XH **latches**, which matters for a toddler-handled box.
>
> *Earlier draft of this doc sent the JST kit to Amazon because Adafruit's JST-**PH**
> matching pairs had the 4-pin out of stock and no 2-pin. Adafruit's JST-**XH**
> matching-pair line (#4872/#4873/#4874) carries all three in stock, so the whole
> build stays a single Adafruit order — cheaper ($2.85) and locking.*

*(Soldering gear — iron, solder, flux, wick — already owned; not listed.)*

## Enclosure mounting + power

**Fastener system: standardized on M3 throughout.** The only board that gets
screwed down is the Perma-Proto, whose mounting holes are M3 — so M3 screws seat
snugly there (an M2.5 screw rattles in an M3 hole). Insert, both ends of the
standoff, and the screw all share the M3 thread spec. The PN532 is *not*
screwed — it's foam-taped flush under the tap zone (no metal near the antenna).

| Item | ~Price | Notes |
|---|---|---|
| **M3 × 4 mm heat-set brass inserts, 50-pk** — Adafruit **#4255** — *ordered* | $5.95 | The "screw sockets" that melt into the printed plastic with the soldering iron; the standoff's male end threads into them. 4 mm length = more pull-out resistance than the 3 mm (#4256). Adafruit stocks **only M3** inserts — one of the reasons the whole stack went M3 |
| **M3 nylon screw + standoff kit** — Adafruit **#4685** — *ordered* | $16.95 | Stands the Perma-Proto off the enclosure floor. Includes **both** F-F and **M-F** standoffs — use the **male-female** ones (20× 6 mm, 10× 12 mm): male end into the insert, board screws onto the female top. Nylon (not metal) is safe near the PN532 antenna. *(Amazon's HVAZI 240/260-pc M3 kit, ~$10, is the cheaper equivalent if not consolidating on Adafruit.)* |
| **Panel-mount USB extension** — Adafruit **#3258** (Micro-B male→female, ~25 cm) — *ordered* | $4.95 | Clean power inlet on the back wall instead of a cable squeezing inside to the Pico's own jack. **Micro-B both ends** (Pico is Micro-B). Data-capable, so reflashing through the closed box works. Mounting ears ship with M3 screws installed. *Stayed Micro-B (not USB-C) deliberately: a USB-C panel inlet needs CC pull-down resistors to draw power, which cheap passthrough cables omit — Micro-B is dumb 5 V, always works* |
| **5 V / 2 A USB-A wall supply** — Adafruit **#1994** — *ordered* | $7.95 | Confirmed the **USB-A-port** version (not the barrel-jack #1995). 2 A leaves headroom; the ring stays capped at 25 % in firmware (~360 mA) regardless. *A 5 W (1 A) phone charger also works at the 25 % cap (~400–500 mA peak) — only insufficient if the brightness cap is ever raised.* Skip this buy entirely if a 2 A USB brick is already on hand |
| Right-angle Micro-B cable (USB-A → Micro-B) | — | **Deferred** — decide after seeing how the box sits on the console. Any data-capable Micro-B cable works; right-angle is purely so the cable runs flat along the back wall instead of jutting out |
| **Kapton (polyimide) tape, 1 cm** — Adafruit **#3057** — *ordered* | $4.95 | Optional polish — insulating/masking around solder joints and the antenna area. Not on the critical path (heat-shrink + foam tape cover the essentials); bought as a useful kit staple |
| Double-sided foam mounting tape | — | *On hand.* PN532 sits flush under the top surface; foam tape beats screws there. Also tacks the buzzer behind its vent slots |
| Small zip ties / adhesive cable-tie mounts | — | *On hand.* Internal strain relief |
| Translucent/white PLA | — | *On hand.* Ring diffuser (already in the Phase 5 plan) |

## Explicitly *not* needed for v1

- **SSD1306 OLED** — cut from v1 ([ADR 0003](./adr/0003-drop-oled-for-v1.md)). It would share the existing I²C bus (GP4/GP5) with the PN532, so adding it later costs no new pins — just a 4-pin JST lead and an enclosure window.
- **KY-040 rotary encoder / play-pause button** — dropped from v1 ([ADR 0002](./adr/0002-drop-volume-knob-and-play-pause-button-for-v1.md)).
- **Battery + charging dock** — the box is wall-powered over USB, full stop. If a battery ever happens, VSYS is already the right rail, so nothing here blocks it.
- **Custom PCB** — the "v2 final form" in `spec.md`, only after the design has been stable for 6+ months.
- **Level shifter for the WS2812 ring** — it's been running fine on a 3.3 V data signal from GP28 with 5 V power on the bench; don't add parts to fix a problem you don't have. If the ring glitches *after* the move to longer wires, a 300–500 Ω resistor in the DIN line is the first cheap fix.

## While the parts ship

The enclosure build can't start until the box arrives, but **none of the
remaining *software* work needs the production hardware** — it all runs on the
existing breadboard + HA. So the next development step is to close out the
in-flight milestone rather than idle:

1. **Phase 3 step 6 — real-HA `vonbox/state` publishing (the active milestone).**
   The Pico side is already proven against the mock HA
   (`test/offline-harness/full_loop_test.py` + `lib/feedback.py`). The new work is
   the **real Home Assistant automations** that publish the tagged `vonbox/state`
   payload (`idle` / `loading` / `playing` / `already_playing` / `paused` /
   `standby` / `error`) off *actual* Apple TV + Plex playback state, so the LED
   ring reflects reality instead of a scripted mock. Build on
   `test/home-assistant/play_from_tap.yaml`; an unknown UID should publish
   `error` + `reason: "unknown_tag"` (the warn-and-stop gap noted in `CLAUDE.md`).

2. **Phase 4 finish — lock the buzzer cues.** Pick which tones from
   `test/bench/buzzer_test.py` become `play_success()` / `play_error()`, and bind
   `lib/feedback.py` to the real `vonbox/state` feed once step 1 is publishing it.

Both are doable today on the breadboard. When the parts land, *then* start the
enclosure build below. (Roadmap of record stays `spec.md` / `CLAUDE.md` — update
those when these milestones close.)

## Order of operations (so nothing gets soldered twice)

1. Solder female headers + JST headers to the protoboard; transfer the layout from the `CLAUDE.md` pin table.
2. Plug the Pico in, connect each device by its JST lead, and re-run the bench scripts (`test/bench/`) one device at a time — same one-variable-at-a-time rule as bring-up.
3. Only then design the enclosure around the assembled stack's real measurements.

## What was actually ordered

The entire list came from **Adafruit in a single order** — no Amazon or other
site. (The JST kit was the one near-exception, resolved by Adafruit's JST-XH
matching pairs being in stock — see the JST note above.)

**Adafruit (~$52.90):** Perma-Proto #571 · Pico socket headers #5583 (long) ·
silicone wire #1877/#1881/#1880/#1878 · panel-mount USB #3258 · Kapton #3057 ·
M3×4 mm inserts #4255 · M3 standoff kit #4685 · JST-XH pairs #4872/#4873/#4874.

**On hand (not ordered):** Pico 2 WH, PN532, LED ring, buzzer, NTAG tags ·
soldering gear + heat-shrink · solid-core jumpers to cut · double-sided foam
tape · zip ties · white/translucent PLA · a 2 A USB wall charger.

**Must already have (verify):** a **USB-A → Micro-B *data* cable** to feed the
#3258 inlet from the charger — the box has no power path without it, and it must
carry data so reflashing through the closed box works.

**Deferred / optional:** right-angle Micro-B cable (decide after console fit) ·
WS2812 robustness parts — a 470 Ω data resistor + 1000 µF cap — *not* bought, per
the "don't add parts to fix a problem you don't have" rule; add only if the ring
glitches over the longer enclosure wiring.

**Total ordered: ~$52.90, all Adafruit.**

## Final assembly — how it all fits in the enclosure

The box is two printed parts: a **lid** carrying everything Von interacts with
(tap zone, PN532, LED ring) and a **base** carrying everything else
(protoboard + Pico, buzzer, USB inlet). The two halves connect through just two
JST leads, so the lid lifts off for service without desoldering anything.

```
                 Von taps tag here
                        ▼
┌──────────────────────────────────────────────┐
│ LID                                          │
│   tap-zone surface — keep the plastic thin   │
│   (~2 mm) directly over the antenna          │
│   • PN532, antenna up, foam-taped flush      │
│     under the tap zone (no screws/inserts    │
│     over the antenna — metal kills range)    │
│   • LED ring concentric around the tap zone, │
│     behind a translucent printed diffuser    │
└────── 4-pin + 3-pin JST leads drop down ─────┘
┌──────────────────────────────────────────────┐
│ BASE                                         │
│   • Perma-Proto on standoffs over heat-set   │
│     inserts (its two mounting holes are      │
│     M3-sized)                                │
│   • Pico 2 WH plugged into the female        │
│     sockets — never soldered down            │
│   • buzzer foam-taped behind vent slots      │
│   • panel-mount USB inlet in the back wall ──┼──▶ USB cable ──▶ 5 V/2 A wall adapter
└──────────────────────────────────────────────┘
```

Electrical chart (matches the `CLAUDE.md` pin table):

```
wall adapter ── USB cable ──▶ panel-mount inlet ── short internal pigtail ──▶ Pico USB port

Pico 2 WH (in sockets on the Perma-Proto)
  ├── 4-pin JST ──▶ PN532    3V3 · GND · SDA (GP4) · SCL (GP5)     [lid]
  ├── 3-pin JST ──▶ LED ring VSYS · GND · DIN (GP28)               [lid]
  └── 2-pin JST ──▶ buzzer   S (GP22) · GND                        [base]
```

Build sequence:

1. **Protoboard first** (see order of operations above): female sockets +
   three JST headers soldered, every device re-verified with its bench script
   *before* anything touches the enclosure.
2. **Print the base and lid** around the assembled stack's real measurements.
   Print a flat test coupon of the tap-zone thickness first and confirm the
   PN532 still reads a tag through it — read range is only ~2–3 cm bare, and
   plastic thickness comes straight out of that budget.
3. **Base fit-out:** melt the heat-set inserts into the bosses, screw the
   standoffs down, mount the Perma-Proto, plug in the Pico.
4. **Power path:** bolt the panel-mount USB inlet into the back wall, plug its
   internal pigtail into the Pico. From here on, firmware updates happen by
   plugging the laptop into the back of the closed box — the inlet passes data
   as well as power, so MicroPico works without opening anything.
5. **Lid fit-out:** foam-tape the PN532 centered under the tap zone, seat the
   LED ring around it behind the diffuser (foam tape or printed clips —
   no metal fasteners in this zone).
6. **Buzzer:** foam-tape it behind the vent slots in the base wall.
7. **Close up:** connect the two lid JST leads, zip-tie the slack to adhesive
   mounts so lifting the lid never tugs a solder joint, screw the lid down
   into its inserts.

Serviceability checklist the design must preserve:

- Lid off = two JST connectors, four screws. No tools beyond a screwdriver.
- Pico swaps by unplugging the USB pigtail and pulling it from its sockets.
- Reflash/debug over the rear USB port with the box closed; BOOTSEL only
  needs the lid off (or `machine.bootloader()` from the REPL, no button).
- Any single device unplugs at its JST lead and is re-testable on the bench
  with its `test/bench/` script, unchanged.

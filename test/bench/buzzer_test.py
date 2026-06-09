# Buzzer bring-up: prove the KY-006 passive piezo plays tones, and audition a
# menu of success / error / neutral cues so we can pick the ones Von will hear.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   S (signal) -> GP22 (R12/pin29)   - (GND) -> GND (R13/pin28)   middle pin: unused
#
# Run ephemerally via MicroPico "Run current file on Pico". Each tone prints its
# name as it plays — call out the numbers you like. Ctrl-C (MicroPico "Stop
# execution") silences the pin on the way out.
#
# Passive piezo detail: it makes NO sound on plain DC. Pitch comes from the PWM
# *frequency*; we gate sound on/off with the duty cycle (0 = silent). That's the
# whole reason this part can play distinct rising/falling tones instead of one
# fixed beep like an active buzzer.

from machine import Pin, PWM
import time

BUZZER_PIN = 22

# Duty sets volume/timbre, not pitch. 50% (32768/65535) is the standard square
# drive and about as loud as the piezo gets. Drop it if it's piercing on the bench.
VOLUME_DUTY = 32768

buzzer = PWM(Pin(BUZZER_PIN))

# Note frequencies in Hz. A piezo is loudest near its mechanical resonance
# (~2-4kHz for these), so the high notes will ring noticeably louder than the
# low ones — that contrast is useful: bright = good, low/dull = bad.
G3, A3, B3 = 196, 220, 247
C4, D4, E4, F4, G4, A4, B4 = 262, 294, 330, 349, 392, 440, 494
C5, E5, G5, A5, B5 = 523, 659, 784, 880, 988
C6, E6, G6, C7 = 1047, 1319, 1568, 2093
LOW_BUZZ = 110  # deliberately dull/quiet — reads as "wrong"


# --- core ---------------------------------------------------------------------

def tone(freq, ms, gap_ms=40):
    # One note, then a short silence so adjacent notes don't slur together.
    buzzer.freq(freq)
    buzzer.duty_u16(VOLUME_DUTY)
    time.sleep_ms(ms)
    buzzer.duty_u16(0)
    if gap_ms:
        time.sleep_ms(gap_ms)


def play(notes):
    # notes: list of (freq, ms). freq == 0 is a rest.
    for freq, ms in notes:
        if freq == 0:
            buzzer.duty_u16(0)
            time.sleep_ms(ms)
        else:
            tone(freq, ms)


def silence():
    buzzer.duty_u16(0)


# --- success cues (bright, rising) -------------------------------------------

def success_coin():
    # The classic "got a coin" — short high note jumping up to a higher one.
    play([(B5, 90), (E6, 220)])


def success_arpeggio():
    # Major arpeggio sprinting upward: unmistakably "yes / it worked".
    play([(C5, 90), (E5, 90), (G5, 90), (C6, 220)])


def success_double_ding():
    # Two quick identical high chirps — simple, friendly, very "confirmed".
    play([(G6, 110), (0, 60), (G6, 160)])


def success_level_up():
    # Longer celebratory run for the big "movie starting!" moment.
    play([(C5, 80), (E5, 80), (G5, 80), (C6, 80), (E6, 80), (G6, 260)])


# --- error cues (low, falling, dull) -----------------------------------------

def error_low_buzz():
    # Single long low note — the universal "nope".
    play([(LOW_BUZZ, 450)])

def error_descending():
    # Sad "wah-wah" two-note fall.
    play([(A3, 200), (0, 30), (175, 350)])  # 175 Hz ~= F3, a dull low landing


def error_double_low():
    # Two blunt low beeps — "try again".
    play([(B3, 150), (0, 80), (B3, 150)])


def error_raspberry():
    # Very low, slightly longer — the harshest "that didn't work" we've got.
    play([(LOW_BUZZ, 120), (0, 40), (LOW_BUZZ, 120), (0, 40), (LOW_BUZZ, 300)])


# --- neutral cues (single, mid-range, unemotional) ---------------------------

def neutral_blip():
    # One mid beep — "I heard you / tap registered", no judgement.
    play([(A5, 120)])


def neutral_tick():
    # Tiny high click — the lightest possible acknowledgement.
    play([(C7, 30)])


def neutral_ready():
    # Soft mid tone — could be a "powered on / ready" cue.
    play([(G5, 250)])


def neutral_two_tone():
    # Small step up, calm and informational (not as triumphant as success).
    play([(E5, 120), (G5, 160)])


# --- range check --------------------------------------------------------------

def frequency_sweep():
    # Glide low -> high so you can hear the full usable range and where the
    # piezo peaks (it'll get noticeably louder near resonance, ~2-4kHz).
    f = 150
    while f < 4000:
        buzzer.freq(int(f))
        buzzer.duty_u16(VOLUME_DUTY)
        time.sleep_ms(12)
        f *= 1.06
    silence()


# --- audition the menu --------------------------------------------------------

CUES = [
    ("success: coin",          success_coin),
    ("success: arpeggio",      success_arpeggio),
    ("success: double ding",   success_double_ding),
    ("success: level up",      success_level_up),
    ("error:   low buzz",      error_low_buzz),
    ("error:   descending",    error_descending),
    ("error:   double low",    error_double_low),
    ("error:   raspberry",     error_raspberry),
    ("neutral: blip",          neutral_blip),
    ("neutral: tick",          neutral_tick),
    ("neutral: ready",         neutral_ready),
    ("neutral: two-tone",      neutral_two_tone),
    ("--- frequency sweep ---", frequency_sweep),
]

print("buzzer test: passive piezo on GP%d" % BUZZER_PIN)

try:
    while True:
        for i, (name, fn) in enumerate(CUES):
            print("%2d  %s" % (i, name))
            fn()
            time.sleep_ms(700)  # breathing room so cues stay distinct
        print("--- menu complete, looping ---")
        time.sleep_ms(1200)
except KeyboardInterrupt:
    pass
finally:
    silence()
    buzzer.deinit()
    print("buzzer silenced. done.")

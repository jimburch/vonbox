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
G3, GS3, A3, AS3, B3 = 196, 208, 220, 233, 247
C4, CS4, D4, DS4, E4, F4, FS4, G4, GS4, A4, AS4, B4 = (
    262, 277, 294, 311, 330, 349, 370, 392, 415, 440, 466, 494
)
C5, CS5, D5, DS5, E5, F5, FS5, G5, GS5, A5, AS5, B5 = (
    523, 554, 587, 622, 659, 698, 740, 784, 831, 880, 932, 988
)
C6, CS6, D6, DS6, E6, F6, FS6, G6, GS6, A6, AS6, B6 = (
    1047, 1109, 1175, 1245, 1319, 1397, 1480, 1568, 1661, 1760, 1865, 1976
)
C7 = 2093
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


# --- themed cues (famous game / cartoon / TV / movie hooks) ------------------
#
# Piezo limits to keep in mind while reading these:
#   - monophonic: one note at a time, no chords, no harmony.
#   - resonance peaks ~2-4 kHz, so anything below ~250 Hz reads as a muted thud.
#     Iconic low themes (Jaws, Imperial March bass) are transposed up an octave
#     or two so they're actually audible — they lose menace but stay recognisable.
#   - timings are short on purpose so each cue fits inside the ~1s "feedback
#     after a tap" window. They're hooks, not full songs.


# Video games -----------------------------------------------------------------

def game_mario_theme():
    # Super Mario Bros. overworld, opening phrase. Everyone knows this one.
    play([
        (E5, 120), (E5, 120), (0, 120), (E5, 120),
        (0, 120), (C5, 120), (E5, 120), (0, 120),
        (G5, 120), (0, 360), (G4, 120),
    ])


def game_mario_1up():
    # The "extra life" jingle — bright six-note climb, cousin of success_coin.
    play([(E5, 120), (G5, 120), (E6, 120), (C6, 120), (D6, 120), (G6, 180)])


def game_mario_powerup():
    # Mushroom power-up: tumbling-upward run, hugely recognisable.
    play([
        (C5, 60), (G5, 60), (C6, 60),
        (E5, 60), (A5, 60), (B5, 60),
        (A5, 60), (GS5, 60), (C6, 60),
        (E6, 60), (A6, 60), (F6, 60),
        (A6, 60), (B6, 200),
    ])


def game_zelda_secret():
    # "You found a secret!" six-note jingle from The Legend of Zelda.
    play([
        (G5, 140), (FS5, 140), (DS5, 140), (A4, 140),
        (GS4, 140), (E5, 140), (GS5, 140), (C6, 320),
    ])


def game_tetris():
    # Korobeiniki, opening bars — the Game Boy Tetris theme.
    play([
        (E5, 200), (B4, 100), (C5, 100), (D5, 200),
        (C5, 100), (B4, 100), (A4, 200), (A4, 100),
        (C5, 100), (E5, 200), (D5, 100), (C5, 100),
        (B4, 300),
    ])


def game_pacman():
    # Pac-Man start-of-game fanfare — fast, arcadey, ascending.
    play([
        (B4, 90), (B5, 90), (FS5, 90), (DS5, 90),
        (B5, 60), (FS5, 120), (DS5, 200),
        (C5, 90), (C6, 90), (G5, 90), (E5, 90),
        (C6, 60), (G5, 120), (E5, 200),
    ])


def game_sonic_ring():
    # Sonic ring pickup: two very short, very high chirps a fifth apart.
    play([(B6, 60), (FS6, 100)])


def game_pokemon_caught():
    # "Gotcha!" — the four-note ditty after a successful catch.
    play([(D5, 120), (E5, 120), (FS5, 120), (B5, 320)])


# Cartoons --------------------------------------------------------------------

def cartoon_looney_thats_all_folks():
    # Closing fanfare. Original is a chord at the end; we land on a single note.
    play([
        (G4, 140), (C5, 140), (E5, 140), (G5, 140),
        (E5, 100), (C5, 100), (G4, 100),
        (G4, 80), (A4, 80), (B4, 80), (C5, 400),
    ])


def cartoon_pink_panther():
    # Sneaky opening riff — chromatic creep up to the famous accent.
    play([
        (DS4, 140), (E4, 140), (0, 80),
        (FS4, 140), (G4, 140), (0, 80),
        (DS4, 100), (E4, 100), (FS4, 100), (G4, 100),
        (C5, 100), (B4, 100), (E4, 100), (G4, 100), (B4, 300),
    ])


def cartoon_scooby_doo():
    # "Scooby Dooby Doo, where are you?" — first phrase, sing-songy.
    play([
        (G4, 200), (E4, 150), (G4, 150), (A4, 200),
        (G4, 200), (E4, 200), (D4, 400),
    ])


def cartoon_mickey_mouse_march():
    # "Who's the leader of the club..." — first bar, classic Disney.
    play([
        (C5, 150), (G4, 150), (G4, 100), (A4, 100),
        (G4, 200), (0, 80), (B4, 200), (C5, 400),
    ])


# TV --------------------------------------------------------------------------

def tv_simpsons():
    # "The Simp-sons!" — that famously off-kilter cadence.
    play([
        (C5, 180), (E5, 180), (FS5, 180), (0, 80),
        (A5, 240), (G5, 180), (E5, 180), (C5, 180),
        (0, 80), (A4, 180), (FS4, 180), (FS4, 180),
        (FS4, 180), (G4, 400),
    ])


def tv_inspector_gadget():
    # Sneaky minor-key descent — the "go go gadget" theme's opening hook.
    play([
        (E4, 130), (G4, 130), (A4, 130), (B4, 130),
        (E5, 130), (D5, 130), (B4, 130), (G4, 130),
        (A4, 260),
    ])


def tv_addams_family():
    # "Dun-dun-dun-DUN (snap snap)" — we omit the snaps and just land the four.
    play([
        (FS4, 180), (A4, 180), (D5, 180), (A4, 180),
        (FS4, 280),
    ])


# Movies ----------------------------------------------------------------------

def movie_star_wars_main():
    # Opening fanfare — the four-note "STAR WARS" call.
    play([
        (G4, 130), (G4, 130), (G4, 130),
        (C5, 500),
        (G5, 500),
        (F5, 100), (E5, 100), (D5, 100), (C6, 500),
    ])


def movie_imperial_march():
    # Vader's theme. Real bass is ~A2/F2; transposed up so the piezo can sing it.
    play([
        (A4, 250), (A4, 250), (A4, 250),
        (F4, 180), (0, 30), (C5, 90),
        (A4, 250),
        (F4, 180), (0, 30), (C5, 90),
        (A4, 500),
    ])


def movie_indiana_jones():
    # The raiders march, opening four-note motif.
    play([
        (E4, 120), (F4, 60), (G4, 240), (0, 80),
        (C5, 500),
        (D4, 120), (E4, 60), (F4, 500),
    ])


def movie_jaws():
    # Two-note "shark approaching" loop, speeding up. Transposed up two octaves
    # from the original E2/F2 so the piezo actually plays it — true bass would
    # be inaudible here.
    play([
        (E4, 400), (F4, 400),
        (E4, 300), (F4, 300),
        (E4, 200), (F4, 200),
        (E4, 120), (F4, 120),
        (E4, 80), (F4, 80), (E4, 80), (F4, 80),
    ])


def movie_close_encounters():
    # The famous five-note "hello, aliens" phrase.
    play([
        (D5, 280), (E5, 280), (C5, 280),
        (C4, 280), (G4, 500),
    ])


def movie_jurassic_park():
    # Main theme's lullaby phrase — slow, hopeful, sweeping.
    play([
        (B4, 350), (FS5, 700), (E5, 350),
        (FS5, 700), (DS5, 350), (FS5, 350),
        (B4, 700),
    ])


def movie_harry_potter():
    # Hedwig's Theme, opening line. Lilting, three-beat feel.
    play([
        (B4, 200), (E5, 300), (G5, 100), (FS5, 200),
        (E5, 400), (B5, 200),
        (A5, 600), (FS5, 600),
        (E5, 300), (G5, 100), (FS5, 200),
        (DS5, 400), (F5, 200),
        (B4, 800),
    ])


def movie_mission_impossible():
    # The 5/4 spy-march pulse — two beats, two beats, "dun-DUN".
    play([
        (G4, 120), (0, 60), (G4, 120), (0, 60),
        (AS4, 120), (C5, 120), (0, 60),
        (G4, 120), (0, 60), (G4, 120), (0, 60),
        (F4, 120), (FS4, 120), (0, 60),
        (G4, 120), (0, 60), (G4, 120), (0, 60),
        (AS4, 120), (C5, 120), (0, 60),
        (G4, 120), (0, 60), (G4, 120), (0, 60),
        (F4, 120), (FS4, 120),
    ])


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
    ("game:    mario theme",       game_mario_theme),
    ("game:    mario 1-up",        game_mario_1up),
    ("game:    mario power-up",    game_mario_powerup),
    ("game:    zelda secret",      game_zelda_secret),
    ("game:    tetris",            game_tetris),
    ("game:    pac-man",           game_pacman),
    ("game:    sonic ring",        game_sonic_ring),
    ("game:    pokemon caught",    game_pokemon_caught),
    ("cartoon: looney tunes end",  cartoon_looney_thats_all_folks),
    ("cartoon: pink panther",      cartoon_pink_panther),
    ("cartoon: scooby doo",        cartoon_scooby_doo),
    ("cartoon: mickey mouse",      cartoon_mickey_mouse_march),
    ("tv:      simpsons",          tv_simpsons),
    ("tv:      inspector gadget",  tv_inspector_gadget),
    ("tv:      addams family",     tv_addams_family),
    ("movie:   star wars main",    movie_star_wars_main),
    ("movie:   imperial march",    movie_imperial_march),
    ("movie:   indiana jones",     movie_indiana_jones),
    ("movie:   jaws",              movie_jaws),
    ("movie:   close encounters",  movie_close_encounters),
    ("movie:   jurassic park",     movie_jurassic_park),
    ("movie:   harry potter",      movie_harry_potter),
    ("movie:   mission impossible", movie_mission_impossible),
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

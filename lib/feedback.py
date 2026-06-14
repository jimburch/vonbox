# Local feedback renderer for the NFC Movie Box: the LED ring + buzzer.
#
# What it proves / does: turns the abstract session "state" (driven by Home
# Assistant over vonbox/state) into the box's only output the kid sees and
# hears. One object owns both the WS2812 ring and the KY-006 piezo so the two
# stay in sync and there's a single place that knows what each state looks and
# sounds like.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   Ring DIN -> GP28 (R7/pin34), PWR(5V) -> VSYS (R2/pin39), GND -> GND (R3)
#   Buzzer S -> GP22 (R12/pin29), - (GND) -> GND (R13/pin28), middle pin unused
#
# Designed to be uploaded once to the Pico's flash under /lib/feedback.py;
# orchestrator/test scripts then `from feedback import Feedback`.
#
# Concurrency model: this class NEVER blocks the main loop for animation. The
# caller pumps tick() every loop iteration; tick() advances at most one frame
# and returns immediately, so NFC polling and MQTT check_msg() stay responsive.
# The ONLY blocking allowed is the short buzzer cues (<=300ms), because a tone
# is inherently a wall-clock event and Von's tap feedback wants to feel instant.
#
# Animation ideas are lifted from test/bench/led_ring_test.py (dim/wheel/chase/breathe)
# and cue ideas from test/bench/buzzer_test.py (tone()/play(), note frequencies).
#
# WS2812 detail: the neopixel driver handles GRB ordering internally, so every
# color here is plain (R, G, B). The driver is frozen into the official
# RPI_PICO2_W build — no install step needed.

from machine import Pin, PWM
from neopixel import NeoPixel
import time

# --- hardware constants -------------------------------------------------------

LED_PIN_DEFAULT    = 28   # GP28, the ring's DIN (R7/pin34)
NUM_PIXELS_DEFAULT = 24
BUZZER_PIN_DEFAULT = 22   # GP22, the passive piezo signal (R12/pin29)

# Brightness is a hard safety cap, not a preference. All-white at full
# brightness is ~60mA/pixel -> ~1.4A for 24 pixels, more than VSYS/USB can
# supply. At 0.25 the worst case (all white) is ~360mA, well within budget.
# Every color is scaled through dim() before it hits the strip.
BRIGHTNESS = 0.25

# Duty sets piezo volume/timbre, not pitch. 50% (32768/65535) is the standard
# square drive and about as loud as the piezo gets. Pitch is the PWM frequency.
VOLUME_DUTY = 32768

# --- named colors (full-intensity RGB; dim() applies the cap) -----------------

WARM_WHITE = (255, 160, 60)   # soft incandescent-ish white; the "resting" color
GREEN      = (0, 255, 0)      # movie confirmed playing
BLUE       = (0, 0, 255)      # loading / waiting on playback
AMBER      = (255, 120, 0)    # paused
RED        = (255, 0, 0)      # error
PURPLE     = (160, 0, 255)    # broker-unreachable diagnostic (distinct from RED)
OFF        = (0, 0, 0)


# --- buzzer cues (named so they're trivial to swap when the user picks finals)-
#
# Each cue is a list of (freq_hz, ms); freq 0 is a rest. Frequencies match the
# note table in test/bench/buzzer_test.py. Four of these mark the milestones the
# box announces out loud, laddered lowest-and-calmest -> highest-and-brightest:
#   boot           CHIME_BOOT            "powered on"      calm rising fifth
#   tap accepted   CHIME_TAP             "got it"          quick bright two-note
#   playing        CHIME_PLAYING         "movie starting!" bright rising triad
#   error          TONE_ERROR_DESCENDING "nope"            low descending wah-wah
# Pitch carries the meaning: the piezo rings louder near its ~2-4kHz resonance,
# so "good" cues climb and "bad" cues fall. These are sensible picks from the
# buzzer_test.py menu; swap freely right here once they're judged by ear.
A4, E5 = 440, 659
A5     = 880
B5, C6, E6, G6 = 988, 1047, 1319, 1568
A3 = 220
F3_DULL = 175  # ~F3, a dull low landing

CHIME_BOOT            = [(A4, 140), (E5, 240)]             # calm rising fifth, "powered on" (=380ms; boot is a one-shot, blocking is fine)
CHIME_TAP             = [(B5, 80), (E6, 200)]              # rising two-note "got it" (=280ms, under the <=300ms tap budget)
CHIME_PLAYING         = [(C6, 70), (E6, 70), (G6, 160)]    # bright rising triad landing high, "movie starting!" (=300ms)
NOTE_ALREADY_PLAYING  = [(A5, 150)]                        # single soft mid-note
TONE_ERROR_DESCENDING = [(A3, 150), (0, 20), (F3_DULL, 200)]  # soft low "wah-wah" (=370ms, kept brief so the cue can't stall the loop)


# --- the session state vocabulary ---------------------------------------------
#
# SUSTAINED_STATES are the states HA can park the box in indefinitely; their
# render holds until the next state arrives. 'playing' is deliberately NOT one
# of them: the box is tap-and-go, not a presence light, so a movie start is a
# brief green confirmation flash that fades back to the quiet idle rest (handled
# like a transient cue in set_state). A held green ring would read as "busy,
# won't take another tap". The other transients (error, already_playing) and the
# local tap sparkle likewise always revert to a sustained state.
SUSTAINED_STATES = ("idle", "loading", "paused", "standby")
TRANSIENT_STATES = ("error", "already_playing")


class Feedback:
    """LED + buzzer renderer. Pump tick() every main-loop iteration."""

    # Frame intervals (ms) per sustained state. Larger interval = slower
    # animation. idle is a constant dark fill now (the quiet rest), so its
    # interval just sets how often that no-op fill refreshes.
    _IDLE_INTERVAL_MS    = 40
    _LOADING_INTERVAL_MS = 40
    _PAUSED_INTERVAL_MS  = 45
    _STANDBY_INTERVAL_MS = 90   # very slow breathing
    _TRANSIENT_INTERVAL_MS = 45

    # Breathing periods in frames (one full dark->bright->dark triangle).
    _BREATHE_FRAMES_IDLE    = 60
    _BREATHE_FRAMES_PAUSED  = 60
    _BREATHE_FRAMES_STANDBY = 80

    # Per-state breathing peak level as a fraction of BRIGHTNESS (the spec's
    # "~10%", "~15%", "~5%" relative to the cap).
    _LEVEL_IDLE    = 0.10 / BRIGHTNESS
    _LEVEL_LOADING = 0.30 / BRIGHTNESS
    _LEVEL_PLAYING = 0.20 / BRIGHTNESS
    _LEVEL_PAUSED  = 0.15 / BRIGHTNESS
    _LEVEL_STANDBY = 0.05 / BRIGHTNESS
    _LEVEL_ERROR   = 0.40 / BRIGHTNESS
    _LEVEL_SPARKLE = 0.25 / BRIGHTNESS

    # Transient durations in frames (all counted at _TRANSIENT_INTERVAL_MS).
    _ERROR_FLASHES        = 3
    _ERROR_FRAMES_PER_FLASH = 8     # on-half then off-half within each flash
    _ERROR_TOTAL_FRAMES   = _ERROR_FLASHES * _ERROR_FRAMES_PER_FLASH
    _PULSE_FRAMES         = 24      # one soft pulse over the current color
    _SPARKLE_FRAMES       = 14      # quick green sparkle then settle
    # 'playing' confirmation: solid green hold, then fade to dark, then revert to
    # the quiet idle rest. ~2.0 s hold + ~1.25 s fade at 45 ms/frame.
    _PLAYING_HOLD_FRAMES  = 44
    _PLAYING_FADE_FRAMES  = 28

    # Headless boot/connectivity diagnostics (see the diagnostics section
    # below). Frame periods assume main.py drives these at ~25 fps from its
    # feed-the-watchdog connect wait, NOT via tick().
    _DIAG_BOOT_LEVEL     = 0.12 / BRIGHTNESS   # steady dim "alive, in boot window"
    _DIAG_CONNECT_LEVEL  = 0.30 / BRIGHTNESS
    _DIAG_WIFI_FRAMES    = 50       # slow blue breathe period (associating)
    _DIAG_BLINK_PERIOD   = 24       # amber double-blink cycle (Wi-Fi unreachable)
    _DIAG_BROKER_FRAMES  = 36       # purple breathe period (broker unreachable)
    _DIAG_BROKER_LEVEL   = 0.35 / BRIGHTNESS

    def __init__(self, led_pin=LED_PIN_DEFAULT, num_pixels=NUM_PIXELS_DEFAULT,
                 buzzer_pin=BUZZER_PIN_DEFAULT):
        self.num_pixels = num_pixels
        self._ring = NeoPixel(Pin(led_pin), num_pixels)
        self._buzzer = PWM(Pin(buzzer_pin))
        self._buzzer.duty_u16(0)

        # current_state is the active SUSTAINED state. Transients never
        # overwrite it; they remember it in _revert_to and restore it.
        self.current_state = "idle"
        self._transient = None      # name of the running transient, or None
        self._revert_to = "idle"    # sustained state to restore after transient

        self._frame = 0
        self._last_frame = time.ticks_ms()
        self._diag_frame = 0   # independent counter for the diagnostics below

    # --- public API -----------------------------------------------------------

    def boot(self):
        """One-shot power-on flourish: a calm rising cue + a single warm-white
        comet lap around the ring, ending dark.

        Call this ONCE at startup, BEFORE the tick() loop and before the first
        set_state('idle'). Unlike every other cue this is allowed to block for
        ~1s on purpose — it runs before the main loop exists, so there is nothing
        to keep responsive yet. It deliberately does NOT leave a sustained state;
        the caller's set_state('idle') takes over immediately after.
        """
        self._play(CHIME_BOOT)
        # A single comet sweep (bright head, fading tail) so the ring visibly
        # "wakes up". Head runs 0 -> last pixel and trails off the end; no wrap,
        # so it reads as one clean pass rather than a spin.
        tail = 6
        for step in range(self.num_pixels + tail):
            for i in range(self.num_pixels):
                self._ring[i] = OFF
            for t in range(tail):
                idx = step - t
                if idx < 0 or idx >= self.num_pixels:
                    continue
                falloff = (tail - t) / tail
                self._ring[idx] = self._scale(WARM_WHITE, 0.9 * falloff)
            self._ring.write()
            time.sleep_ms(28)
        for i in range(self.num_pixels):
            self._ring[i] = OFF
        self._ring.write()

    def tap_accepted(self):
        """Fresh-tap local feedback, fired by the Pico BEFORE any MQTT round-trip.

        Rising chime now (brief blocking is fine — we want it instant), then a
        quick green sparkle transient that auto-settles back to the prior
        sustained state via tick(). The chime is the only blocking call here.
        """
        self._play(CHIME_TAP)
        self._enter_transient("tap_accepted")

    def set_state(self, state, title=None, reason=None):
        """Change the sustained visual state, or fire a transient cue.

        title/reason are accepted for API symmetry (HA passes them in the
        vonbox/state payload); this renderer only acts on `reason` indirectly
        via the error cue. Unknown states are warned-and-ignored, never crash.
        """
        if state in TRANSIENT_STATES:
            # Transients play their cue once on entry, animate, then revert to
            # whatever sustained state we're currently in.
            if state == "error":
                self._play(TONE_ERROR_DESCENDING)
            elif state == "already_playing":
                self._play(NOTE_ALREADY_PLAYING)
            self._enter_transient(state)
            return

        if state == "playing":
            # Movie-started confirmation. NOT a held state: the box is tap-and-go,
            # so green is a brief "got it — it's playing!" that fades back to the
            # quiet (dark) idle rest, leaving the ring obviously ready for the next
            # tap. A sustained green ring reads as "busy, won't take another tap".
            # Rendered like a transient: hold green -> fade out -> revert to idle.
            # Always chimes on a genuine 'playing' message (retain is OFF on the HA
            # side, so the box only sees this once per real play — no reconnect
            # re-trumpet to guard against); the _transient check only stops a
            # duplicate 'playing' from re-firing the jingle mid-flash.
            if self._transient != "playing":
                self._play(CHIME_PLAYING)
            self.current_state = "idle"        # the resting state we fade into
            self._enter_transient("playing")   # _revert_to <- "idle"
            return

        if state not in SUSTAINED_STATES:
            print("feedback: unknown state %r, ignoring" % (state,))
            return

        # Entering a sustained state cancels any running transient and resets
        # the frame baseline so the new animation starts clean.
        self.current_state = state
        self._revert_to = state
        self._transient = None
        self._frame = 0
        self._last_frame = time.ticks_ms()

    def tick(self):
        """Advance AT MOST ONE animation frame. Non-blocking; call every loop.

        Self-rate-limited via ticks_ms/ticks_diff against the active state's
        frame interval. Renders one frame into the ring buffer and writes once.
        When a transient finishes, reverts to the prior sustained state.
        """
        now = time.ticks_ms()
        interval = self._current_interval_ms()
        if time.ticks_diff(now, self._last_frame) < interval:
            return  # not time for the next frame yet — stay non-blocking

        self._last_frame = now
        self._render_frame()
        self._ring.write()
        self._frame += 1

        # Detect "transient finished" AFTER advancing, so the final frame of the
        # transient is actually shown before we revert.
        if self._transient is not None and self._frame >= self._transient_len():
            self._transient = None
            self._frame = 0
            # current_state already holds the sustained state; just resume it.

    def off(self):
        """Clear the ring and silence the buzzer (cleanup on exit).

        We set the buzzer duty to 0 rather than deinit()-ing the PWM: a deinit
        without a paired re-init would leave a reused Feedback instance mute.
        Silencing is enough to make the box quiet and dark.
        """
        for i in range(self.num_pixels):
            self._ring[i] = OFF
        self._ring.write()
        self._buzzer.duty_u16(0)

    # --- headless boot / connectivity diagnostics ------------------------------
    #
    # The ring is the box's ONLY console when no laptop is attached, so the
    # pre-network boot/connectivity status has to be legible across the room.
    # These methods deliberately live OUTSIDE the session state machine: they
    # are not SUSTAINED_STATES/TRANSIENT_STATES, never touch current_state, and
    # draw their own frame (they don't go through tick()). main.py drives them
    # one frame per call from its connect loops, at ~25 fps inside the wait that
    # also feeds the watchdog. They're silent by design — a box beeping while the
    # router reboots next to the TV would be obnoxious; the dad reads the ring.
    # The three "something's wrong" looks are kept visually distinct:
    #   net_error('wifi')   -> AMBER double-blink   (no link to the router)
    #   net_error('broker') -> PURPLE slow breathe  (router ok, broker down)
    #   session 'error'     -> RED 3-flash          (the state machine, elsewhere)

    def booting(self):
        """Dim steady warm-white fill: 'powered, alive, in the boot-guard window'."""
        self._frame_fill(WARM_WHITE, self._DIAG_BOOT_LEVEL)
        self._ring.write()
        self._diag_frame += 1

    def connecting_wifi(self):
        """Slow blue breathe: 'associating with Wi-Fi'."""
        self._diag_breathe(BLUE, self._DIAG_WIFI_FRAMES, self._DIAG_CONNECT_LEVEL)
        self._ring.write()
        self._diag_frame += 1

    def connecting_mqtt(self):
        """Blue dot chasing the ring: 'reaching the broker' (distinct motion from Wi-Fi)."""
        head = self._diag_frame % self.num_pixels
        on = self._scale(BLUE, self._DIAG_CONNECT_LEVEL)
        for i in range(self.num_pixels):
            self._ring[i] = on if i == head else OFF
        self._ring.write()
        self._diag_frame += 1

    def net_error(self, leg):
        """Sustained 'can't connect' diagnostic. leg='wifi' -> amber double-blink;
        anything else ('broker') -> purple slow breathe. Both distinct from each
        other and from the red session-error flash."""
        if leg == "wifi":
            self._diag_double_blink(AMBER)
        else:
            self._diag_breathe(PURPLE, self._DIAG_BROKER_FRAMES, self._DIAG_BROKER_LEVEL)
        self._ring.write()
        self._diag_frame += 1

    def _diag_breathe(self, color, period_frames, peak_level):
        # Triangle 0->peak->0 over period_frames, off the independent _diag_frame
        # counter so it never disturbs the session animation's _frame.
        half = period_frames // 2
        phase = self._diag_frame % period_frames
        tri = phase if phase <= half else (period_frames - phase)
        level = (tri / half) * peak_level if half else 0.0
        self._frame_fill(color, level)

    def _diag_double_blink(self, color):
        # Two short blinks then a long gap, repeating: reads as "searching, no link".
        phase = self._diag_frame % self._DIAG_BLINK_PERIOD
        if phase < 3 or 5 <= phase < 8:
            self._frame_fill(color, self._DIAG_CONNECT_LEVEL)
        else:
            self._frame_fill(OFF, 1.0)

    # --- internal: buzzer ------------------------------------------------------

    def _play(self, notes):
        # notes: list of (freq_hz, ms). freq 0 is a rest. Brief blocking is OK
        # here (cues are <=300ms of real tone) — see the class header.
        for freq, ms in notes:
            if freq == 0:
                self._buzzer.duty_u16(0)
                time.sleep_ms(ms)
            else:
                self._buzzer.freq(freq)
                self._buzzer.duty_u16(VOLUME_DUTY)
                time.sleep_ms(ms)
        self._buzzer.duty_u16(0)

    # --- internal: state / transient bookkeeping -------------------------------

    def _enter_transient(self, name):
        # _revert_to stays whatever sustained state we were in; current_state is
        # NOT changed (the contract: current_state reflects the SUSTAINED state).
        self._revert_to = self.current_state
        self._transient = name
        self._frame = 0
        self._last_frame = time.ticks_ms()

    def _transient_len(self):
        if self._transient == "error":
            return self._ERROR_TOTAL_FRAMES
        if self._transient == "already_playing":
            return self._PULSE_FRAMES
        if self._transient == "tap_accepted":
            return self._SPARKLE_FRAMES
        if self._transient == "playing":
            return self._PLAYING_HOLD_FRAMES + self._PLAYING_FADE_FRAMES
        return 0

    def _current_interval_ms(self):
        if self._transient is not None:
            return self._TRANSIENT_INTERVAL_MS
        s = self.current_state
        if s == "idle":
            return self._IDLE_INTERVAL_MS
        if s == "loading":
            return self._LOADING_INTERVAL_MS
        if s == "paused":
            return self._PAUSED_INTERVAL_MS
        if s == "standby":
            return self._STANDBY_INTERVAL_MS
        return self._IDLE_INTERVAL_MS

    # --- internal: rendering ---------------------------------------------------

    def _render_frame(self):
        # Dispatch one frame's worth of pixels into the ring buffer. The caller
        # (tick) does the single ring.write(). Transients take priority so their
        # cue is visible over whatever sustained state lurks underneath.
        if self._transient == "error":
            self._frame_error()
        elif self._transient == "already_playing":
            self._frame_pulse(self._revert_to)
        elif self._transient == "tap_accepted":
            self._frame_sparkle()
        elif self._transient == "playing":
            self._frame_play_confirm()
        else:
            s = self.current_state
            if s == "idle":
                # Quiet, dark rest: the box sits dark when idle so that lighting
                # up == "I took your tap". (No constant breathe — idle pref.)
                self._frame_fill(OFF, 1.0)
            elif s == "loading":
                self._frame_chase(BLUE, self._LEVEL_LOADING)
            elif s == "paused":
                self._frame_breathe(AMBER, self._BREATHE_FRAMES_PAUSED,
                                    self._LEVEL_PAUSED)
            elif s == "standby":
                self._frame_breathe(WARM_WHITE, self._BREATHE_FRAMES_STANDBY,
                                    self._LEVEL_STANDBY)

    def _frame_fill(self, color, level=1.0):
        c = self._scale(color, level)
        for i in range(self.num_pixels):
            self._ring[i] = c

    def _frame_breathe(self, color, period_frames, peak_level):
        # Triangle wave from the integer frame counter: 0 -> 1 -> 0 over
        # period_frames. Integer math, so no float drift over long runtimes.
        half = period_frames // 2
        phase = self._frame % period_frames
        tri = phase if phase <= half else (period_frames - phase)
        level = (tri / half) * peak_level if half else 0.0
        self._frame_fill(color, level)

    def _frame_chase(self, color, level):
        # A single bright LED running around the ring. One pixel per frame.
        head = self._frame % self.num_pixels
        on = self._scale(color, level)
        for i in range(self.num_pixels):
            self._ring[i] = on if i == head else OFF

    def _frame_sparkle(self):
        # Quick GREEN sparkle from a deterministic stride (no RNG), settling to
        # a dim green hold on the last frame so the tap visibly "lands".
        for i in range(self.num_pixels):
            self._ring[i] = OFF
        if self._frame >= self._SPARKLE_FRAMES - 1:
            # Settle: dim green fill — the box now reads "accepted, working".
            self._frame_fill(GREEN, 0.4 * self._LEVEL_SPARKLE)
            return
        # Light a small moving cluster; stride 7 spreads them around the ring.
        base = (self._frame * 7) % self.num_pixels
        on = self._scale(GREEN, self._LEVEL_SPARKLE)
        for k in range(3):
            self._ring[(base + k * 7) % self.num_pixels] = on

    def _frame_play_confirm(self):
        # Movie-started confirmation: hold solid green, then fade it down to dark.
        # tick() reverts to the (dark) idle rest once the fade completes. Green is
        # a flash, not a hold, on purpose — see set_state('playing').
        hold = self._PLAYING_HOLD_FRAMES
        fade = self._PLAYING_FADE_FRAMES
        if self._frame < hold:
            self._frame_fill(GREEN, self._LEVEL_PLAYING)
        else:
            remaining = (hold + fade - self._frame) / fade
            if remaining < 0.0:
                remaining = 0.0
            self._frame_fill(GREEN, self._LEVEL_PLAYING * remaining)

    def _frame_pulse(self, base_state):
        # One soft brightness pulse (triangle 0->1->0) over the color of the
        # sustained state we'll revert to, so the re-tap reads as "yes, that one
        # — still playing" without changing what's on screen.
        color = self._color_for_state(base_state)
        half = self._PULSE_FRAMES // 2
        tri = self._frame if self._frame <= half else (self._PULSE_FRAMES - self._frame)
        # Aim for a bump above the baseline level, but clamp to 1.0 (== the cap)
        # so the pulse peaks cleanly AT the brightness cap instead of overshooting
        # past it and clipping flat — keeps it reading as a soft pulse.
        peak = min(self._level_for_state(base_state) * 1.5, 1.0)
        level = (tri / half) * peak if half else 0.0
        self._frame_fill(color, level)

    def _frame_error(self):
        # 3 RED flashes: on for the first half of each flash window, off for the
        # second half. Reverts (handled in tick) once all flashes complete.
        within = self._frame % self._ERROR_FRAMES_PER_FLASH
        if within < self._ERROR_FRAMES_PER_FLASH // 2:
            self._frame_fill(RED, self._LEVEL_ERROR)
        else:
            self._frame_fill(OFF, 1.0)

    # --- internal: color helpers -----------------------------------------------

    def _scale(self, color, level):
        # Apply the per-state level AND the hard BRIGHTNESS cap in one step.
        # `level` is already expressed relative to BRIGHTNESS (so a level of
        # 1.0 means "the full cap"), hence the single multiply by BRIGHTNESS.
        factor = level * BRIGHTNESS
        if factor < 0.0:
            factor = 0.0
        elif factor > BRIGHTNESS:
            factor = BRIGHTNESS  # never exceed the current-safety cap
        return (int(color[0] * factor),
                int(color[1] * factor),
                int(color[2] * factor))

    def _color_for_state(self, state):
        if state == "playing":
            return GREEN
        if state == "loading":
            return BLUE
        if state == "paused":
            return AMBER
        return WARM_WHITE  # idle, standby, and any fallback

    def _level_for_state(self, state):
        if state == "playing":
            return self._LEVEL_PLAYING
        if state == "loading":
            return self._LEVEL_LOADING
        if state == "paused":
            return self._LEVEL_PAUSED
        if state == "standby":
            return self._LEVEL_STANDBY
        return self._LEVEL_IDLE

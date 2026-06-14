# NFC Movie Box — production orchestrator. Auto-runs on boot from flash.
#
# This is test/offline-harness/full_loop_test.py's proven tap -> feedback ->
# MQTT -> state -> ring/buzzer loop, PROMOTED to a flash-resident main.py and
# hardened for unattended life by the TV. The loop body is intentionally the
# same one we validated against the mock HA; what's new here is everything that
# lets the box boot, recover, and report status with no laptop attached:
#
#   1. A dev-escape BOOT-GUARD WINDOW (§2 of docs/production-deployment.md):
#      main.py always boots toward production, but holds a short quiet window at
#      the very start where a connected MicroPico (which sends Ctrl-C on connect/
#      Run/Stop) breaks in and drops to the REPL = DEV MODE. A wall charger has
#      nothing to interrupt it, so it falls through to production. No USB sensing.
#
#   2. A hardware WATCHDOG, armed ONLY AFTER the window closes (the RP2350 WDT
#      cannot be stopped once started — arming it before the window would reboot
#      us every few seconds while we tried to use the dev REPL). Fed once per
#      main-loop iteration and inside every connect/backoff wait.
#
#   3. Connect + reconnect promoted to UNBOUNDED capped backoff with headless
#      ring diagnostics, so a box that powers on while the router is still
#      booting (whole-house outage) just waits patiently and comes up on its own.
#
#   4. A top-level catch that, on any unhandled exception, flashes red and
#      machine.reset()s into a clean boot — in production "fall through to the
#      REPL" is the same as "dead", because nobody is watching the serial console.
#
# DEV MODE (how to get the REPL back): plug into the laptop and hit MicroPico
# "Stop execution" within the boot window (the first ~2.5 s after a reset/replug).
# If you miss it: once the watchdog is armed, a Ctrl-C gives you a REPL but the
# WDT reboots in <=8 s, dropping you back into a fresh window — so just break in
# during that window. "Run current file on Pico" runs the editor file, not
# main.py, so bench/harness scripts work exactly as before.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   PN532 NFC: SDA->GP4 (L6)  SCL->GP5 (L7)  3V3->3V3(OUT) (R5)  GND->GND (R3)
#   LED ring : DIN->GP28 (R7) PWR->VSYS (R2) GND->GND (R3, shared)
#   Buzzer   : S->GP22 (R12)  -(GND)->GND (R13)
#
# Flash layout this expects (MicroPico "Upload project to Pico"):
#   /main.py, /secrets.py (PRODUCTION values — home SSID + Synology broker),
#   /lib/pn532.py, /lib/feedback.py, /lib/umqtt/simple.mpy
#   (umqtt is NOT frozen into the build — re-run test/bench/install_umqtt.py
#    after any reflash; see CLAUDE.md.)

import json
import network
import time

import machine
from machine import Pin, I2C, WDT

from umqtt.simple import MQTTClient

from pn532 import PN532
from feedback import Feedback
from secrets import (
    WIFI_SSID, WIFI_PASSWORD,
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
)

CLIENT_ID = b"vonbox-pico"
TOPIC_TAPPED = b"vonbox/nfc/tapped"
TOPIC_STATE = b"vonbox/state"

# --- timing (identical to full_loop_test.py — the proven loop cadence) --------
NFC_POLL_INTERVAL_MS = 100   # ~10Hz PN532 poll
LOOP_TICK_MS = 30            # main loop runs faster so check_msg/tick stay snappy
ABSENCE_MS = 2000            # a UID must be gone this long before it can re-fire
WIFI_CONNECT_TIMEOUT_MS = 15_000
OPTIMISTIC_LOADING_GRACE_MS = 400  # let HA answer before we flip the ring to loading
MQTT_KEEPALIVE_S = 60
MQTT_PING_INTERVAL_MS = (MQTT_KEEPALIVE_S // 2) * 1000  # umqtt.simple won't ping itself

# LED ring + buzzer pins (match feedback.py defaults; passed explicitly so this
# file documents the hardware map).
LED_PIN = 28
NUM_PIXELS = 24
BUZZER_PIN = 22

# --- production hardening ------------------------------------------------------
BOOT_GUARD_MS = 2500           # dev-escape window length, BEFORE the watchdog arms
WDT_TIMEOUT_MS = 8000          # ~RP2 max (8.3 s); longest legit block is fb.boot() ~1.2 s
DIAG_FRAME_MS = 40             # connect-wait animation + watchdog-feed cadence (~25 fps)
NET_ERROR_AFTER_ATTEMPTS = 3   # escalate connecting_* -> net_error after this many fails
BACKOFF_MS = (1000, 2000, 5000, 10000)   # capped backoff on reconnect attempts
ERROR_RESET_HOLD_MS = 1500     # hold the red flash this long before machine.reset()


def _backoff_ms(attempt):
    # attempt is 1-based; clamp to the last (longest) bucket.
    return BACKOFF_MS[min(attempt - 1, len(BACKOFF_MS) - 1)]


def _wait(ms, render, wdt):
    # Sleep `ms` while keeping the ring animating and the watchdog fed, so a long
    # backoff never trips the WDT and the box visibly stays alive. `render` draws
    # one diagnostic frame per tick; `wdt` may be None (pre-arm) — feed if present.
    deadline = time.ticks_add(time.ticks_ms(), ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        render()
        if wdt is not None:
            wdt.feed()
        time.sleep_ms(DIAG_FRAME_MS)


def boot_guard_window(fb):
    # The dev-escape window. KeyboardInterrupt raised in here (MicroPico Stop)
    # propagates out to main(), which drops cleanly to the REPL with the watchdog
    # NEVER armed. Untouched, the window elapses and we commit to production.
    print("boot guard: {} ms — MicroPico 'Stop' now to drop to the dev REPL".format(BOOT_GUARD_MS))
    deadline = time.ticks_add(time.ticks_ms(), BOOT_GUARD_MS)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        fb.booting()
        time.sleep_ms(DIAG_FRAME_MS)
    print("boot guard elapsed — committing to production")


def connect_wifi_forever(fb, wdt):
    # Retry forever with backoff; feed the watchdog throughout (a single
    # association can take well past the WDT timeout). Show connecting_wifi while
    # we're hopeful, escalate to net_error('wifi') once it's clearly stuck.
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    attempt = 0
    while not wlan.isconnected():
        attempt += 1
        render = fb.connecting_wifi if attempt <= NET_ERROR_AFTER_ATTEMPTS \
            else (lambda: fb.net_error("wifi"))
        print("Wi-Fi attempt {} -> {}".format(attempt, WIFI_SSID))
        try:
            wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        except OSError as exc:
            print("wlan.connect raised:", exc)
        # Wait for association up to the per-attempt timeout, animating + feeding.
        deadline = time.ticks_add(time.ticks_ms(), WIFI_CONNECT_TIMEOUT_MS)
        while not wlan.isconnected() and time.ticks_diff(deadline, time.ticks_ms()) > 0:
            render()
            wdt.feed()
            time.sleep_ms(DIAG_FRAME_MS)
        if not wlan.isconnected():
            backoff = _backoff_ms(attempt)
            print("Wi-Fi not up, retrying in {} ms (status={})".format(backoff, wlan.status()))
            _wait(backoff, render, wdt)
    print("Wi-Fi ok, ip=", wlan.ifconfig()[0])
    return wlan


def connect_mqtt_forever(client, fb, wdt):
    # (Re)connect + re-subscribe the given client, retrying forever with backoff.
    # umqtt.simple.connect() opens a fresh socket each call, so reusing the same
    # client object across reconnects is fine. A bare reconnect without the
    # re-subscribe would leave the box deaf to vonbox/state — so they go together.
    #
    # Known edge: client.connect() is a blocking socket op with no timeout. If the
    # broker HOST is fully unreachable (e.g. Synology powered off) while Wi-Fi is
    # up, a connect() can block past the WDT timeout and reboot us — so a long
    # broker outage looks like an ~8 s reboot loop rather than a steady
    # net_error('broker'). It still self-heals the moment the broker returns. The
    # common case (broker container restart) refuses fast, so backoff + the
    # diagnostic escalation below work as intended. Future fix: pass
    # socket_timeout to MQTTClient once we confirm the on-flash umqtt supports it.
    attempt = 0
    while True:
        attempt += 1
        render = fb.connecting_mqtt if attempt <= NET_ERROR_AFTER_ATTEMPTS \
            else (lambda: fb.net_error("broker"))
        print("MQTT attempt {} -> {}@{}:{}".format(attempt, MQTT_USER, MQTT_HOST, MQTT_PORT))
        try:
            client.connect()
            client.subscribe(TOPIC_STATE)
            print("MQTT connected, subscribed to", TOPIC_STATE.decode())
            return
        except OSError as exc:
            print("MQTT connect failed (attempt {}): {}".format(attempt, exc))
            _wait(_backoff_ms(attempt), render, wdt)


def reconnect(client, fb, wdt):
    # Mid-session recovery: Wi-Fi first (MQTT can't return without it), then MQTT.
    wlan = network.WLAN(network.STA_IF)
    if not wlan.isconnected():
        connect_wifi_forever(fb, wdt)
    connect_mqtt_forever(client, fb, wdt)


def init_pn532():
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
    pn532 = PN532(i2c)
    pn532.init()
    print("PN532 ready")
    return pn532


def make_state_handler(fb, pending):
    # vonbox/state arrives TAGGED: {"state","uid","title","reason"}. A garbled
    # payload must never take down the loop, so everything is wrapped. ANY valid
    # reply means HA owns the visual state now, so we cancel the deferred
    # optimistic 'loading' (this is what stops a re-tap's 'already_playing' from
    # reverting to blue 'loading' and sitting there forever).
    def on_state(topic, msg):
        try:
            data = json.loads(msg)
            state = data.get("state")
            if not state:
                print("state msg missing 'state':", msg)
                return
            pending[0] = None
            fb.set_state(state, title=data.get("title"), reason=data.get("reason"))
            print("<- {}: {}".format(topic.decode() if isinstance(topic, bytes) else topic, msg))
        except (ValueError, AttributeError, KeyError) as exc:
            print("bad state payload ({}): {}".format(exc, msg))
    return on_state


def publish_tap(client, uid_hex, fb, wdt):
    payload = json.dumps({"uid": uid_hex})
    try:
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {}".format(TOPIC_TAPPED.decode(), payload))
    except OSError as exc:
        # Broker likely dropped us. Reconnect (forever) and retry once; the socket
        # is fresh on return, so this publish should land.
        print("publish failed ({}), reconnecting".format(exc))
        reconnect(client, fb, wdt)
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {} (after reconnect)".format(TOPIC_TAPPED.decode(), payload))


def run_production(fb, wdt):
    # Single-element holder for the deferred optimistic 'loading' deadline
    # (ticks_ms) or None — shared between the state handler (clears it when HA
    # answers) and the loop (fires the flip when it elapses).
    pending_loading = [None]
    mqtt = MQTTClient(
        client_id=CLIENT_ID, server=MQTT_HOST, port=MQTT_PORT,
        user=MQTT_USER, password=MQTT_PASSWORD, keepalive=MQTT_KEEPALIVE_S,
    )
    mqtt.set_callback(make_state_handler(fb, pending_loading))

    connect_wifi_forever(fb, wdt)
    connect_mqtt_forever(mqtt, fb, wdt)
    nfc = init_pn532()
    wdt.feed()

    fb.boot()              # ~1.2 s power-on flourish (< WDT timeout); feed either side
    wdt.feed()
    fb.set_state("idle")
    print("ready. tap a tag.")

    # Edge-trigger + 2 s-absence cooldown (verbatim from full_loop_test): a UID
    # fires only on the leading edge, and can't re-fire until absent ABSENCE_MS.
    current_uid = None
    last_seen_ms = 0
    last_nfc_poll_ms = time.ticks_add(time.ticks_ms(), -NFC_POLL_INTERVAL_MS)
    last_ping_ms = time.ticks_ms()

    try:
        while True:
            wdt.feed()                 # one feed per iteration (~30 ms << 8 s)
            loop_start = time.ticks_ms()

            # 1. Rate-limited NFC poll (~10Hz). lib/pn532 swallows stale
            #    half-frames internally, so None == no tag.
            if time.ticks_diff(loop_start, last_nfc_poll_ms) >= NFC_POLL_INTERVAL_MS:
                last_nfc_poll_ms = loop_start
                uid = nfc.read_passive_target(timeout_ms=150)

                if uid is not None:
                    if uid != current_uid:
                        uid_hex = uid.hex().upper()
                        print("TAPPED:", uid_hex)
                        # Local, instant feedback FIRST — before the broker round-trip.
                        fb.tap_accepted()
                        publish_tap(mqtt, uid_hex, fb, wdt)
                        # Optimistic 'loading' is ARMED, not fired: HA gets a short
                        # grace window to answer. If it replies with any sustained
                        # state (or a transient like 'already_playing' on a re-tap),
                        # the handler cancels this and we never flip to blue.
                        pending_loading[0] = time.ticks_add(
                            time.ticks_ms(), OPTIMISTIC_LOADING_GRACE_MS
                        )
                        current_uid = uid
                    last_seen_ms = time.ticks_ms()
                else:
                    if current_uid is not None:
                        if time.ticks_diff(time.ticks_ms(), last_seen_ms) >= ABSENCE_MS:
                            current_uid = None

            # 2. Drain incoming vonbox/state (non-blocking). A broker drop surfaces
            #    here as OSError; reconnect+re-subscribe (forever) and keep listening.
            try:
                mqtt.check_msg()
            except OSError as exc:
                print("check_msg failed ({}), reconnecting".format(exc))
                reconnect(mqtt, fb, wdt)

            # 3. Fire the deferred optimistic 'loading' if HA stayed quiet past the
            #    grace window. (The handler clears pending_loading the moment a
            #    vonbox/state reply arrives, so this only fires when HA is slow.)
            if pending_loading[0] is not None and \
                    time.ticks_diff(time.ticks_ms(), pending_loading[0]) >= 0:
                pending_loading[0] = None
                fb.set_state("loading")

            # 4. Keepalive: umqtt.simple won't ping on its own, so we do, at ~half
            #    the keepalive, to keep an idle box's socket from being dropped.
            if time.ticks_diff(time.ticks_ms(), last_ping_ms) >= MQTT_PING_INTERVAL_MS:
                last_ping_ms = time.ticks_ms()
                try:
                    mqtt.ping()
                except OSError as exc:
                    print("ping failed ({}), reconnecting".format(exc))
                    reconnect(mqtt, fb, wdt)

            # 5. Advance the ring/buzzer animation by at most one frame.
            fb.tick()

            elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
            if elapsed < LOOP_TICK_MS:
                time.sleep_ms(LOOP_TICK_MS - elapsed)
    finally:
        # Cleanup runs on the way out of the loop (KeyboardInterrupt at the REPL,
        # or an exception bubbling to main()'s top-level reset). The watchdog, if
        # armed, will reboot us shortly after — that's intended in production.
        fb.off()
        try:
            mqtt.disconnect()
        except Exception:
            pass
        print("ring cleared, buzzer silent, MQTT closed.")


def main():
    fb = Feedback(led_pin=LED_PIN, num_pixels=NUM_PIXELS, buzzer_pin=BUZZER_PIN)

    # Dev escape FIRST, before the watchdog exists. A KeyboardInterrupt here ends
    # the script -> REPL, with the WDT never armed (so the REPL is stable).
    try:
        boot_guard_window(fb)
    except KeyboardInterrupt:
        fb.off()
        print("dev mode: dropped to REPL (watchdog not armed).")
        return

    # Committed to production. Arm the watchdog (cannot be stopped once started).
    wdt = WDT(timeout=WDT_TIMEOUT_MS)
    try:
        run_production(fb, wdt)
    except Exception as exc:
        # No one is at the REPL in production: flash red, then reboot into a clean
        # boot. Every boot re-opens the dev window first, so even a deterministic
        # crash-loop stays escapable by plugging in and breaking in during it.
        print("FATAL:", exc)
        try:
            fb.set_state("error")
            _wait(ERROR_RESET_HOLD_MS, fb.tick, wdt)
        except Exception:
            pass
        machine.reset()


if __name__ == "__main__":
    main()

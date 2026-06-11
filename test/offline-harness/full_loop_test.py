# Pico LAYER 3: the complete tap -> feedback choreography against a mock broker.
#
# What this proves: a real NFC tap on the Pico drives the WHOLE local-feedback
# story end to end. On a fresh tap the box fires its own instant feedback
# (green sparkle + rising chime via fb.tap_accepted()) and publishes the UID to
# the broker immediately. It then ARMS an optimistic 'loading' that only fires
# if HA stays quiet past a short grace window — so HA's reply (loading ->
# playing on a known tag, the 'already_playing' transient on a re-tap, 'error'
# on an unknown tag) always wins and the ring never gets stranded on blue. The
# ring/buzzer follow the resulting sustained state. This is the first time NFC
# + WiFi + MQTT + LEDs + buzzer all run in one program.
#
# Wiring (see CLAUDE.md "Pico pin allocation"):
#   PN532 NFC: SDA->GP4 (L6)  SCL->GP5 (L7)  3V3->3V3(OUT) (R5)  GND->GND (R3)
#   LED ring : DIN->GP28 (R7) PWR->VSYS (R2) GND->GND (R3, shared)
#   Buzzer   : S->GP22 (R12)  -(GND)->GND (R13)
#
# Pre-flight:
#   - secrets.py on the Pico's flash, with MQTT_HOST/PORT/USER/PASSWORD pointed
#     at the LAPTOP broker (the iPhone-hotspot LAN address), NOT the Synology.
#     See docs/testing-away-from-home.md.
#   - umqtt.simple installed under /lib (test/bench/install_umqtt.py if missing).
#   - lib/pn532.py and lib/feedback.py uploaded to the Pico via MicroPico
#     "Upload project to Pico" — otherwise the imports below ImportError.
#   - The laptop running test/offline-harness/mosquitto.dev.conf broker + test/offline-harness/mock_ha.py.
#
# Run ephemerally via MicroPico "Run current file on Pico". Ctrl-C (MicroPico
# "Stop execution") clears the ring and silences the buzzer on the way out.

import json
import network
import time

from machine import Pin, I2C
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

# The PN532 poll stays ~10Hz (same as nfc_to_mqtt_test). The main loop runs
# faster (~30ms) so check_msg() and the animation tick stay responsive; the
# NFC read is rate-limited separately so we don't hammer the I2C bus.
NFC_POLL_INTERVAL_MS = 100   # ~10Hz
LOOP_TICK_MS = 30
ABSENCE_MS = 2000            # how long a UID must be gone before it can re-fire
WIFI_CONNECT_TIMEOUT_MS = 15_000

# Optimistic 'loading' is DEFERRED, not fired the instant we publish a tap. HA
# owns session knowledge (loading vs. playing vs. already_playing); the Pico
# does not track which tags are mid-session. So we wait a short grace window
# after publishing, and only flip the ring to 'loading' if HA hasn't already
# answered with a sustained state. This matters on a re-tap: HA replies with the
# 'already_playing' transient ONLY (it never re-sends 'playing'), so if we'd
# clobbered the state to 'loading' first, the transient would revert to blue
# 'loading' and sit there forever. Letting any reply pre-empt the optimistic
# 'loading' avoids that and keeps the box self-correcting.
OPTIMISTIC_LOADING_GRACE_MS = 400

# umqtt.simple does NOT auto-ping; check_msg() only reads. With keepalive=60 the
# broker will drop an idle box (no taps, no incoming state) after a missed
# keepalive, and the next socket op raises OSError. So we ping on our own at
# ~half the keepalive to hold the connection open between taps.
MQTT_KEEPALIVE_S = 60
MQTT_PING_INTERVAL_MS = (MQTT_KEEPALIVE_S // 2) * 1000

# LED ring + buzzer pins (see wiring header / CLAUDE.md). Passed explicitly so
# this file documents the hardware map even though they match Feedback's
# defaults.
LED_PIN = 28
NUM_PIXELS = 24
BUZZER_PIN = 22


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("connecting to Wi-Fi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        deadline = time.ticks_add(time.ticks_ms(), WIFI_CONNECT_TIMEOUT_MS)
        while not wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise RuntimeError("Wi-Fi failed, status=" + str(wlan.status()))
            time.sleep_ms(200)
    print("Wi-Fi ok, ip=", wlan.ifconfig()[0])


def connect_mqtt(on_state):
    client = MQTTClient(
        client_id=CLIENT_ID,
        server=MQTT_HOST,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=MQTT_KEEPALIVE_S,
    )
    client.set_callback(on_state)
    print("connecting MQTT: {}@{}:{}".format(MQTT_USER, MQTT_HOST, MQTT_PORT))
    client.connect()
    client.subscribe(TOPIC_STATE)
    print("MQTT connected, subscribed to", TOPIC_STATE.decode())
    return client


def init_pn532():
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
    pn532 = PN532(i2c)
    pn532.init()
    print("PN532 ready")
    return pn532


def make_state_handler(fb, pending):
    # vonbox/state arrives in the TAGGED form:
    #   {"state": "<NAME>", "uid": ..., "title": ..., "reason": ...}
    # A garbled or unexpected payload must never take down the loop — the box
    # has to keep reading taps even if HA sends junk. So everything here is
    # wrapped: parse, validate, then hand the sustained state to feedback.
    #
    # `pending` is the single-element [deadline_or_None] holder for the deferred
    # optimistic 'loading'. ANY valid reply from HA means HA has taken ownership
    # of the visual state, so we cancel the pending flip (clearing the holder).
    # This is what stops a re-tap's 'already_playing' from reverting to 'loading'.
    def on_state(topic, msg):
        try:
            data = json.loads(msg)
            state = data.get("state")
            if not state:
                print("state msg missing 'state':", msg)
                return
            pending[0] = None  # HA answered — drop any deferred optimistic loading
            fb.set_state(state, title=data.get("title"), reason=data.get("reason"))
            print("<- {}: {}".format(topic.decode() if isinstance(topic, bytes) else topic, msg))
        except (ValueError, AttributeError, KeyError) as exc:
            print("bad state payload ({}): {}".format(exc, msg))
    return on_state


def reconnect_mqtt(client):
    # Re-establish a dropped connection AND re-subscribe — a bare reconnect
    # without the subscribe would leave the box deaf to vonbox/state.
    client.connect()
    client.subscribe(TOPIC_STATE)
    print("MQTT reconnected, re-subscribed to", TOPIC_STATE.decode())


def publish_tap(client, uid_hex):
    payload = json.dumps({"uid": uid_hex})
    try:
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {}".format(TOPIC_TAPPED.decode(), payload))
    except OSError as exc:
        # Most likely the broker dropped us. Reconnect once and retry; if that
        # also fails, let the caller see it.
        print("publish failed ({}), reconnecting MQTT".format(exc))
        reconnect_mqtt(client)
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {} (after reconnect)".format(TOPIC_TAPPED.decode(), payload))


fb = Feedback(led_pin=LED_PIN, num_pixels=NUM_PIXELS, buzzer_pin=BUZZER_PIN)

# Single-element holder for the deferred optimistic 'loading' deadline (ticks_ms
# value) or None. Shared between the state handler (which clears it when HA
# answers) and the main loop (which fires the flip when it elapses).
pending_loading = [None]

connect_wifi()
mqtt = connect_mqtt(make_state_handler(fb, pending_loading))
nfc = init_pn532()

fb.boot()              # power-on flourish: rising cue + warm-white comet lap
fb.set_state("idle")
print("ready. tap a tag.")

# Edge-trigger + 2s-absence cooldown, verbatim in spirit from nfc_to_mqtt_test:
# a UID only fires on the leading edge, and the same UID can't re-fire until it
# has been absent from the field for ABSENCE_MS.
current_uid = None
last_seen_ms = 0
last_nfc_poll_ms = time.ticks_add(time.ticks_ms(), -NFC_POLL_INTERVAL_MS)
last_ping_ms = time.ticks_ms()

try:
    while True:
        loop_start = time.ticks_ms()

        # 1. Rate-limited NFC poll (~10Hz). lib/pn532 already swallows stale
        #    half-frames internally, so we just read and trust None == no tag.
        if time.ticks_diff(loop_start, last_nfc_poll_ms) >= NFC_POLL_INTERVAL_MS:
            last_nfc_poll_ms = loop_start
            uid = nfc.read_passive_target(timeout_ms=150)

            if uid is not None:
                if uid != current_uid:
                    uid_hex = uid.hex().upper()
                    print("TAPPED:", uid_hex)
                    # Local, instant feedback FIRST — the box reacts to the
                    # tap itself, before the broker round-trip.
                    fb.tap_accepted()
                    publish_tap(mqtt, uid_hex)
                    # Optimistic 'loading' is ARMED, not fired: we give HA a
                    # short grace window to answer. If it replies with any
                    # sustained state (or a transient like 'already_playing' on
                    # a re-tap), the handler cancels this and we never flip to
                    # blue. Only if HA is slow do we show 'loading' so the box
                    # isn't visually stuck on the tap sparkle.
                    pending_loading[0] = time.ticks_add(
                        time.ticks_ms(), OPTIMISTIC_LOADING_GRACE_MS
                    )
                    current_uid = uid
                last_seen_ms = time.ticks_ms()
            else:
                if current_uid is not None:
                    if time.ticks_diff(time.ticks_ms(), last_seen_ms) >= ABSENCE_MS:
                        current_uid = None

        # 2. Drain any incoming vonbox/state (non-blocking — never wait_msg()).
        #    Guarded: a broker drop surfaces here as OSError, and an unguarded
        #    raise would fall straight through to finally{} and kill the box.
        #    Instead we reconnect+re-subscribe and keep listening.
        try:
            mqtt.check_msg()
        except OSError as exc:
            print("check_msg failed ({}), reconnecting MQTT".format(exc))
            try:
                reconnect_mqtt(mqtt)
            except OSError as exc2:
                print("reconnect failed ({}), will retry next loop".format(exc2))

        # 3. Fire the deferred optimistic 'loading' if HA hasn't answered within
        #    the grace window. (The handler clears pending_loading the moment a
        #    vonbox/state reply arrives, so this only fires when HA is slow.)
        if pending_loading[0] is not None and \
                time.ticks_diff(time.ticks_ms(), pending_loading[0]) >= 0:
            pending_loading[0] = None
            fb.set_state("loading")

        # 4. Keepalive: umqtt.simple won't ping on its own, so we do, at
        #    ~half the keepalive, to keep an idle box's socket from being
        #    dropped between taps.
        if time.ticks_diff(time.ticks_ms(), last_ping_ms) >= MQTT_PING_INTERVAL_MS:
            last_ping_ms = time.ticks_ms()
            try:
                mqtt.ping()
            except OSError as exc:
                print("ping failed ({}), reconnecting MQTT".format(exc))
                try:
                    reconnect_mqtt(mqtt)
                except OSError as exc2:
                    print("reconnect failed ({}), will retry next loop".format(exc2))

        # 5. Advance the ring/buzzer animation by at most one frame.
        fb.tick()

        elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
        if elapsed < LOOP_TICK_MS:
            time.sleep_ms(LOOP_TICK_MS - elapsed)

except KeyboardInterrupt:
    print("\nstopping.")
finally:
    fb.off()
    try:
        mqtt.disconnect()
    except Exception:
        pass
    print("ring cleared, buzzer silent, MQTT closed.")

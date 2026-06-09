# Phase 3 sub-milestone 4: tap → MQTT.
#
# On each new tap, publish {"uid": "<hex>"} to vonbox/nfc/tapped. Same
# edge-triggered + 2s-absence cooldown as the Phase 2 tap detector — re-reads
# of the same tag inside the cooldown window stay quiet.
#
# Pre-flight:
#   - secrets.py must be on the Pico's flash (already there from sub-milestone 3.2).
#   - umqtt.simple must be on the Pico's flash under /lib (install via
#     test/bench/install_umqtt.py if missing).
#   - lib/pn532.py must be uploaded to the Pico via MicroPico "Upload current
#     file" — otherwise `from pn532 import PN532` will ImportError.
#
# Verify from the Mac with:
#   mosquitto_sub -h 192.168.0.123 -p 1883 -u vonbox -P '<password>' \
#       -t 'vonbox/#' -v
# Each tap should print:
#   vonbox/nfc/tapped {"uid": "04462765C82A81"}

import json
import network
import time

from machine import Pin, I2C
from umqtt.simple import MQTTClient

from pn532 import PN532
from secrets import (
    WIFI_SSID, WIFI_PASSWORD,
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
)

CLIENT_ID = b"vonbox-pico"
TOPIC_TAPPED = b"vonbox/nfc/tapped"

POLL_INTERVAL_MS = 100   # ~10Hz
ABSENCE_MS = 2000        # how long a UID must be gone before it can re-fire
WIFI_CONNECT_TIMEOUT_MS = 15_000


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


def connect_mqtt():
    client = MQTTClient(
        client_id=CLIENT_ID,
        server=MQTT_HOST,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD,
        keepalive=60,
    )
    print("connecting MQTT: {}@{}:{}".format(MQTT_USER, MQTT_HOST, MQTT_PORT))
    client.connect()
    print("MQTT connected")
    return client


def init_pn532():
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)
    pn532 = PN532(i2c)
    pn532.init()
    print("PN532 ready")
    return pn532


def publish_tap(client, uid_hex):
    payload = json.dumps({"uid": uid_hex})
    try:
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {}".format(TOPIC_TAPPED.decode(), payload))
    except OSError as exc:
        # Most likely the broker dropped us. Reconnect once and retry; if that
        # also fails, let the caller see it.
        print("publish failed ({}), reconnecting MQTT".format(exc))
        client.connect()
        client.publish(TOPIC_TAPPED, payload)
        print("-> {}: {} (after reconnect)".format(TOPIC_TAPPED.decode(), payload))


connect_wifi()
mqtt = connect_mqtt()
nfc = init_pn532()

print("ready. tap a tag.")

current_uid = None
last_seen_ms = 0

while True:
    loop_start = time.ticks_ms()
    uid = nfc.read_passive_target(timeout_ms=150)

    if uid is not None:
        if uid != current_uid:
            uid_hex = uid.hex().upper()
            print("TAPPED:", uid_hex)
            publish_tap(mqtt, uid_hex)
            current_uid = uid
        last_seen_ms = time.ticks_ms()
    else:
        if current_uid is not None:
            if time.ticks_diff(time.ticks_ms(), last_seen_ms) >= ABSENCE_MS:
                current_uid = None

    elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
    if elapsed < POLL_INTERVAL_MS:
        time.sleep_ms(POLL_INTERVAL_MS - elapsed)

# Phase 3 sub-milestone 3: Pico publishes test messages over MQTT.
#
# Connects to Wi-Fi using secrets.py, then to the Mosquitto broker on the
# Synology, then publishes "hello N" to test/hello once every 5 seconds.
#
# On your Mac, run:
#   mosquitto_sub -h 192.168.0.123 -p 1883 -u vonbox -P '<password>' -t 'test/#' -v
# You should see one line per publish.

import network
import time
from umqtt.simple import MQTTClient

from secrets import (
    WIFI_SSID, WIFI_PASSWORD,
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
)

CLIENT_ID = b"vonbox-pico"
TOPIC = b"test/hello"
PUBLISH_INTERVAL_S = 5
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


connect_wifi()
client = connect_mqtt()

n = 0
while True:
    n += 1
    msg = "hello {}".format(n)
    client.publish(TOPIC, msg)
    print("-> {}: {}".format(TOPIC.decode(), msg))
    time.sleep(PUBLISH_INTERVAL_S)

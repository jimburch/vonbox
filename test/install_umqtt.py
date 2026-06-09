# One-shot installer: fetches umqtt.simple from micropython-lib via mip
# and writes it to the Pico's flash under /lib/umqtt/simple.py.
#
# Run once via MicroPico "Run current file on Pico". After it succeeds,
# `from umqtt.simple import MQTTClient` will work on this Pico forever
# (or until the flash is wiped).

import network
import time
import mip

from secrets import WIFI_SSID, WIFI_PASSWORD


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("connecting to Wi-Fi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        deadline = time.ticks_add(time.ticks_ms(), 15_000)
        while not wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise RuntimeError("Wi-Fi failed, status=" + str(wlan.status()))
            time.sleep_ms(200)
    print("Wi-Fi ok, ip=", wlan.ifconfig()[0])


connect_wifi()
print("installing umqtt.simple via mip...")
mip.install("umqtt.simple")
print("done. Listing /lib:")
import os
for entry in os.ilistdir("/lib"):
    print(" ", entry)

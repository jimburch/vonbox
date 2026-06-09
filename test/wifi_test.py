# Phase 3 sub-milestone 2: Pico connects to Wi-Fi and prints its IP.
#
# Ephemeral run via MicroPico "Run current file on Pico". secrets.py must
# already be on the Pico's filesystem — if running ephemerally without an
# Upload Project step, MicroPico syncs the current file plus auto-uploads
# changed siblings; if Wi-Fi import fails on `secrets`, do an Upload Project
# once so secrets.py lands on the Pico's flash.

import network
import time
from secrets import WIFI_SSID, WIFI_PASSWORD

CONNECT_TIMEOUT_MS = 15_000  # cold-boot a Pico 2 WH usually associates in 2-5s

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

print("connecting to SSID:", WIFI_SSID)
wlan.connect(WIFI_SSID, WIFI_PASSWORD)

deadline = time.ticks_add(time.ticks_ms(), CONNECT_TIMEOUT_MS)
while not wlan.isconnected():
    if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
        # status() codes: -3 bad password, -2 no AP found, -1 fail, 0 idle, 1 connecting, 3 got IP
        raise RuntimeError("Wi-Fi connect timed out, status=" + str(wlan.status()))
    time.sleep_ms(200)

ip, subnet, gateway, dns = wlan.ifconfig()
print("connected.")
print("  ip:     ", ip)
print("  subnet: ", subnet)
print("  gateway:", gateway)
print("  dns:    ", dns)
print("  rssi:   ", wlan.status("rssi"), "dBm")

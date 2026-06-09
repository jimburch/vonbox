from machine import Pin, I2C
import time

PN532_ADDR = 0x24
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)

# GetFirmwareVersion frame, per PN532 datasheet:
#   preamble 00, start 00 FF, len 02, lcs FE, TFI D4 (host->PN532),
#   cmd 02 (GetFirmwareVersion), dcs 2A (= 0x100 - (D4 + 02)), postamble 00
GET_FIRMWARE_VERSION = bytes([0x00, 0x00, 0xFF, 0x02, 0xFE, 0xD4, 0x02, 0x2A, 0x00])

print("sending GetFirmwareVersion...")
i2c.writeto(PN532_ADDR, GET_FIRMWARE_VERSION)

# PN532 needs a moment to process and assert its RDY status byte.
# Poll the first byte; it's 0x01 when a response is ready.
def wait_ready(timeout_ms=1000):
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        status = i2c.readfrom(PN532_ADDR, 1)
        if status[0] == 0x01:
            return True
        time.sleep_ms(10)
    return False

# First the ACK frame (status + 6 bytes: 00 00 FF 00 FF 00)
if not wait_ready():
    print("timed out waiting for ACK")
else:
    ack = i2c.readfrom(PN532_ADDR, 7)
    print("ACK:", [hex(b) for b in ack])

# Then the actual response
if not wait_ready():
    print("timed out waiting for response")
else:
    resp = i2c.readfrom(PN532_ADDR, 13)
    print("response:", [hex(b) for b in resp])
    # Response payload (after status byte and frame header) is:
    #   D5 03 IC VER REV SUPPORT
    # IC=0x32 means PN532, VER/REV are firmware version numbers.
    try:
        ic = resp[7]
        ver = resp[8]
        rev = resp[9]
        support = resp[10]
        print("IC: 0x{:02X}  firmware: {}.{}  support: 0x{:02X}".format(ic, ver, rev, support))
    except IndexError:
        print("response too short to parse")

# Sub-milestone 3: single-shot tap detection.
#
# Polls the PN532 at ~10Hz. Prints `TAPPED: <UID>` once each time a *new* UID
# enters the field. Repeated polls of the same UID stay quiet until the tag
# has been absent for >= ABSENCE_MS, then the next read of that UID counts as
# a fresh tap.
#
# Driver code is inlined here for ephemeral MicroPico "Run current file"
# usage — once this works we'll graduate it to lib/pn532.py.

from machine import Pin, I2C
import time

# --- PN532 protocol constants -------------------------------------------------

PN532_ADDR = 0x24
HOST_TO_PN532 = 0xD4
PN532_TO_HOST = 0xD5

CMD_SAMCONFIGURATION     = 0x14
CMD_RFCONFIGURATION      = 0x32
CMD_INLISTPASSIVETARGET  = 0x4A

ACK_BODY = b"\x00\x00\xff\x00\xff\x00"

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=100000)


# --- low-level framing --------------------------------------------------------

def _build_frame(cmd, params=b""):
    # Standard PN532 information frame:
    #   preamble(00) start(00 FF) LEN LCS TFI CMD PARAMS... DCS postamble(00)
    body = bytes([HOST_TO_PN532, cmd]) + params
    length = len(body)
    lcs = (-length) & 0xFF
    dcs = (-sum(body)) & 0xFF
    return bytes([0x00, 0x00, 0xFF, length, lcs]) + body + bytes([dcs, 0x00])


def _wait_ready(timeout_ms=1000):
    # In I2C mode the PN532 prefixes every read with a status byte; 0x01 = ready.
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        try:
            if i2c.readfrom(PN532_ADDR, 1)[0] == 0x01:
                return True
        except OSError:
            pass
        time.sleep_ms(5)
    return False


def _read_ack():
    if not _wait_ready():
        return False
    data = i2c.readfrom(PN532_ADDR, 7)
    return data[1:7] == ACK_BODY


def _send_and_ack(cmd, params=b""):
    i2c.writeto(PN532_ADDR, _build_frame(cmd, params))
    return _read_ack()


def _read_response(expected_resp_code, n=32, timeout_ms=1000):
    if not _wait_ready(timeout_ms):
        return None
    raw = i2c.readfrom(PN532_ADDR, n)
    # raw[0]=status, raw[1:4]=00 00 FF, raw[4]=LEN, raw[5]=LCS,
    # raw[6]=TFI(0xD5), raw[7]=response code, raw[8:8+LEN-2]=payload, then DCS+postamble.
    if raw[1:4] != b"\x00\x00\xff":
        return None
    if raw[6] != PN532_TO_HOST or raw[7] != expected_resp_code:
        return None
    length = raw[4]
    return raw[8:8 + length - 2]


# --- high-level commands ------------------------------------------------------

def sam_configuration():
    # mode=0x01 normal (no SAM), timeout=0x14 (unused in normal mode), use_irq=0x01.
    if not _send_and_ack(CMD_SAMCONFIGURATION, b"\x01\x14\x01"):
        return False
    return _read_response(CMD_SAMCONFIGURATION + 1) is not None


def set_passive_max_retries(retries):
    # RFConfiguration item 5 = MxRetries.
    #   MxRtyATR = 0xFF (default, used during active mode — irrelevant here)
    #   MxRtyPSL = 0x01 (default)
    #   MxRtyPassiveActivation = retries  (0 = try once and return immediately)
    # Without this the chip defaults to 0xFF (infinite) and InListPassiveTarget
    # blocks until a tag appears — useless for a 10Hz poll loop.
    if not _send_and_ack(CMD_RFCONFIGURATION, bytes([0x05, 0xFF, 0x01, retries])):
        return False
    return _read_response(CMD_RFCONFIGURATION + 1) is not None


def read_passive_target(timeout_ms=200):
    # MaxTg=1 (we only care about the first card in field), BrTy=0x00 (ISO14443A 106kbps).
    if not _send_and_ack(CMD_INLISTPASSIVETARGET, b"\x01\x00"):
        return None
    payload = _read_response(CMD_INLISTPASSIVETARGET + 1, n=32, timeout_ms=timeout_ms)
    if not payload or payload[0] == 0:
        return None
    # payload layout: NbTg, Tg, SENS_RES(2), SEL_RES(1), NFCIDLength, NFCID...
    uid_len = payload[5]
    return bytes(payload[6:6 + uid_len])


# --- bring-up -----------------------------------------------------------------

print("init: SAM configuration...")
if not sam_configuration():
    raise RuntimeError("SAMConfiguration failed")

print("init: setting max passive activation retries to 0 (return immediately)...")
if not set_passive_max_retries(0x00):
    raise RuntimeError("RFConfiguration failed")

print("ready. tap a tag.")


# --- single-shot tap detection loop ------------------------------------------

POLL_INTERVAL_MS = 100   # ~10Hz
ABSENCE_MS = 2000        # how long a UID must be gone before it can re-fire

current_uid = None       # UID we're currently treating as "present"
last_seen_ms = 0         # ticks_ms of the most recent poll that saw current_uid

while True:
    loop_start = time.ticks_ms()
    uid = read_passive_target(timeout_ms=150)

    if uid is not None:
        if uid != current_uid:
            # Either nothing was present, or a different tag has swapped in.
            print("TAPPED:", uid.hex().upper())
            current_uid = uid
        last_seen_ms = time.ticks_ms()
    else:
        # No tag this poll. If the previously-present tag has been gone long
        # enough, clear it so a future re-tap of the same UID counts again.
        if current_uid is not None:
            if time.ticks_diff(time.ticks_ms(), last_seen_ms) >= ABSENCE_MS:
                current_uid = None

    elapsed = time.ticks_diff(time.ticks_ms(), loop_start)
    if elapsed < POLL_INTERVAL_MS:
        time.sleep_ms(POLL_INTERVAL_MS - elapsed)

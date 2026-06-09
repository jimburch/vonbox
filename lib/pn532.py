# Minimal MicroPython driver for the PN532 over I2C.
#
# Scope is intentionally narrow: bring the chip up, configure it for
# non-blocking passive-target reads, and read ISO14443A UIDs. That's all
# the NFC Movie Box needs. If we ever need NTAG read/write, MIFARE auth,
# or active P2P, extend here.
#
# Designed to be uploaded once to the Pico's flash under /lib/pn532.py;
# orchestrator scripts then `from pn532 import PN532`.
#
# Reference: the inline implementation in test/nfc_tap_test.py, plus the
# Phase 2 lessons in SPEC.md (status-byte 0x01, MxRtyPassiveActivation = 0,
# 7-byte NTAG UIDs starting 0x04).

import time

HOST_TO_PN532 = 0xD4
PN532_TO_HOST = 0xD5

CMD_SAMCONFIGURATION    = 0x14
CMD_RFCONFIGURATION     = 0x32
CMD_INLISTPASSIVETARGET = 0x4A

DEFAULT_ADDR = 0x24

_ACK_BODY = b"\x00\x00\xff\x00\xff\x00"


class PN532Error(Exception):
    pass


class PN532:

    def __init__(self, i2c, address=DEFAULT_ADDR):
        self._i2c = i2c
        self._addr = address

    # --- bring-up ---------------------------------------------------------

    def init(self):
        # One-shot setup: enter normal SAM mode, then ask the RF front-end
        # to return immediately when no tag is in field (otherwise
        # InListPassiveTarget blocks forever — see Phase 2 lesson #6).
        #
        # SAMConfiguration is retried once: if MicroPico hot-stopped a
        # previous run mid-frame, the chip is still holding stale I2C state
        # and the first call NACKs. The first call's preamble itself
        # discards that state; the second call lands clean. See Phase 3
        # lesson #9.
        for _ in range(2):
            try:
                if self._sam_configuration():
                    break
            except OSError:
                pass
            time.sleep_ms(50)
        else:
            raise PN532Error("SAMConfiguration failed")
        if not self._set_passive_max_retries(0x00):
            raise PN532Error("RFConfiguration failed")

    # --- public read API --------------------------------------------------

    def read_passive_target(self, timeout_ms=200):
        # Returns the UID bytes of the first ISO14443A target in field,
        # or None if no tag is present.
        if not self._send_and_ack(CMD_INLISTPASSIVETARGET, b"\x01\x00"):
            return None
        payload = self._read_response(
            CMD_INLISTPASSIVETARGET + 1, n=32, timeout_ms=timeout_ms
        )
        if not payload or payload[0] == 0:
            return None
        # payload layout: NbTg, Tg, SENS_RES(2), SEL_RES(1), NFCIDLength, NFCID...
        uid_len = payload[5]
        return bytes(payload[6:6 + uid_len])

    # --- low-level framing ------------------------------------------------

    @staticmethod
    def _build_frame(cmd, params=b""):
        body = bytes([HOST_TO_PN532, cmd]) + params
        length = len(body)
        lcs = (-length) & 0xFF
        dcs = (-sum(body)) & 0xFF
        return bytes([0x00, 0x00, 0xFF, length, lcs]) + body + bytes([dcs, 0x00])

    def _wait_ready(self, timeout_ms=1000):
        # In I2C mode the PN532 prefixes every read with a status byte;
        # 0x01 means a frame is ready to be clocked out.
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while time.ticks_diff(deadline, time.ticks_ms()) > 0:
            try:
                if self._i2c.readfrom(self._addr, 1)[0] == 0x01:
                    return True
            except OSError:
                pass
            time.sleep_ms(5)
        return False

    def _read_ack(self):
        if not self._wait_ready():
            return False
        data = self._i2c.readfrom(self._addr, 7)
        return data[1:7] == _ACK_BODY

    def _send_and_ack(self, cmd, params=b""):
        self._i2c.writeto(self._addr, self._build_frame(cmd, params))
        return self._read_ack()

    def _read_response(self, expected_resp_code, n=32, timeout_ms=1000):
        if not self._wait_ready(timeout_ms):
            return None
        raw = self._i2c.readfrom(self._addr, n)
        # raw[0]=status, raw[1:4]=00 00 FF, raw[4]=LEN, raw[5]=LCS,
        # raw[6]=TFI (0xD5), raw[7]=response code, raw[8:8+LEN-2]=payload.
        if raw[1:4] != b"\x00\x00\xff":
            return None
        if raw[6] != PN532_TO_HOST or raw[7] != expected_resp_code:
            return None
        length = raw[4]
        return raw[8:8 + length - 2]

    # --- internal high-level commands -------------------------------------

    def _sam_configuration(self):
        # mode=0x01 normal (no SAM), timeout=0x14 (unused), use_irq=0x01.
        if not self._send_and_ack(CMD_SAMCONFIGURATION, b"\x01\x14\x01"):
            return False
        return self._read_response(CMD_SAMCONFIGURATION + 1) is not None

    def _set_passive_max_retries(self, retries):
        # RFConfiguration item 5 = MxRetries.
        #   MxRtyATR = 0xFF (default, used during active mode)
        #   MxRtyPSL = 0x01 (default)
        #   MxRtyPassiveActivation = retries (0 = try once, return immediately)
        if not self._send_and_ack(
            CMD_RFCONFIGURATION, bytes([0x05, 0xFF, 0x01, retries])
        ):
            return False
        return self._read_response(CMD_RFCONFIGURATION + 1) is not None

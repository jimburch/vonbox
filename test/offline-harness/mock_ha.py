"""Fake Home Assistant for away-from-home testing of the NFC Movie Box.

This stands in for the whole HA + Apple TV + Plex back end. It subscribes to
the Pico's tap events on vonbox/nfc/tapped and publishes the resulting state
machine on vonbox/state — exactly the contract the real HA automation
(SPEC.md Phase 3, "On HA") will satisfy, so the Pico's full-loop firmware can
be exercised end-to-end with no home LAN, no Synology, no Pi.

This is the LAPTOP side and runs under CPython, so paho-mqtt is fair game here
(the "no paho, use umqtt" rule applies only to the Pico). It uses paho-mqtt
2.x and the VERSION2 callback API.

Install hint:
    pip3 install paho-mqtt

Run it (the dev broker must already be up — see test/offline-harness/mosquitto.dev.conf):
    mosquitto -c test/offline-harness/mosquitto.dev.conf -v     # terminal 1
    python3 test/offline-harness/mock_ha.py                      # terminal 2

Once running you can either tap a real tag against the Pico, or type commands
at the prompt to inject states directly (see the help banner on startup) and
watch the Pico's LED ring / buzzer react without touching any NFC hardware.

Full runbook: docs/testing-away-from-home.md
"""

import json
import sys
import threading

import paho.mqtt.client as mqtt

# --- Broker -----------------------------------------------------------------
# mock_ha.py and the broker run on the same laptop, so we connect to loopback.
# (The Pico, a different host, reaches the same broker via the laptop's hotspot
# IP — but that's the Pico's concern, not ours.)
BROKER_HOST = "localhost"
BROKER_PORT = 1883

# --- Topics (must match the canonical contract) -----------------------------
TOPIC_TAPPED = "vonbox/nfc/tapped"   # Pico -> us:  {"uid": "<HEX>"}
TOPIC_STATE = "vonbox/state"         # us -> Pico:  tagged-form state payload

# --- Behaviour --------------------------------------------------------------
# How long the fake Apple TV "takes" to start (or fail) playback after a tap.
# Mirrors the real cold-start wake + Plex launch latency the Pico will see, so
# the 'loading' animation actually gets airtime before 'playing'/'error'.
PLAYBACK_DELAY_S = 2.5

# UID -> (plex_rating_key, title). Seeded with the one known-good test tag.
# The real HA holds this as a UID->rating-key map (SPEC.md Phase 3); we carry
# the title too because it's a required key in the canonical vonbox/state
# payload (and a future display would render it — see ADR 0003).
MOVIE_TABLE = {
    "04462765C82A81": ("190", "The Super Mario Bros. Movie"),
}

# A designated tag that is "known" but whose playback always fails, so we can
# exercise the Pico's error-then-revert path without an unknown-tag lookup
# miss. Tap this UID and you get loading -> (2.5s) -> error/playback_failed.
FAKE_FAIL_UID = "04FA11FA11FA11"

# Placeholder identity used by the stdin 'playing'/'error' inject commands,
# which have no real tag behind them.
INJECT_UID = "04462765C82A81"
INJECT_TITLE = "The Super Mario Bros. Movie"


class MockHA:
    """Holds the tiny bit of session state the real HA would track."""

    def __init__(self, client):
        self._client = client
        # The UID of the movie we believe is loading/playing right now, or None.
        # Lets us tell a fresh tap from a re-tap of the active movie.
        self._current_uid = None
        # Keep references so we can cancel a pending playback if a new tap
        # arrives mid-load (switching movies before the first one "starts").
        self._pending_timer = None

    # -- publishing ----------------------------------------------------------

    def _publish_state(self, state, uid=None, title=None, reason=None):
        """Emit one tagged-form state payload to vonbox/state.

        Retained vs. not: SUSTAINED states (idle/playing/paused/standby) are
        published retained so a Pico that connects late immediately learns the
        current world. TRANSIENT states (loading/already_playing/error) are
        NOT retained — they're momentary cues; a late subscriber should never
        be greeted by a stale 'error' or a frozen 'loading'.
        """
        retain = state in ("idle", "playing", "paused", "standby")
        payload = {"state": state, "uid": uid, "title": title, "reason": reason}
        encoded = json.dumps(payload)
        self._client.publish(TOPIC_STATE, encoded, retain=retain)
        flag = " (retained)" if retain else ""
        print("-> {} {}{}".format(TOPIC_STATE, encoded, flag))

    def publish_idle(self):
        """Retained idle, so a freshly booted Pico shows idle on connect."""
        self._current_uid = None
        self._publish_state("idle")

    # -- tap handling --------------------------------------------------------

    def handle_tap(self, uid):
        """React to a vonbox/nfc/tapped event for the given UID."""
        # Re-tap of the movie that's already the active session -> soft no-op.
        # (The Pico should already suppress this locally; this is the safety
        # belt the spec calls for in case its state drifted.)
        if uid == self._current_uid:
            key_title = MOVIE_TABLE.get(uid)
            title = key_title[1] if key_title else INJECT_TITLE
            self._publish_state("already_playing", uid=uid, title=title)
            return

        # Designated always-fails tag: known enough to start loading, then
        # reports a playback failure.
        if uid == FAKE_FAIL_UID:
            self._current_uid = uid
            self._publish_state("loading", uid=uid, title=None)
            self._schedule(
                lambda: self._publish_state(
                    "error", uid=uid, title=None, reason="playback_failed"
                )
            )
            return

        # Unknown tag -> immediate error, no loading phase. Does NOT become the
        # current session.
        if uid not in MOVIE_TABLE:
            self._publish_state("error", uid=uid, title=None, reason="unknown_tag")
            return

        # Known, good, and different from what's playing -> start it.
        rating_key, title = MOVIE_TABLE[uid]
        self._current_uid = uid
        print("   (uid {} -> plex rating key {} = {!r})".format(uid, rating_key, title))
        self._publish_state("loading", uid=uid, title=title)
        self._schedule(
            lambda: self._publish_state("playing", uid=uid, title=title)
        )

    def _schedule(self, fn):
        """Run fn after PLAYBACK_DELAY_S off the network loop.

        paho's loop thread must never block, so the loading->playing/error
        delay lives on a threading.Timer instead of a sleep in the callback.
        A new tap cancels any still-pending timer so we don't fire a stale
        'playing' for a movie that's already been switched away from.
        """
        if self._pending_timer is not None:
            self._pending_timer.cancel()
        self._pending_timer = threading.Timer(PLAYBACK_DELAY_S, fn)
        self._pending_timer.daemon = True
        self._pending_timer.start()

    # -- stdin injection -----------------------------------------------------

    def inject(self, command):
        """Publish a state directly, bypassing the tap path, for render tests."""
        if command == "idle":
            self.publish_idle()
        elif command == "standby":
            self._current_uid = None
            self._publish_state("standby")
        elif command == "paused":
            self._publish_state("paused", uid=INJECT_UID, title=INJECT_TITLE)
        elif command == "playing":
            self._current_uid = INJECT_UID
            self._publish_state("playing", uid=INJECT_UID, title=INJECT_TITLE)
        elif command == "error":
            self._publish_state(
                "error", uid=INJECT_UID, title=INJECT_TITLE, reason="injected"
            )
        else:
            print("unknown command: {!r} (try 'help')".format(command))


# --- paho callbacks (VERSION2 signatures) -----------------------------------

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("connected to broker at {}:{}".format(BROKER_HOST, BROKER_PORT))
        client.subscribe(TOPIC_TAPPED)
        print("subscribed to {}".format(TOPIC_TAPPED))
        # Seed the retained idle state so a Pico connecting any time after us
        # immediately has a sustained state to render.
        userdata.publish_idle()
    else:
        print("connect failed, reason_code={}".format(reason_code))


def on_message(client, userdata, msg):
    # Wrap everything: a malformed payload should log and keep the loop alive,
    # never crash the mock and strand a test run.
    try:
        text = msg.payload.decode()
        print("<- {} {}".format(msg.topic, text))
        data = json.loads(text)
        uid = data.get("uid")
        if not uid:
            print("   ignoring: no 'uid' in payload")
            return
        userdata.handle_tap(uid)
    except Exception as exc:  # noqa: BLE001 - mock test tool, stay alive
        print("   bad message ({}): {!r}".format(exc, msg.payload))


HELP_BANNER = """
mock_ha ready. Tap a tag against the Pico, or inject a state by typing:
    idle      -> retained idle      (box awake, ready)
    playing   -> retained playing   (placeholder Mario session)
    paused    -> retained paused
    standby   -> retained standby   (session ended)
    error     -> transient error    (reason 'injected')
    help      -> show this banner
    quit      -> publish idle and exit

Known test tag : 04462765C82A81 -> "The Super Mario Bros. Movie" (key 190)
Fake-fail tag  : {fail}  -> loading then error/playback_failed
Any other UID  : immediate error/unknown_tag
""".format(fail=FAKE_FAIL_UID)


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mock-ha")
    ha = MockHA(client)
    client.user_data_set(ha)
    client.on_connect = on_connect
    client.on_message = on_message

    print("connecting to broker at {}:{} ...".format(BROKER_HOST, BROKER_PORT))
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    print(HELP_BANNER)

    try:
        for line in sys.stdin:
            command = line.strip().lower()
            if not command:
                continue
            if command == "quit":
                break
            if command == "help":
                print(HELP_BANNER)
                continue
            ha.inject(command)
    except KeyboardInterrupt:
        pass
    finally:
        # Leave the box in a clean, retained idle state on the way out so the
        # Pico doesn't sit on a stale 'playing' after the mock goes away.
        print("\nshutting down: publishing idle")
        ha.publish_idle()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

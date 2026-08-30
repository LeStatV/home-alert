"""The ntfy boundary: everything the household sees leaves through a sink."""
import asyncio
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

PRIORITY = {"URGENT": 5, "WATCH": 4, "INFO": 2}
# The owner's own topic: agent up, agent down, Telegram lost, everybody quiet under a
# siren (ADR 13). It is not a tier, so it rides as an override on the push.
SYSTEM_TOPIC = "system"
SILENT = 1                       # body updates must never make a sound
# ponytail: if an Android phone is seen dropping a p5 URGENT to silent because a p1
# update replaced it, SILENT = 2 is the candidate -- still below the ring threshold.
SILENT_KINDS = ("UPDATE", "CLEAR")   # neither is news: one is a body edit, one is over
TAGS = {"URGENT": "rotating_light", "WATCH": "warning", "INFO": "information_source"}


@dataclass(frozen=True, slots=True)
class Push:
    time: datetime
    kind: str       # NEW | PROMOTE | RESOUND (sound) | UPDATE (silent body update)
    tier: str       # URGENT | WATCH | INFO
    title: str
    body: str
    tag: str        # stable per event, so ntfy replaces the entry in place
    source: str = ""   # t.me link to the post behind it -- the "view source" action
    topic: str = ""    # overrides the tier's topic; only the `system` topic uses it


def now():
    """Naive UTC, the clock every timestamp in this project is in."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def system(sink, title, body="", tag=None):
    """A note on the owner's own topic: agent up, agent down, Telegram lost. It is not
    an alert, so it carries no tier of its own -- INFO is priority 2, silent."""
    when = now()
    sink(Push(when, "SYSTEM", "INFO", title, body,
              tag or f"system-{when:%Y%m%dT%H%M%S}", topic=SYSTEM_TOPIC))


async def heartbeat(sink, minutes, status=lambda: ""):
    """"The agent is still here", every `minutes`, until the process stops.

    One tag for all of them, so the phone keeps one line rather than a column of
    identical ones. Live only: `replay` has no wall clock to beat against.
    """
    while True:
        await asyncio.sleep(minutes * 60)
        system(sink, "Агент працює", status(), tag="system-heartbeat")


class Recorder:
    """Test sink: keeps the pushes instead of sending them."""

    def __init__(self):
        self.pushes = []

    def __call__(self, push):
        self.pushes.append(push)


class Console:
    """CLI sink: the notification sequence `replay` prints."""

    def __call__(self, push):
        # the body is several lines on a phone; on a terminal it stays one, so a replay
        # of a whole night can be diffed against another one line for line
        print(f"{push.time:%Y-%m-%d %H:%M:%S}  {push.kind:<8} {push.tier:<6} "
              f"{push.title}  |  {' · '.join(push.body.splitlines())}")


class Ntfy:
    """Publishes to a self-hosted ntfy over its JSON API (headers are latin-1 only,
    and every title here is Cyrillic)."""

    def __init__(self, config):
        self.url = config["url"].rstrip("/")
        self.topics = config["topics"]
        self.token = os.environ.get(config.get("token_env", "NTFY_TOKEN"))

    def __call__(self, push):
        payload = {
            "topic": push.topic or self.topics[push.tier],
            "title": push.title,
            "message": push.body,
            "priority": SILENT if push.kind in SILENT_KINDS else PRIORITY[push.tier],
            "tags": [TAGS[push.tier]],
            # ntfy links messages into a sequence: publishing again with the same
            # `sequence_id` replaces the notification the client already showed
            # (docs.ntfy.sh/publish "Updating notifications"). The event tag is that
            # id, so one event owns one entry in the shade instead of eighty.
            # Needs ntfy server >= 2.16 and Android app >= 1.22.2; older clients, and
            # iOS (which is not on the supported list), stack the updates as before.
            # Identity is (server, topic, sequence_id): the same tag on another topic
            # is another notification, so a push must keep its event's topic.
            "sequence_id": push.tag,
        }
        if push.source:
            payload["actions"] = [{"action": "view", "label": "Джерело",
                                   "url": push.source}]
        request = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"} |
                    ({"Authorization": f"Bearer {self.token}"} if self.token else {}))
        # ponytail: blocking, inside the live path's asyncio handler -- an ntfy server
        # that hangs stalls message processing for up to 5 s per push, mid-raid. The
        # upgrade is `await asyncio.to_thread(...)` once a sink can be async.
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
        except OSError as error:      # one unreachable push must not end the raid
            print(f"ntfy push failed ({error}): {push.tier} {push.title}", file=sys.stderr)

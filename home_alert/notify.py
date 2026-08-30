"""The ntfy boundary: everything the household sees leaves through a sink."""
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from datetime import datetime

PRIORITY = {"URGENT": 5, "WATCH": 4, "INFO": 2}
SILENT = 1                       # body updates must never make a sound
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


class Recorder:
    """Test sink: keeps the pushes instead of sending them."""

    def __init__(self):
        self.pushes = []

    def __call__(self, push):
        self.pushes.append(push)


class Console:
    """CLI sink: the notification sequence `replay` prints."""

    def __call__(self, push):
        print(f"{push.time:%Y-%m-%d %H:%M:%S}  {push.kind:<8} {push.tier:<6} "
              f"{push.title}  |  {push.body}")


class Ntfy:
    """Publishes to a self-hosted ntfy over its JSON API (headers are latin-1 only,
    and every title here is Cyrillic)."""

    def __init__(self, config):
        self.url = config["url"].rstrip("/")
        self.topics = config["topics"]
        self.token = os.environ.get(config.get("token_env", "NTFY_TOKEN"))

    def __call__(self, push):
        payload = {
            "topic": self.topics[push.tier],
            "title": push.title,
            "message": push.body,
            "priority": SILENT if push.kind == "UPDATE" else PRIORITY[push.tier],
            "tags": [TAGS[push.tier]],
            # ntfy links messages into a sequence: publishing again with the same
            # `sequence_id` replaces the notification the client already showed
            # (docs.ntfy.sh/publish "Updating notifications"). The event tag is that
            # id, so one event owns one entry in the shade instead of eighty.
            # Needs ntfy server and Android app >= 2.16; older clients, and iOS
            # (which is not on the supported list), stack the updates as before.
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

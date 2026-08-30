"""Message input: a JSONL corpus for `replay`, live Telegram for `run`.

Both produce the same `Message`, so everything downstream of this module is the
same code on both paths. Telethon is confined to `normalize`/`subscribe`/`run`.
"""
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from telethon import events as tg_events
from telethon.tl.types import PeerChannel
from telethon.utils import get_peer_id

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Message:
    channel: str
    id: int
    time: datetime          # naive UTC -- replay uses it as the clock
    reply_to: int | None
    text: str
    edited: bool = False    # a correction to a message we have already seen


def read_corpus(path, start=None, end=None):
    """Messages from a corpus in time order.

    `path` is either a directory of `<channel>.jsonl` (the research corpus, where
    the channel is the filename) or a single merged `.jsonl` whose rows carry a
    `channel` field (a test fixture). Rows without a date are skipped.
    """
    path = Path(path)
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    messages = []
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("date"):
                continue
            time = datetime.fromisoformat(row["date"]).astimezone(timezone.utc).replace(tzinfo=None)
            if (start and time < start) or (end and time > end):
                continue
            messages.append(Message(row.get("channel") or file.stem, row["id"], time,
                                    row.get("reply_to"), row.get("text") or ""))
    messages.sort(key=lambda m: (m.time, m.channel, m.id))
    return messages


def normalize(message, channel):
    """A Telethon message as the `Message` the corpus reader produces."""
    return Message(channel, message.id,
                   message.date.astimezone(timezone.utc).replace(tzinfo=None),
                   message.reply_to_msg_id, message.message or "",
                   bool(message.edit_date))


async def subscribe(client, channels, on_message):
    """Route the configured channels' updates into `on_message`.

    Telegram only pushes updates for dialogs the account has joined (ADR note), so a
    channel that is missing from the dialog list is logged and left: one unjoined
    channel must not cost the household the other five. Names and counts only ever
    reach the log -- never the session, never a token.
    """
    joined = set()
    async for dialog in client.iter_dialogs():
        joined.add(dialog.entity.id)
    handles = {}
    for handle in channels:
        try:
            entity = await client.get_entity(handle)
        except (ValueError, TypeError) as error:
            log.warning("channel %s: cannot resolve (%s)", handle, type(error).__name__)
            continue
        if entity.id not in joined:
            log.warning("channel %s: not joined, no updates will arrive", handle)
        # `event.chat_id` is the -100-marked form, `entity.id` the bare one; keying on
        # both means the live path never turns on which of the two Telethon hands over.
        handles[entity.id] = handles[get_peer_id(PeerChannel(entity.id))] = handle

    async def handler(event):
        handle = handles.get(event.chat_id)
        if handle is not None:
            on_message(normalize(event.message, handle))

    # one callback, both update types: Telegram sends a post as one or the other.
    client.add_event_handler(handler, tg_events.NewMessage())
    client.add_event_handler(handler, tg_events.MessageEdited())
    following = sorted(set(handles.values()))
    log.info("following %d/%d channels: %s", len(following), len(channels),
             ", ".join(following))
    return handles


async def run(client, channels, on_message, retry_sec=5):
    """Follow the channels until the process is stopped.

    Telethon reconnects on its own; `run_until_disconnected` returns only once it has
    given up, so the loop reconnects and says so. ponytail: a fixed gap, not a growing
    backoff -- the home server's link comes back in seconds or not at all.
    """
    await subscribe(client, channels, on_message)
    while True:
        await client.run_until_disconnected()
        log.warning("telegram disconnected; reconnecting in %ds", retry_sec)
        await asyncio.sleep(retry_sec)
        await client.connect()

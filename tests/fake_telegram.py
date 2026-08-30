"""A Telethon-shaped client that replays fixture rows as live updates.

Nothing here talks to Telegram: the point is that a live update, once normalized,
is the same `Message` the replayer feeds, so it can enter the same pipeline.
"""
from datetime import timezone

from home_alert import reader


class FakeMessage:
    """The fields `reader.normalize` reads off a `telethon.tl.custom.Message`."""

    def __init__(self, message, edit_date=None):
        self.id = message.id
        self.date = message.time.replace(tzinfo=timezone.utc)
        self.message = message.text
        self.reply_to_msg_id = message.reply_to
        self.edit_date = edit_date


class FakeEvent:
    """`telethon.events.NewMessage.Event` / `MessageEdited.Event`."""

    def __init__(self, chat_id, message):
        self.chat_id = chat_id
        self.message = message


class FakeEntity:
    def __init__(self, id, username):
        self.id = id
        self.username = username


class FakeClient:
    """Resolves the configured channels, collects handlers, fires canned updates."""

    def __init__(self, channels, joined=None):
        self.entities = {handle: FakeEntity(1000 + n, handle)
                         for n, handle in enumerate(channels)}
        self.joined = self.entities.keys() if joined is None else joined
        self.handlers = []
        self.connects = 0
        self.disconnects = 0

    async def get_entity(self, handle):
        if handle not in self.entities:
            raise ValueError(f"no such channel: {handle}")
        return self.entities[handle]

    async def iter_dialogs(self):
        for handle in self.joined:
            yield type("Dialog", (), {"entity": self.entities[handle]})()

    def add_event_handler(self, callback, event=None):
        self.handlers.append(callback)

    async def run_until_disconnected(self):
        self.disconnects += 1

    async def connect(self):
        self.connects += 1

    async def fire(self, handle, message, edit_date=None):
        """Deliver one update, the way Telethon delivers it: to one handler.

        `subscribe` registers the same callback for NewMessage and MessageEdited,
        and Telegram sends an edit as one or the other, never both.
        """
        assert self.handlers and len(set(self.handlers)) == 1, self.handlers
        await self.handlers[0](
            FakeEvent(self.entities[handle].id, FakeMessage(message, edit_date)))


async def feed(client, messages):
    """Every message in the slice, live, in the order the replayer reads them."""
    for message in messages:
        await client.fire(message.channel, message)

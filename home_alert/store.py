"""SQLite audit trail. Written after a push has left, never before it.

It is also a corpus: `replay --from-db` reads a night back out of `messages` and runs
it through the current rules, which is how a rule change is checked against what the
household actually received rather than against the research corpus (SPEC story 34).
"""
import dataclasses
import json
import sqlite3
from datetime import datetime

from .reader import Message

SCHEMA = """
create table if not exists messages (
    channel text, msg_id integer, time text, reply_to integer, text text, parse text,
    edited integer default 0,
    primary key (channel, msg_id));
create table if not exists events (
    tag text primary key, opened text, last text, tier text, title text,
    launches integer, places text, sources text,
    -- the official siren in м. Київ when the event was last written: a signal, never
    -- a gate, kept so "URGENT without a siren" can be counted later (SPEC story 24)
    siren text);
create table if not exists notifications (
    time text, kind text, tier text, title text, body text, tag text);
"""


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        if "edited" not in {row[1] for row in self.db.execute("pragma table_info(messages)")}:
            self.db.execute("alter table messages add column edited integer default 0")
        if "siren" not in {row[1] for row in self.db.execute("pragma table_info(events)")}:
            self.db.execute("alter table events add column siren text")

    def record(self, message, parse, event, pushes, siren=None):
        with self.db:
            self.db.execute(
                "insert or replace into messages "
                "(channel, msg_id, time, reply_to, text, parse, edited) "
                "values (?,?,?,?,?,?,?)",
                (message.channel, message.id, message.time.isoformat(), message.reply_to,
                 message.text, json.dumps(dataclasses.asdict(parse), ensure_ascii=False),
                 message.edited))
            if event:
                self.db.execute(
                    "insert or replace into events values (?,?,?,?,?,?,?,?,?)",
                    (event.tag, event.opened.isoformat(), event.last_launch.isoformat(),
                     event.tier, event.title, event.launches,
                     json.dumps(event.places, ensure_ascii=False),
                     json.dumps(event.sources, ensure_ascii=False),
                     {True: "on", False: "off"}.get(siren)))
            self.db.executemany(
                "insert into notifications values (?,?,?,?,?,?)",
                [(p.time.isoformat(), p.kind, p.tier, p.title, p.body, p.tag) for p in pushes])

    def messages(self, start=None, end=None):
        """A stored night, as the `Message` the corpus reader produces.

        ponytail: an edited message comes back with its final text and the edit flag
        dropped, so the rules run on it -- live they never did (an edit is recorded and
        goes no further, #7). A replay of a night with edits can therefore say more
        than the night did; 47 messages in the whole corpus were edited.
        """
        rows = self.db.execute(
            "select channel, msg_id, time, reply_to, text from messages "
            "where time between ? and ? order by time, channel, msg_id",
            ((start or datetime.min).isoformat(), (end or datetime.max).isoformat()))
        return [Message(channel, msg_id, datetime.fromisoformat(time), reply_to, text)
                for channel, msg_id, time, reply_to, text in rows]

    def record_edit(self, message):
        """A corrected message: new text, flag raised, parse left alone.

        The rules never ran on this text (the spec does not alert on edits), so
        overwriting the parse would make the audit trail claim they had.
        """
        with self.db:
            edited = self.db.execute(
                "update messages set text = ?, edited = 1 where channel = ? and msg_id = ?",
                (message.text, message.channel, message.id))
            if not edited.rowcount:      # edited before we ever saw the original
                self.db.execute(
                    "insert into messages "
                    "(channel, msg_id, time, reply_to, text, parse, edited) "
                    "values (?,?,?,?,?,null,1)",
                    (message.channel, message.id, message.time.isoformat(),
                     message.reply_to, message.text))

"""SQLite audit trail. Written after a push has left, never before it."""
import dataclasses
import json
import sqlite3

SCHEMA = """
create table if not exists messages (
    channel text, msg_id integer, time text, reply_to integer, text text, parse text,
    primary key (channel, msg_id));
create table if not exists events (
    tag text primary key, opened text, last text, tier text, title text,
    launches integer, places text, sources text);
create table if not exists notifications (
    time text, kind text, tier text, title text, body text, tag text);
"""


class Store:
    def __init__(self, path=":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def record(self, message, parse, event, pushes):
        with self.db:
            self.db.execute(
                "insert or replace into messages values (?,?,?,?,?,?)",
                (message.channel, message.id, message.time.isoformat(), message.reply_to,
                 message.text, json.dumps(dataclasses.asdict(parse), ensure_ascii=False)))
            if event:
                self.db.execute(
                    "insert or replace into events values (?,?,?,?,?,?,?,?)",
                    (event.tag, event.opened.isoformat(), event.last_launch.isoformat(),
                     event.tier, event.title, event.launches,
                     json.dumps(sorted(event.places), ensure_ascii=False),
                     json.dumps(sorted(event.sources), ensure_ascii=False)))
            self.db.executemany(
                "insert into notifications values (?,?,?,?,?,?)",
                [(p.time.isoformat(), p.kind, p.tier, p.title, p.body, p.tag) for p in pushes])

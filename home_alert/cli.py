"""`home-alert run` -- follow the live channels. `replay <from> <to>` -- what the
household would have been sent. `add-channel @handle` -- draft a profile for a new
channel and report what the rules make of its history."""
import argparse
import asyncio
import contextlib
import logging
import os
from datetime import datetime
from pathlib import Path

import yaml

from telethon import TelegramClient

from . import add_channel, events, notify, profiles, reader, store


def sink_for(config, ntfy):
    """The one sink both paths use: the console always, ntfy when it is for real."""
    ntfy = notify.Ntfy(config["ntfy"]) if ntfy else None
    console = notify.Console()

    def sink(push):
        console(push)
        if ntfy:
            ntfy(push)

    return sink


def replay(args, config):
    start, end = datetime.fromisoformat(args.start), datetime.fromisoformat(args.end)
    # `--from-db` replays what the live agent stored instead of the research corpus, and
    # records into memory so re-reading a night never appends to the night itself.
    messages = (store.Store(args.db).messages(start, end) if args.from_db
                else reader.read_corpus(args.corpus or config["corpus"], start, end))
    print(f"{len(messages)} messages, {args.start} .. {args.end}")
    events.replay(messages, config, sink_for(config, args.ntfy),
                  store.Store(":memory:" if args.from_db else args.db))


def run(args, config):
    """Live Telegram in, ntfy out. First start prompts for the login; after that the
    session file on the data volume is the login."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Telethon's own DEBUG logs carry request payloads and session state; INFO and
    # above never do, and nothing here logs a token or the session file's contents.
    logging.getLogger("telethon").setLevel(logging.WARNING)

    sink = sink_for(config, ntfy=True)
    # the siren feed has no profile and no weight -- it is read for one bit -- so it is
    # not in the profiles directory and has to be added to the follow list by hand.
    channels = sorted(profiles.load(config["profiles"])) + [events.SIREN_CHANNEL]
    pipeline = events.Pipeline(config, sink, store.Store(args.db or config["db"]))
    client = TelegramClient(config["telegram"]["session"],
                            int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])

    async def follow():
        beat = asyncio.create_task(notify.heartbeat(
            sink, config.get("system", {}).get("heartbeat_min", 360),
            lambda: f"{pipeline.active(notify.now())}/{len(pipeline.channels)}"
                    " каналів активні"))
        try:
            await reader.run(client, channels, pipeline.feed,
                             on_status=lambda why: notify.system(
                                 sink, "Telegram відпав", why))
        finally:
            beat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await beat

    with client:      # prompts for phone + code on first start, reuses the session after
        notify.system(sink, "Агент запущено", f"{len(channels)} каналів")
        try:
            # `client.loop` is Telethon 1.x's own loop handle; fine on the pinned 3.12,
            # and it is what goes when Telethon 2 drops it.
            client.loop.run_until_complete(follow())
        finally:
            notify.system(sink, "Агент зупинено")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="home-alert")
    commands = parser.add_subparsers(dest="command", required=True)
    live = commands.add_parser("run", help="follow the live channels and push for real")
    live.add_argument("--config", default="config.yaml")
    live.add_argument("--db", help="override the configured sqlite file")
    past = commands.add_parser("replay", help="replay a corpus window through the rules")
    past.add_argument("start", help="ISO datetime, UTC, e.g. 2026-08-21T21:54")
    past.add_argument("end", help="ISO datetime, UTC")
    past.add_argument("--config", default="config.yaml")
    past.add_argument("--corpus", help="override the configured corpus path")
    past.add_argument("--db", default=":memory:", help="sqlite file to record into")
    past.add_argument("--from-db", action="store_true",
                      help="replay the messages stored in --db, not the corpus")
    past.add_argument("--ntfy", action="store_true",
                      help="also push to the configured ntfy server for real")
    new = commands.add_parser("add-channel",
                              help="draft a profile for a channel and report coverage")
    new.add_argument("handle", help="the channel, e.g. @kyiv_nebo")
    new.add_argument("--config", default="config.yaml")
    new.add_argument("--history", help="a JSONL history file to read instead of "
                                       "fetching from Telegram")
    new.add_argument("--limit", type=int, default=500,
                     help="how many of the channel's last messages to read")
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    if args.command == "add-channel":
        add_channel.add(args.handle, config, args.history, args.limit)
    else:
        (run if args.command == "run" else replay)(args, config)
    return 0

"""`home-alert run` -- follow the live channels. `replay <from> <to>` -- what the
household would have been sent."""
import argparse
import logging
import os
from datetime import datetime
from pathlib import Path

import yaml

from . import events, notify, profiles, reader, store


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
    messages = reader.read_corpus(args.corpus or config["corpus"],
                                  datetime.fromisoformat(args.start),
                                  datetime.fromisoformat(args.end))
    print(f"{len(messages)} messages, {args.start} .. {args.end}")
    events.replay(messages, config, sink_for(config, args.ntfy), store.Store(args.db))


def run(args, config):
    """Live Telegram in, ntfy out. First start prompts for the login; after that the
    session file on the data volume is the login."""
    from telethon import TelegramClient      # only the live path needs it

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Telethon's own DEBUG logs carry request payloads and session state; INFO and
    # above never do, and nothing here logs a token or the session file's contents.
    logging.getLogger("telethon").setLevel(logging.WARNING)

    channels = sorted(profiles.load(config["profiles"]))
    pipeline = events.Pipeline(config, sink_for(config, ntfy=True),
                               store.Store(args.db or config["db"]))
    client = TelegramClient(config["telegram"]["session"],
                            int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    with client:      # prompts for phone + code on first start, reuses the session after
        client.loop.run_until_complete(reader.run(client, channels, pipeline.feed))


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
    past.add_argument("--ntfy", action="store_true",
                      help="also push to the configured ntfy server for real")
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    (run if args.command == "run" else replay)(args, config)
    return 0

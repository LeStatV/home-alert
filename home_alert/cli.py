"""`home-alert replay <from> <to>` -- what the household would have been sent."""
import argparse
from datetime import datetime
from pathlib import Path

import yaml

from . import events, notify, reader, store


def main(argv=None):
    parser = argparse.ArgumentParser(prog="home-alert")
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("replay", help="replay a corpus window through the rules")
    replay.add_argument("start", help="ISO datetime, UTC, e.g. 2026-08-21T21:54")
    replay.add_argument("end", help="ISO datetime, UTC")
    replay.add_argument("--config", default="config.yaml")
    replay.add_argument("--corpus", help="override the configured corpus path")
    replay.add_argument("--db", default=":memory:", help="sqlite file to record into")
    replay.add_argument("--ntfy", action="store_true",
                        help="also push to the configured ntfy server for real")
    args = parser.parse_args(argv)

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    messages = reader.read_corpus(args.corpus or config["corpus"],
                                  datetime.fromisoformat(args.start),
                                  datetime.fromisoformat(args.end))
    console = notify.Console()
    ntfy = notify.Ntfy(config["ntfy"]) if args.ntfy else None

    def sink(push):
        console(push)
        if ntfy:
            ntfy(push)

    print(f"{len(messages)} messages, {args.start} .. {args.end}")
    events.replay(messages, config, sink, store.Store(args.db))
    return 0

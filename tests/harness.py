"""Seam 1: JSONL corpus slice in at the reader boundary, ntfy pushes out at the sink.

Tests assert ordered ``(time, kind, tier, title)`` tuples and nothing else -- never
event objects, scoring internals or DB rows. The clock is the message timestamps.
"""
from pathlib import Path

import yaml

from home_alert import events, notify, reader, store

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SOUNDS = ("NEW", "PROMOTE", "RESOUND")


def replay(fixture, **overrides):
    """Replay a fixture slice; return every push as (time, kind, tier, title)."""
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["ballistic"].update(overrides)
    recorder = notify.Recorder()
    events.replay(reader.read_corpus(FIXTURES / f"{fixture}.jsonl"), config,
                  recorder, store.Store(":memory:"))
    return [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title) for p in recorder.pushes]


def sounds(fixture, **overrides):
    """Pushes of a sound kind: NEW, PROMOTE, RESOUND. An INFO one is still silent
    (priority 2) -- `audible` is the list the household actually hears."""
    return [p for p in replay(fixture, **overrides) if p[1] in SOUNDS]


def audible(fixture, **overrides):
    """Only the sounds the household actually hears: INFO is priority 2, silent."""
    return [p for p in sounds(fixture, **overrides) if p[2] != "INFO"]

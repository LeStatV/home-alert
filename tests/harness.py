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


def replay(fixture, cooldown_min=None, **overrides):
    """Replay a fixture slice; return every push as (time, kind, tier, title).

    `cooldown_min` overrides the household's per-tier drone cooldowns, e.g.
    `cooldown_min={"URGENT": 30}`; anything else overrides the ballistic knobs.
    """
    return [p[:4] for p in bodies(fixture, cooldown_min, **overrides)]


def bodies(fixture, cooldown_min=None, **overrides):
    """The same pushes as `replay`, plus the body -- where the `>=N` count is shown.
    Titles are asserted exactly; a body is matched loosely, by what it contains."""
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["ballistic"].update(overrides)
    config["drone"]["cooldown_min"].update(cooldown_min or {})
    recorder = notify.Recorder()
    events.replay(reader.read_corpus(FIXTURES / f"{fixture}.jsonl"), config,
                  recorder, store.Store(":memory:"))
    return [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title, p.body)
            for p in recorder.pushes]


def sounds(fixture, **overrides):
    """Pushes of a sound kind: NEW, PROMOTE, RESOUND. An INFO one is still silent
    (priority 2) -- `audible` is the list the household actually hears."""
    return [p for p in replay(fixture, **overrides) if p[1] in SOUNDS]


def audible(fixture, **overrides):
    """Only the sounds the household actually hears: INFO is priority 2, silent."""
    return [p for p in sounds(fixture, **overrides) if p[2] != "INFO"]

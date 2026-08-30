"""`home-alert review [--since 24h]`: what the rules could not type last night, and
what a model proposes doing about it -- as a diff nobody has applied (SPEC story 27).

Two halves, and the first stands on its own. The report reads the stored messages of
the last day back out of SQLite, runs them through the same coverage buckets
`add-channel` uses, and prints per channel what got no type. Then, if and only if a
provider is configured, each channel that has a profile gets its unparsed messages
shown to the model, and whatever survives the same gates `add-channel` puts a draft
through is written to `profiles/reviews/<date>.diff`.

Nothing here writes a profile. The proposals land in a unified diff the owner reads
and applies by hand (`patch -p0`), which is the only way a channel's behaviour ever
changes -- "never auto-applied" is the story, and the byte-identity of `profiles/`
across a run is the test.
"""
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from . import add_channel, llm, notify, profiles, store

UNITS = {"h": "hours", "d": "days"}


def window(text):
    """`24h`, `7d` -- an argparse `type`, so garbage is refused at the command line."""
    try:
        return timedelta(**{UNITS[text[-1]]: float(text[:-1])})
    except (KeyError, ValueError, IndexError) as error:
        raise ValueError(f"--since takes a number of hours or days, e.g. 24h or 7d, "
                         f"not {text!r}") from error


def unparsed(config, db, since):
    """`(channel -> [(message, text)], end)`: what the rules could not type, per
    channel, over the last `since` of what the store holds.

    The window ends at the newest stored message rather than at the wall clock: a
    review run at 04:00 over a night that ended at 03:50 must see that night, and a
    run over a store nobody has written to since Tuesday must say so rather than
    report an empty and reassuring nothing.
    """
    messages = store.Store(db).messages()
    if not messages:
        return {}, None
    end = messages[-1].time         # `store.messages` is ordered by time
    loaded = profiles.load(config["profiles"])
    found = defaultdict(list)
    for channel, group in _by_channel(messages, end - window(since)).items():
        _, missed, _ = add_channel.coverage(group, loaded.get(channel))
        if missed:
            found[channel] = missed
    return dict(found), end


def _by_channel(messages, start):
    groups = defaultdict(list)
    for message in messages:
        if message.time >= start:
            groups[message.channel].append(message)
    return groups


def review(config, db, since="24h", sink=None):
    """The whole command: collect, report, propose, summarize."""
    sink = sink or notify.Console()
    missed, end = unparsed(config, db, since)
    total = sum(len(group) for group in missed.values())
    print(f"\nreview -- the last {since} of {db}, "
          + (f"ending {end:%Y-%m-%dT%H:%M:%S}" if end else "which is empty"))
    for channel, group in sorted(missed.items()):
        print(f"\n@{channel} -- {len(group)} the rules got no type out of:")
        for message, text in group:
            print(f"  {message.time:%Y-%m-%dT%H:%M:%S}  {text}")
    line = (f"{total} unparsed across {len(missed)} channel{'s' * (len(missed) != 1)}, "
            f"0 proposals written")
    print(f"\nreview: {line}")
    notify.system(sink, "review", line)

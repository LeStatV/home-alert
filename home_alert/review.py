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
import argparse
import difflib
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import yaml

from . import add_channel, llm, notify, profiles, store

UNITS = {"h": "hours", "d": "days"}

NOTE = """\
This channel already has a profile. It is printed below; propose only ADDITIONS to
it, and never repeat anything it already carries.
{current}
The messages listed further down are only the ones this profile and the rules could
not type. Every example you propose must be one of them, copied verbatim.
"""

HEADER = """\
# home-alert review, {end:%Y-%m-%d} -- {window} of stored messages, nothing applied.
#
# `profiles/` was not touched: this file is a proposal. Read every hunk, then apply
# the ones you agree with, from the directory holding `{directory}/`:
#
#     patch -p0 -d . < {directory}/reviews/{name}
#
# `git apply` will not take this file -- the lines you are reading are not a patch.
# Every example below has already been run through the classifier with the rest of
# the proposal applied, and only the ones that reproduced their own labels are here
# ({kept} of {proposed} proposed). The rest, and everything else that was dropped:
#
{notes}"""


def window(text):
    """`24h`, `7d` -- an argparse `type`, so garbage is refused at the command line."""
    try:
        return timedelta(**{UNITS[text[-1]]: float(text[:-1])})
    except (KeyError, ValueError, IndexError) as error:
        raise ValueError("--since takes a number of hours or days, e.g. 24h or 7d, "
                         f"not {text!r}") from error


def since(text):
    """The same thing as an argparse `type`: a `--since` nobody can read is an error
    at the command line, not a week-long window discovered in the output.

    `ArgumentTypeError` and not `ValueError`: argparse prints the message of the
    first and replaces the second with `invalid since value`, which tells the owner
    nothing about what a valid one looks like.
    """
    try:
        window(text)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    return text


def collect(config, db, since):
    """`(channel -> (messages, unparsed), end)` over the last `since` of the store.

    The window ends at the newest stored message rather than at the wall clock: a
    review run at 04:00 over a night that ended at 03:50 must see that night, and a
    run over a store nobody has written to since Tuesday must say so rather than
    report an empty and reassuring nothing.

    `unparsed` is `add-channel`'s coverage bucket, not a second definition of the
    same thing: the messages nothing typed -- not their own words, not their reply
    parent, not the channel's 3-minute memory, not its `default_type` -- and not an
    all-clear, which types nothing and is not a miss.
    """
    messages = store.Store(db).messages()
    if not messages:
        return {}, None
    end = messages[-1].time         # `store.messages` is ordered by time
    loaded = profiles.load(config["profiles"])
    groups = defaultdict(list)
    for message in messages:
        if message.time >= end - window(since):
            groups[message.channel].append(message)
    found = {}
    for channel, group in groups.items():
        _, missed, _ = add_channel.coverage(group, loaded.get(channel))
        if missed:
            found[channel] = (group, missed)
    return found, end


# -- the proposal, as an edit to the file the owner wrote ---------------------------

def _dump(obj, indent=0):
    """One YAML fragment in the style the profiles are written in, indented."""
    body = yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=100,
                          default_flow_style=None)
    return [" " * indent + line + "\n" for line in body.splitlines()]


def _item(value):
    """One list item -- `- {text: ..., type: drone}`, `- '^дайджест'`."""
    if isinstance(value, dict):
        body = yaml.safe_dump(value, allow_unicode=True, sort_keys=False,
                              default_flow_style=True, width=1000).strip()
    else:
        # quoted, the way every noise pattern in `profiles/` is written: a regex
        # reads as one thing, and `- '^дайджест'` cannot be mistaken for prose
        body = yaml.safe_dump([value], allow_unicode=True, width=1000,
                              default_style="'").strip()[2:]
    return f"  - {body}\n"


def _block(lines, key, indent):
    """`(first, last)` line indices of `key`'s block, or None when the key is absent.

    A block ends at the next line indented no further than the key itself, so a
    comment indented under an example belongs to it and one at column 0 does not.
    This is why the edits below are line surgery rather than a re-dump of the loaded
    YAML: a profile is a document a human wrote, and its comments are the reasoning
    behind every weight and pattern in it. A round-trip through PyYAML would delete
    all of them and call it a diff.
    """
    head = " " * indent + key + ":"
    for first, line in enumerate(lines):
        if line.startswith(head):
            last = first + 1
            while last < len(lines) and (not lines[last].strip()
                                         or lines[last].startswith(" " * (indent + 1))):
                last += 1
            while last > first + 1 and not lines[last - 1].strip():
                last -= 1       # a trailing blank line separates blocks, it is not one
            return first, last
    return None


def _fresh(lines, block):
    """A key this profile does not have yet, at the end of the file."""
    return lines + ["\n"] + block


def _append(lines, key, items):
    """New items at the end of a list the profile already keeps."""
    block = _block(lines, key, 0)
    if block is None:
        return _fresh(lines, [f"{key}:\n"] + items)
    return lines[:block[1]] + items + lines[block[1]:]


def _extend(lines, key, name, patterns):
    """`type_vocab: {name: [...]}` -- a new name in the mapping, or a name whose line
    is rewritten with the old patterns and the new ones on it. Rewritten and not
    appended: a second `clear:` under `type_vocab:` is a duplicate key, and PyYAML
    keeps the last one, which would silently drop everything the owner had there.
    """
    dumped = _dump({name: patterns}, indent=2)
    block = _block(lines, key, 0)
    if block is None:
        return _fresh(lines, [f"{key}:\n"] + dumped)
    first, last = block
    inner = _block(lines[first + 1:last], name, 2)
    if inner is None:
        return lines[:last] + dumped + lines[last:]
    return lines[:first + 1 + inner[0]] + dumped + lines[first + 1 + inner[1]:]


def merge(text, current, additions):
    """The profile file with the proposals folded in, and nothing else moved."""
    lines = text.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    for key in ("noise_patterns", "examples"):
        if additions.get(key):
            lines = _append(lines, key, [_item(value) for value in additions[key]])
    for key in ("type_vocab", "place_aliases"):
        for name, patterns in (additions.get(key) or {}).items():
            lines = _extend(lines, key, name,
                            list((current.get(key) or {}).get(name) or ()) + patterns)
    return "".join(lines)


# -- what the model may propose ----------------------------------------------------

def _new(proposed, existing, note, what):
    """The patterns this profile does not already carry. A proposal that repeats the
    file back at us is not a change, and a diff that contains one is noise."""
    kept = []
    for pattern in proposed:
        if pattern in (existing or ()):
            note(f"{what} {pattern!r}: the profile already has it")
        else:
            kept.append(pattern)
    return kept


def additions(fields, current, missed, messages, note):
    """The model's validated answer with everything already-known or unsupported
    taken out of it -- the additions, and only the additions.

    The verbatim gate is here: an example whose text is not one of the messages the
    model was shown is an invention, however plausible, and a profile example is
    supposed to be a message this channel actually posted (SPEC "Profiles as data").
    """
    seen = {text for _, text in missed}
    examples = []
    for example in fields["examples"]:
        if example["text"] not in seen:
            note(f"example {example['text'][:40]!r}: not one of the messages under "
                 "review -- an example has to be a message this channel posted")
        elif example["text"] in {e["text"] for e in current.get("examples") or ()}:
            note(f"example {example['text'][:40]!r}: the profile already has it")
        else:
            examples.append(example)
    return {
        "noise_patterns": add_channel.swallowed(
            _new(fields["noise_patterns"], current.get("noise_patterns"), note, "noise"),
            messages, note),
        "type_vocab": {name: kept for name, patterns in fields["type_vocab"].items()
                       if (kept := _new(patterns,
                                        (current.get("type_vocab") or {}).get(name),
                                        note, f"type_vocab {name}"))},
        "place_aliases": {name: kept for name, stems in fields["place_aliases"].items()
                          if (kept := _new(stems,
                                           (current.get("place_aliases") or {}).get(name),
                                           note, f"place_aliases {name}"))},
        "examples": examples,
    }


def propose(channel, path, group, config, client, note):
    """`(diff, examples kept, examples proposed)` for one channel -- diff None when
    there is nothing left to propose.

    The examples go through `add-channel`'s own seam-2 gate, against this profile
    *with the rest of the proposal applied* -- so a new vocabulary word is what makes
    its own example pass, and an example the classifier cannot reproduce is dropped
    here rather than breaking `tests/test_profiles.py` after the owner applies it.
    """
    messages, missed = group
    text = path.read_text(encoding="utf-8")
    current = yaml.safe_load(text)
    answer = client.draft(add_channel.draft_prompt(
        channel, [message for message, _ in missed], config,
        note=NOTE.format(current=text)))
    if answer is None:
        note("the provider did not answer")
        return None, 0, 0
    try:
        fields = add_channel.validate(answer, note)
    except Exception as error:      # noqa: BLE001 -- fail-open, as everywhere the LLM
        note(f"the answer could not be read ({type(error).__name__})")
        fields = None
    if fields is None:
        note("the provider did not answer with usable JSON")
        return None, 0, 0
    print(f"\nnoise patterns proposed for @{channel}, over the {len(messages)} "
          "messages in the window:")
    new = additions(fields, current, missed, messages, note)
    proposed = new.pop("examples")
    new["examples"] = add_channel.approved(
        add_channel.profile_of(_merged(current, new, channel)), proposed, note)
    if not any(new.values()):
        return None, 0, len(proposed)
    name = f"{Path(config['profiles']).name}/{path.name}"
    return ("".join(difflib.unified_diff(text.splitlines(keepends=True),
                                         merge(text, current, new).splitlines(True),
                                         fromfile=name, tofile=name)),
            len(new["examples"]), len(proposed))


def _merged(current, new, channel):
    """This profile as it would be with the proposal applied -- what the examples are
    checked against, so a new vocabulary word is what makes its own example pass."""
    merged = dict(current) | {"channel": channel, "examples": []}
    merged["noise_patterns"] = list(current.get("noise_patterns") or ()) + \
        new["noise_patterns"]
    for key in ("type_vocab", "place_aliases"):
        merged[key] = (current.get(key) or {}) | {
            name: list((current.get(key) or {}).get(name) or ()) + patterns
            for name, patterns in new[key].items()}
    return merged


def review(config, db, since="24h", sink=None):
    """The whole command: collect, report, propose, summarize."""
    sink = sink or notify.Console()
    directory = Path(config["profiles"])
    collected, end = collect(config, db, since)
    total = sum(len(missed) for _, missed in collected.values())
    print(f"\nreview -- the last {since} of {db}, "
          + (f"ending {end:%Y-%m-%dT%H:%M:%S}" if end else "which is empty"))
    for channel, (_, missed) in sorted(collected.items()):
        print(f"\n@{channel} -- {len(missed)} the rules got no type out of:")
        for message, text in missed:
            print(f"  {message.time:%Y-%m-%dT%H:%M:%S}  {text}")

    client = llm.client(config.get("llm"))
    if client is None and collected:
        print("\nno LLM provider configured (llm.provider: none) -- the report above "
              "is the whole run.\nSet `llm.provider` to have the unparsed messages "
              "turned into proposed profile changes.")
    chunks, notes, kept, proposed = [], [], 0, 0
    for channel, group in sorted(collected.items()) if client else ():
        path = directory / f"{channel}.yaml"
        if not path.exists():
            notes.append(f"@{channel}: no profile to propose changes to -- "
                         f"`home-alert add-channel @{channel}` writes one")
            continue
        said = []
        chunk, agreed, asked = propose(channel, path, group, config, client, said.append)
        kept, proposed = kept + agreed, proposed + asked
        notes += [f"@{channel}: {line}" for line in said]
        if chunk:
            chunks.append(chunk)
        else:
            notes.append(f"@{channel}: nothing left to propose")
    file = _write(directory, end, since, chunks, notes, kept, proposed)
    line = (f"{total} unparsed across {len(collected)} "
            f"channel{'s' * (len(collected) != 1)}, "
            f"{len(chunks)} proposal{'s' * (len(chunks) != 1)} written")
    if notes:
        print(f"\nnotes ({len(notes)}):")
        for note in notes:
            print(f"  {note}")
    if file:
        print(f"\nwrote {file} -- read it, then `patch -p0 -d {directory.parent}` "
              "the hunks you agree with. Nothing in `profiles/` has changed.")
    print(f"\nreview: {line}")
    notify.system(sink, "review", line)
    return file


def _write(directory, end, since, chunks, notes, kept, proposed):
    """The review file, or None when there was nothing to propose."""
    if not chunks:
        return None
    file = directory / "reviews" / f"{end:%Y-%m-%d}.diff"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        HEADER.format(end=end, window=since, directory=directory.name, name=file.name,
                      kept=kept, proposed=proposed,
                      notes="".join(f"#   {note}\n" for note in notes) or "#   nothing\n")
        + "\n" + "".join(chunks), encoding="utf-8")
    return file

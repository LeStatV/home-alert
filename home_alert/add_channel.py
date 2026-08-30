"""`add-channel @handle`: fetch a channel's history, see what the rules make of it,
and leave a draft profile for the owner to read (SPEC story 26).

Nothing here goes live. The draft lands in `profiles/drafts/`, which `profiles.load`
does not look in, and it carries `weight: null`, which `profiles.load` refuses by
name -- so a channel is added by a human editing the draft and moving it, twice over.

This command needs no ntfy and no database: it reads Telegram (or a history file the
owner already has) and writes one YAML file.
"""
import asyncio
import json
import os
import re
import tempfile
import time
from collections import Counter
from pathlib import Path

import yaml

from . import llm, profiles, reader, rules
from .context import Context

UNPARSED_SHOWN = 50      # the rest is a count: an unparsed list can be 400 lines long
PROMPT_MESSAGES = 400    # how many of the fetched messages the model is shown
NOISE_BUDGET = 1.0       # seconds one noise pattern may spend on the whole history
EXAMPLE_FIELDS = {"type", "stage", "places", "count", "noise"}
CANONICAL = frozenset(rules.PLACES.values())   # the only names a place_alias may map to

HEADER = """\
# DRAFT profile for @{channel}, written by `home-alert add-channel`. Not live, and
# not approved by anybody: an LLM wrote most of what is below by reading {count}
# of this channel's messages. To put the channel on the air:
#
#   1. read every line, and every example -- the examples run as tests
#   2. set the weight (0.0-1.0): >=0.8 wakes the house alone, >=0.6 may launch alone
#   3. set `default_type` if a bare place name from this channel means a threat type
#      (kyiv_nebo: drone -- without it 88% of that channel is inert)
#   4. move this file to `profiles/{channel}.yaml` and commit it
#
# Until then nothing reads it: `profiles.load` does not look in this directory, and
# a draft moved up with the weight still unset is refused at startup by name.
"""


def history(handle, config, path=None, limit=500):
    """The channel's last `limit` messages, oldest first.

    `path` is a JSONL history the owner already has -- the research corpus is exactly
    that, which is how this command is verified without credentials. Without it the
    messages come from Telegram through the same session and the same `normalize` the
    live agent uses, so a fetched message and a live one are the same `Message`.

    One channel's history, or nothing: `read_corpus` also reads a whole corpus
    *directory*, which is what `config.yaml: corpus` names and so exactly what gets
    pasted in here -- and six channels' messages under one channel's name make a
    report that looks right and is not (six channels' replies decide this one's
    `threads_by_reply`, five channels' typed messages hide its unparsed ones).
    """
    if not path:
        return asyncio.run(_fetch(handle, config, limit))
    messages = reader.read_corpus(path)
    # not `m.channel == handle`: `read_corpus` names a message after its file, so a
    # renamed single-channel dump would filter down to nothing and report on silence.
    found = sorted({message.channel for message in messages})
    assert len(found) <= 1, (
        f"{path} holds {len(found)} channels ({', '.join(found)}) -- --history takes "
        "one channel's history file, not a corpus directory")
    return messages[-limit:]


async def _fetch(handle, config, limit):
    """Telethon, the #7 session, newest-first turned into chronological order.

    ponytail: owner-verified -- there are no Telegram credentials on a build machine,
    so this path has no test. Everything below it takes messages, not a client.
    """
    from telethon import TelegramClient        # noqa: PLC0415 -- only the fetch needs it

    client = TelegramClient(config["telegram"]["session"],
                            int(os.environ["TG_API_ID"]), os.environ["TG_API_HASH"])
    async with client:
        entity = await client.get_entity(handle)
        fetched = [message async for message in client.iter_messages(entity, limit=limit)]
    return [reader.normalize(message, handle) for message in reversed(fetched)]


def coverage(messages, profile):
    """What the rules make of a history: `(labels, unparsed, noise)`.

    The same order the live agent uses -- noise, then context, then the rules -- so
    the report is what the agent would actually have made of these messages, memory
    and all. A message is `classified` when something typed it (its own words, its
    reply parent, the channel's 3-minute memory, or the profile's `default_type`) or
    when it is an all-clear, which types nothing but is not a miss. Everything else
    is unparsed, and that list is the point of the report: on a channel with no
    profile the bare place names pile up in it, which is what `default_type` is for.
    """
    context = Context()
    labels, unparsed, noise = Counter(), [], []
    for message in messages:
        text = " ".join(message.text.split())
        parse = rules.classify(text, profile)
        if not text or parse.is_noise:
            noise.append((message, text))
            continue
        # a bump (the same text re-posted as a reply) is counted like any other post
        # here: the report is about what the rules can read, not about what the agent
        # would push.
        _, kind = context.assemble(message, text, parse)
        # an all-clear first: it types nothing and never should, and a channel with
        # `default_type` would otherwise have every «Більше не летить» read as a drone
        label = ("clear" if parse.is_clear else None) or kind or (
            profile.default_type if profile else None)
        if label:
            labels[label] += 1
        else:
            unparsed.append((message, text))
    return labels, unparsed, noise


def _percent(count, total):
    return f"{100 * count / total:5.1f}%" if total else "    -"


def report(handle, messages, profile, source):
    """The coverage report, on stdout, for a human to read once."""
    total = len(messages)
    replies = sum(1 for message in messages if message.reply_to)
    print(f"\n@{handle} -- {total} messages from {source}")
    if not total:
        return Counter(), []
    print(f"{messages[0].time:%Y-%m-%dT%H:%M:%S} .. {messages[-1].time:%Y-%m-%dT%H:%M:%S}"
          f" -- {replies}/{total} replies"
          f" (threads_by_reply: {str(replies > total // 10).lower()})")
    labels, unparsed, noise = coverage(messages, profile)
    classified = sum(labels.values())
    print("\ncoverage" + (f" (with profiles/{handle}.yaml" if profile
                          else " (no profile yet -- the global rules only")
          + ", in 3-min channel context)")
    print(f"  classified      {classified:5d} {_percent(classified, total)}   "
          + " * ".join(f"{name} {count}" for name, count in labels.most_common()))
    print(f"  unparsed        {len(unparsed):5d} {_percent(len(unparsed), total)}")
    print(f"  suspected noise {len(noise):5d} {_percent(len(noise), total)}")
    if unparsed:
        print(f"\nunparsed -- the rules got no type out of these "
              f"(first {min(UNPARSED_SHOWN, len(unparsed))} of {len(unparsed)}):")
        for message, text in unparsed[:UNPARSED_SHOWN]:
            print(f"  {message.time:%Y-%m-%dT%H:%M:%S}  {text}")
        if len(unparsed) > UNPARSED_SHOWN:
            print(f"  ... and {len(unparsed) - UNPARSED_SHOWN} more")
    return labels, unparsed


PROMPT = """\
Channel: @{channel}
{note}The household is in Kyiv. HOME places: {home}. NEARBY places: {nearby}.
Vocabulary names you may extend, and no others: {vocab}
Canonical place names, the only keys `place_aliases` may take: {places}

Answer with one JSON object with these keys:
  "noise_patterns": [regex]     -- this channel's ads, essays, digests, asides. Never
                                   its threat reports.
  "type_vocab": {{name: [regex]}} -- wording *this* channel uses for one of the
                                   vocabularies above that the global rules would
                                   miss, e.g. its own way of saying "it is over".
  "place_aliases": {{canonical: [regex stem]}} -- this channel's own spellings and
                                   typos of a canonical place above.
  "examples": [{{"text": a message copied verbatim from below,
                "type": "drone"|"missile"|"ballistic"|"recon"|null,
                "stage": "threat"|"launch"|"clear"|"trajectory"|null,
                "places": [canonical], "count": integer}}]
                                -- about 30, covering every kind of message this
                                   channel posts. `count` is the figure the message
                                   states about itself. Use null for anything you are
                                   not asserting; every example is run through the
                                   rules and a wrong one is thrown away.

{shown} messages from @{channel}:
{messages}"""


def draft_prompt(handle, messages, config, note=""):
    """What the model is shown: the household's geometry, the vocabulary it may
    extend, the gazetteer it may not add to, and the channel's own messages.

    `note` is what `review` adds -- the profile the channel already has, and the fact
    that the messages below it are only the ones nothing could type. The rest of the
    prompt is the same in both commands on purpose: it is the same answer shape, put
    through the same validation, and a second copy of it would drift.
    """
    shown = messages[-PROMPT_MESSAGES:]
    # 200 characters each: `_item` in `review.py` dumps a proposed example on one
    # line (`width=1000`), which is only safe because no message the model was shown
    # -- and so no verbatim example -- is longer than this.
    return PROMPT.format(
        channel=handle, note=note, home=", ".join(config.get("home") or ()),
        nearby=", ".join(config.get("nearby") or ()),
        vocab=", ".join(rules.VOCAB), places=", ".join(sorted(CANONICAL)),
        shown=len(shown),
        messages="\n".join(f"{message.time:%Y-%m-%d %H:%M} "
                            f"{' '.join(message.text.split())[:200]}"
                            for message in shown))


def _patterns(patterns, note, what):
    """Only the ones that are regexes -- a pattern that does not compile takes the
    whole profile down at load time, which is a bad way to learn about a typo.

    Compiled joined, because `profiles._compile` joins them with `|`: a pattern that
    is fine alone and poisonous in a group (`(?i)`) has to be caught here too.
    """
    kept = []
    for pattern in patterns if isinstance(patterns, list) else ():
        try:
            re.compile("|".join(kept + [str(pattern)]), re.I)
        except re.error as error:
            note(f"{what} {pattern!r}: not a regex ({error.msg})")
        else:
            kept.append(str(pattern))
    return kept


def validate(answer, note):
    """The model's answer as profile fields the schema accepts, or None if it is not
    JSON at all. Everything that does not validate is dropped and noted: the model is
    a drafting tool, and the only thing standing between it and `profiles/` is this.
    """
    found = re.search(r"\{.*\}", answer or "", re.S)
    if not found:
        return None
    data = json.loads(found.group())
    vocab = {}
    for name, patterns in (data.get("type_vocab") or {}).items():
        if name not in rules.VOCAB:
            note(f"type_vocab {name!r}: the rules have no such vocabulary")
        elif kept := _patterns(patterns, note, f"type_vocab {name}"):
            vocab[name] = kept
    aliases = {}
    for canonical, stems in (data.get("place_aliases") or {}).items():
        if canonical not in CANONICAL:
            note(f"place_aliases {canonical!r}: not a place the gazetteer knows -- "
                 "add it to rules.PLACES first if the household needs it")
        elif kept := _patterns(stems, note, f"place_aliases {canonical}"):
            aliases[canonical] = kept
    return {"noise_patterns": _patterns(data.get("noise_patterns"), note, "noise"),
            "type_vocab": vocab, "place_aliases": aliases,
            "examples": _examples(data.get("examples"), note)}


def _examples(examples, note):
    """Proposed examples, unlabelled fields dropped. A `null` is "not asserting this",
    the way the §7 draft and the seam-2 test both read it -- an example asserting
    nothing at all is no example."""
    kept = []
    for example in examples if isinstance(examples, list) else ():
        if not isinstance(example, dict):
            note(f"example {str(example)[:40]!r}: not an object")
            continue
        text = " ".join(str(example.get("text") or "").split())
        listed = {field: value for field, value in example.items()
                  if field != "text" and value is not None}
        if unknown := set(listed) - EXAMPLE_FIELDS:
            note(f"example {text[:40]!r}: no such field(s) {sorted(unknown)}")
        elif text and listed:
            kept.append({"text": text} | listed)
    return kept


def swallowed(patterns, messages, note):
    r"""The accepted noise patterns, each with what it would silence out of this
    history noted next to it -- a pattern nobody has run is a guess, and `.*` reads
    as `500/500` rather than as a plausible line of YAML.

    A pattern that cannot get through the history inside `NOISE_BUDGET` is dropped:
    `^(\w+\s?)+$` compiles fine, backtracks for 40 s on one of kyiv_nebo's messages,
    and the live path would run it on every post the channel ever makes.

    ponytail: the budget is checked between messages, so it bounds the whole scan at
    one message's worst case, not at a second -- a single catastrophic match still
    runs to completion, because `re` cannot be interrupted. Bounding one match needs
    the scan in another process, which is a lot of machinery for an offline command
    that is already showing the owner the number.
    """
    kept = []
    for pattern in patterns:
        compiled, started, hits = re.compile(pattern, re.I), time.monotonic(), 0
        for message in messages:
            hits += bool(compiled.search(message.text))
            if time.monotonic() - started > NOISE_BUDGET:
                note(f"noise {pattern!r}: more than {NOISE_BUDGET:g}s over this "
                     "history -- too slow to run on every post the channel makes")
                hits = None
                break
        if hits is not None:
            # a note and not a `print`: `review` runs from cron at 05:17 with stdout
            # going nowhere, and `noise '.': silences 47/47` is the one line standing
            # between the owner and a silenced channel
            note(f"noise {pattern!r}: silences {hits}/{len(messages)} of them")
            kept.append(pattern)
    return kept


def profile_of(draft):
    """The draft as a real `Profile`, through the real loader -- with a weight, since
    the loader refuses a draft without one, which is the whole point of the draft."""
    with tempfile.TemporaryDirectory() as temporary:
        file = Path(temporary) / f"{draft['channel']}.yaml"
        file.write_text(yaml.safe_dump(draft | {"weight": 0.0}, allow_unicode=True),
                        encoding="utf-8")
        return profiles.load(temporary)[draft["channel"]]


def approved(profile, examples, note):
    """The proposed examples the rules actually agree with (#10 AC1).

    Whatever the model labelled, each example goes through the same classifier the
    seam-2 test runs, with this draft's own vocabulary and aliases, and only the ones
    that reproduce their own labels are written. An example nobody can reproduce is
    not a test, it is a claim.
    """
    kept = []
    for example in examples:
        parse = rules.classify(example["text"], profile)
        got = {"type": rules.type_of(parse, profile.default_type),
               "stage": rules.stage(parse), "places": list(parse.places),
               "count": parse.count, "noise": parse.is_noise}
        listed = {field: value for field, value in example.items() if field != "text"}
        wrong = {field: (value, got[field]) for field, value in listed.items()
                 if got[field] != value}
        if wrong:
            note(f"example {example['text'][:40]!r}: the rules say "
                 + ", ".join(f"{field} {mine!r}, not {theirs!r}"
                             for field, (theirs, mine) in wrong.items()))
        else:
            kept.append(example)
    return kept


def write_draft(handle, answer, messages, directory, note):
    """The validated draft on disk, or None if there was nothing to write."""
    try:
        fields = validate(answer, note)
    except Exception as error:      # noqa: BLE001 -- fail-open, as everywhere the LLM
        # An answer can be prose with a brace in it, JSON cut off mid-sentence, or
        # JSON of an entirely different shape. The coverage report has already been
        # printed by now and it is worth having on its own (#10 AC4).
        note(f"the answer could not be read ({type(error).__name__})")
        fields = None
    if fields is None:
        print("\nthe provider did not answer with usable JSON -- profile drafting "
              "skipped.")
        return None
    print(f"\nnoise patterns, over the same {len(messages)} messages:")
    fields["noise_patterns"] = swallowed(fields["noise_patterns"], messages, note)
    replies = sum(1 for message in messages if message.reply_to)
    draft = {"channel": handle, "weight": None, "language": "uk",
             # derived, not asked: the history says this outright
             "threads_by_reply": replies > len(messages) // 10,
             "default_type": None} | fields
    proposed = draft.pop("examples")
    draft["examples"] = approved(profile_of(draft | {"examples": []}), proposed, note)
    print(f"\nexamples: kept {len(draft['examples'])} of {len(proposed)} proposed"
          f" ({len(proposed) - len(draft['examples'])} dropped, the rules disagreed)")
    file = directory / "drafts" / f"{handle}.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(HEADER.format(channel=handle, count=len(messages))
                    + yaml.safe_dump(draft, allow_unicode=True, sort_keys=False,
                                     width=100),
                    encoding="utf-8")
    return file


def add(handle, config, history_path=None, limit=500):
    """The whole command: fetch, report, draft. No ntfy, no database."""
    handle = handle.lstrip("@")
    directory = Path(config["profiles"])
    file = directory / f"{handle}.yaml"
    existing = profiles.load(directory)[handle] if file.exists() else None
    messages = history(handle, config, history_path, limit)
    report(handle, messages, existing, history_path or "Telegram")
    if not messages:
        print("\nno messages -- nothing to draft from.")
        return None

    client = llm.client(config.get("llm"))
    if client is None:
        print("\nno LLM provider configured (llm.provider: none) -- profile drafting "
              "skipped.\nThe coverage report above stands on its own; set "
              "`llm.provider` to draft a profile.")
        return None
    notes = []
    answer = client.draft(draft_prompt(handle, messages, config))
    if answer is None:
        print("\nthe provider did not answer -- profile drafting skipped.")
        return None
    written = write_draft(handle, answer, messages, directory, notes.append)
    if notes:
        print(f"\nnotes on the draft ({len(notes)}):")
        for line in notes:
            print(f"  {line}")
    if written:
        print(f"\nwrote {written} -- read it, set the weight, and move it to "
              f"{directory / (handle + '.yaml')} to put the channel on the air.")
    return written

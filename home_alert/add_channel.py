"""`add-channel @handle`: fetch a channel's history, see what the rules make of it,
and leave a draft profile for the owner to read (SPEC story 26).

Nothing here goes live. The draft lands in `profiles/drafts/`, which `profiles.load`
does not look in, and it carries `weight: null`, which `profiles.load` refuses by
name -- so a channel is added by a human editing the draft and moving it, twice over.

This command needs no ntfy and no database: it reads Telegram (or a history file the
owner already has) and writes one YAML file.
"""
import asyncio
import os
from collections import Counter
from pathlib import Path

from . import profiles, reader, rules
from .context import Context

UNPARSED_SHOWN = 50      # the rest is a count: an unparsed list can be 400 lines long


def history(handle, config, path=None, limit=500):
    """The channel's last `limit` messages, oldest first.

    `path` is a JSONL history the owner already has -- the research corpus is exactly
    that, which is how this command is verified without credentials. Without it the
    messages come from Telegram through the same session and the same `normalize` the
    live agent uses, so a fetched message and a live one are the same `Message`.
    """
    if path:
        return reader.read_corpus(path)[-limit:]
    return asyncio.run(_fetch(handle, config, limit))


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
    print("\ncoverage" + (f" (with profiles/{handle}.yaml)" if profile
                          else " (no profile yet -- the global rules only)"))
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


def add(handle, config, history_path=None, limit=500):
    """The whole command: fetch, report, draft."""
    handle = handle.lstrip("@")
    directory = Path(config["profiles"])
    file = directory / f"{handle}.yaml"
    existing = profiles.load(directory)[handle] if file.exists() else None
    messages = history(handle, config, history_path, limit)
    report(handle, messages, existing, history_path or "Telegram")
    print("\nno LLM provider configured (llm.provider: none) -- profile drafting "
          "skipped.\nThe coverage report above stands on its own; set `llm.provider` "
          "to draft a profile.")

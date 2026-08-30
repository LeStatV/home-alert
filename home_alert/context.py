"""Context assembly -- reading a terse, threaded channel the way a human does.

A monitoring channel does not repeat itself. `ЦІЛЬ` is followed by a bare `КИЇВ`,
a reply carries only what changed (`1х далі Білогородка`), and the same fact gets
re-posted as a reply to push it back up the feed. Two memories per channel turn
that back into whole messages: the reply chain, and the type the channel is
currently talking about.
"""
from dataclasses import replace
from datetime import timedelta

# ponytail: the spec names two windows -- a 45 s burst and a ~3 min current-type
# memory -- but for typing a bare post they are one mechanism at two lengths, and
# the burst is inside the memory. So there is one window. If the burst ever needs to
# do something the memory must not (attribute a count to *this* launch, say), that is
# when it earns its own constant.
MEMORY = timedelta(minutes=3)


def kind(parse):
    """The threat type a message states in its own words, or None if it states none."""
    if parse.is_drone:
        return "drone"
    if parse.names_ballistic or parse.is_launch or parse.is_threat:
        return "ballistic"
    return None


class Context:
    """Per-channel memory. One instance per run, fed every message in time order."""

    def __init__(self):
        self.texts = {}      # (channel, id) -> text, so a repost can be recognised
        self.kinds = {}      # (channel, id) -> resolved type, for the reply chain
        self.current = {}    # channel -> (time, type) of its last message that said one

    def assemble(self, message, text, parse):
        """The parse in context, or None when the message is a bump (nothing new).

        A message that names no type takes one from its reply parent, else from what
        its channel was talking about up to `MEMORY` ago. Only the type is inherited:
        places, launch wording and the non-Kyiv flag are always the message's own.
        """
        key = (message.channel, message.id)
        parent = (message.channel, message.reply_to)
        bump = self.texts.get(parent) == text
        self.texts[key] = text

        own = kind(parse)
        if own is not None:
            self.current[message.channel] = (message.time, own)
            self.kinds[key] = own
            return None if bump else parse

        inherited = self.kinds.get(parent)
        if inherited is None:
            remembered = self.current.get(message.channel)
            if remembered and message.time - remembered[0] <= MEMORY:
                inherited = remembered[1]
        self.kinds[key] = inherited

        if bump:
            return None
        if inherited == "drone":
            return replace(parse, is_drone=True)
        if inherited == "ballistic":
            return replace(parse, names_ballistic=True)
        return parse

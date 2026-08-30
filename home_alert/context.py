"""Context assembly -- reading a terse, threaded channel the way a human does.

A monitoring channel does not repeat itself. `ЦІЛЬ` is followed by a bare `КИЇВ`,
a reply carries only what changed (`1х далі Білогородка`), and the same fact gets
re-posted as a reply to push it back up the feed. Two memories per channel turn
that back into whole messages: the reply chain, and the type the channel is
currently talking about.
"""
from datetime import timedelta

# ponytail: the spec names two windows -- a 45 s burst and a ~3 min current-type
# memory -- but for typing a bare post they are one mechanism at two lengths, and
# the burst is inside the memory. So there is one window. If the burst ever needs to
# do something the memory must not (attribute a count to *this* launch, say), that is
# when it earns its own constant.
MEMORY = timedelta(minutes=3)


def kind(parse):
    """The threat type a message states in its own words, or None if it states none.

    A message carrying both (`🅿️ Одеса 4х мгКР Бандероль над містом.`) reads as a
    drone; when #5 gives cruise missiles their own tier this needs a real precedence.
    """
    if parse.is_drone:
        return "drone"
    if parse.names_ballistic or parse.is_launch or parse.is_threat:
        return "ballistic"
    return None


class Context:
    """Per-channel memory. One instance per run, fed every non-noise message in order."""

    def __init__(self):
        self.seen = {}       # (channel, id) -> (time, text, resolved type), pruned
        self.current = {}    # channel -> (time, type) of its last message that said one

    def assemble(self, message, text, parse):
        """`(parse, type)` in context, or `(None, None)` when the message is a bump.

        A bump is the same text re-posted as a reply -- the same fact twice. The type is
        resolved from the message's own words first, else the reply parent, else what
        the channel was talking about up to `MEMORY` ago; drone events read it to tell
        a bare `Нивки` from a bare trajectory call.

        ponytail: a bump whose parent fell out of the window -- older than `MEMORY`,
        or posted before this replay/process started -- is not recognised as one. That
        is the same 3 minutes after which a re-post is a fresh report anyway.
        """
        self.seen = {k: v for k, v in self.seen.items()
                     if message.time - v[0] <= MEMORY}
        parent = self.seen.get((message.channel, message.reply_to))

        resolved = kind(parse)
        if resolved is not None:
            self.current[message.channel] = (message.time, resolved)
        else:
            resolved = parent[2] if parent else None
        if resolved is None:
            remembered = self.current.get(message.channel)
            if remembered and message.time - remembered[0] <= MEMORY:
                resolved = remembered[1]

        self.seen[(message.channel, message.id)] = (message.time, text, resolved)
        if parent and parent[1] == text:
            return None, None
        return parse, resolved

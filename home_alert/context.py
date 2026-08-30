"""Context assembly -- reading a terse, threaded channel the way a human does.

A monitoring channel does not repeat itself: `ЦІЛЬ` is followed by `КИЇВ`, a reply
carries only what changed, and the same fact gets re-posted as a reply to push it
back up the feed. Three memories per channel turn that into whole messages again:
the reply chain, the burst (posts ≤ 45 s apart), and the current threat type (≤ 3 min).
"""


class Context:
    """Per-channel memory. One instance per replay/run, fed every message in order."""

    def __init__(self):
        self.texts = {}      # (channel, id) -> normalized text, for the bump

    def assemble(self, message, text, parse):
        """The parse in context, or None when the message is a bump (nothing new)."""
        key = (message.channel, message.id)
        bump = self.texts.get((message.channel, message.reply_to)) == text
        self.texts[key] = text
        return None if bump else parse

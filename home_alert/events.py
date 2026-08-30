"""The ballistic three-stage state machine: messages in, ntfy pushes out.

One active event at a time. The clock is the message timestamps, so `replay` and
the live path run the identical code.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import rules
from .context import Context
from .notify import Push

# Fixed by the spec, not by the household -- only the resound gap is tunable.
LAUNCH_WEIGHT_MIN = 0.6          # a launch on Kyiv from any channel this trusted is URGENT
THREAT_WINDOW = timedelta(minutes=15)
PENDING_TTL = timedelta(seconds=90)   # a launch nobody gave a target stops mattering
EVENT_TTL = timedelta(minutes=5)      # an event closes after this long without launches

THREAT_TITLE = "Загроза балістики"
PENDING_TITLE = "Пуск балістики, ціль уточнюється"
CONFIRMED_TITLE = "БАЛІСТИКА на Київ"


@dataclass
class Event:
    opened: datetime
    last_launch: datetime    # drives the close: the spec closes on launches, not chatter
    sounded: datetime        # last push that made a noise
    pending: bool            # a launch whose target has not been named yet
    launches: int = 1
    places: set = field(default_factory=set)
    sources: set = field(default_factory=set)

    @property
    def tier(self):
        return "WATCH" if self.pending else "URGENT"

    @property
    def title(self):
        return PENDING_TITLE if self.pending else CONFIRMED_TITLE

    @property
    def tag(self):
        return f"bal-{self.opened:%Y%m%dT%H%M%S}"


def replay(messages, config, sink, store=None):
    """Feed messages through the rules and push what the household would have seen."""
    weights = config["channels"]
    resound_gap = timedelta(minutes=config["ballistic"]["resound_gap_min"])

    event = None
    threat_until = None
    context = Context()

    for message in messages:
        text = " ".join(message.text.split())
        parse = rules.classify(text)
        in_context = context.assemble(message, text, parse)
        pushes = []

        def emit(kind, tier, title):
            push = Push(message.time, kind, tier, title,
                        f"{message.channel}: {text[:120]}",
                        event.tag if event else f"threat-{message.time:%Y%m%dT%H%M%S}")
            sink(push)
            pushes.append(push)

        def done():
            if store:
                store.record(message, parse, event, pushes)

        # a bump -- the same text re-posted as a reply -- is the same fact twice
        if not text or parse.is_noise or in_context is None:
            done()
            continue
        parse = in_context

        # the message clock closes stale events and expires unconfirmed launches
        if event and message.time - event.last_launch > EVENT_TTL:
            event = None
        if event and event.pending and message.time - event.opened > PENDING_TTL:
            event = None

        # -- stage 1: declared threat -> one silent INFO per window
        if parse.is_threat:
            # a threat during a live event is noise: the household is already alarmed
            if event is None and (threat_until is None or message.time > threat_until):
                emit("NEW", "INFO", THREAT_TITLE)
            threat_until = message.time + THREAT_WINDOW
            done()
            continue

        ballistic_context = (parse.names_ballistic or event is not None
                             or (threat_until is not None and message.time <= threat_until))

        # -- stage 2: launch
        # a drone report is never a ballistic launch, however much it reads like one
        # ("1 Заворичі на вихід" names Київщина and matches the launch vocabulary)
        if (parse.is_launch and (ballistic_context or parse.places)
                and (parse.names_ballistic or not parse.is_drone)
                and weights.get(message.channel, 0.0) >= LAUNCH_WEIGHT_MIN):
            if parse.names_non_kyiv:
                done()          # a launch on another city: its own, log-only event
                continue
            if event is None:
                event = Event(message.time, message.time, message.time,
                              pending=not parse.places, places=set(parse.places),
                              sources={message.channel})
                emit("NEW", event.tier, event.title)
            else:
                event.launches += 1
                event.last_launch = message.time
                event.places |= set(parse.places)
                event.sources.add(message.channel)
                if event.pending and parse.places:
                    event.pending = False
                    event.sounded = message.time
                    emit("PROMOTE", "URGENT", CONFIRMED_TITLE)
                elif not event.pending and message.time - event.sounded >= resound_gap:
                    event.sounded = message.time
                    emit("RESOUND", "URGENT", CONFIRMED_TITLE)
                else:
                    emit("UPDATE", event.tier, event.title)
            done()
            continue

        # -- stage 3: trajectory -- bare place names while the event is live
        if (event and parse.places and parse.terse
                and not parse.names_non_kyiv and not parse.is_drone and not parse.is_recon):
            event.places |= set(parse.places)
            event.sources.add(message.channel)
            if event.pending:
                event.pending = False
                event.sounded = message.time
                emit("PROMOTE", "URGENT", CONFIRMED_TITLE)
            else:
                emit("UPDATE", "URGENT", CONFIRMED_TITLE)
            done()
            continue

        # -- stage 4: impact / all-clear -- body update only, never a sound
        if event and parse.is_clear:
            emit("UPDATE", event.tier, event.title)
            done()
            continue

        done()

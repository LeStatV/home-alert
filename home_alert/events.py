"""The ballistic three-stage state machine: messages in, ntfy pushes out.

One active event at a time. The clock is the message timestamps, so `replay` and
the live path run the identical code.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import rules
from .notify import Push

THREAT_TITLE = "Загроза балістики"
PENDING_TITLE = "Пуск балістики, ціль уточнюється"
CONFIRMED_TITLE = "БАЛІСТИКА на Київ"


@dataclass
class Event:
    opened: datetime
    last: datetime           # last launch/trajectory report -- the event's liveness
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
    settings = config["ballistic"]
    weights = config["channels"]
    threat_window = timedelta(minutes=settings["threat_window_min"])
    pending_ttl = timedelta(seconds=settings["pending_ttl_s"])
    event_ttl = timedelta(minutes=settings["event_ttl_min"])
    resound_gap = timedelta(minutes=settings["resound_gap_min"])

    event = None
    threat_until = None

    for message in messages:
        text = " ".join(message.text.split())
        parse = rules.classify(text)
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

        if not text or parse.is_noise:
            done()
            continue

        # the message clock closes stale events and expires unconfirmed launches
        if event and message.time - event.last > event_ttl:
            event = None
        if event and event.pending and message.time - event.opened > pending_ttl:
            event = None

        # -- stage 1: declared threat -> one silent INFO per window
        if parse.is_threat:
            if event is None and (threat_until is None or message.time > threat_until):
                emit("NEW", "INFO", THREAT_TITLE)
            threat_until = message.time + threat_window
            done()
            continue

        ballistic_context = (parse.names_ballistic or event is not None
                             or (threat_until is not None and message.time <= threat_until))

        # -- stage 2: launch
        if parse.is_launch and ballistic_context and weights.get(message.channel, 0.0) >= settings["launch_weight_min"]:
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
                event.last = message.time
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
        if event and parse.places and parse.terse and not parse.names_non_kyiv and not parse.is_drone:
            event.last = message.time
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

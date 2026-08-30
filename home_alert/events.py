"""Two state machines, messages in and ntfy pushes out: the ballistic three-stage
model, and drone events keyed by how close to the household the report is.

They share nothing but the message stream -- separate event keys, separate tags,
separate sounds -- so a drone over Нивки can never mute a ballistic launch on Kyiv.
The clock is the message timestamps, so `replay` and the live path run identical code.
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

# -- drones. Also fixed by the spec; only the per-tier cooldowns are the household's.
DRONE_WINDOW = timedelta(minutes=8)      # one event per zone while reports keep coming
ECHO = timedelta(seconds=15)             # an aggregator restating another channel's fact
PARTIAL = 0.5                            # ...counts half. It is not a second pair of eyes.
URGENT_CONFIDENCE = 0.8                  # noisy-OR bar for waking the house

DRONE_TITLES = {
    ("HOME", "URGENT"): "БпЛА НАД ДОМОМ",
    ("HOME", "WATCH"): "БпЛА над домом — одне джерело",
    ("NEARBY", "WATCH"): "БпЛА поруч",
    ("KYIV", "INFO"): "БпЛА над Києвом",
}


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


@dataclass
class Drone:
    """A drone tracked in one zone. The zone is the event key, so the household gets one
    live notification for "over us" and one for "in the ring", not one per report."""
    zone: str
    opened: datetime
    last: datetime            # a zone falls quiet for DRONE_WINDOW and the event closes
    weights: dict = field(default_factory=dict)   # channel -> its best contribution here
    places: set = field(default_factory=set)
    chained: bool = False     # a channel followed its own reply chain into this zone
    echo: tuple = None        # (time, places, channel) of the last report folded in

    @property
    def tier(self):
        """HOME wakes the house only once the reports are worth waking it for.

        Confidence is noisy-OR over the channels that reported (ADR 9): one channel at
        w >= 0.8 clears the bar alone, two weaker ones clear it together (0.6+0.6 = 0.84),
        and a half-weight echo does not (0.7 + 0.6/2 = 0.79). Reply-chain progression --
        the channel that has been tracking this drone says it is over us now -- clears it
        too, which is the only reason AerisRimor's lone `Антонов.` at 07:55 on 28 Aug
        rings the phone.
        """
        if self.zone == "KYIV":
            return "INFO"
        missed = 1.0
        for weight in self.weights.values():
            missed *= 1 - weight
        confident = self.chained or 1 - missed >= URGENT_CONFIDENCE
        return "URGENT" if self.zone == "HOME" and confident else "WATCH"

    @property
    def title(self):
        return DRONE_TITLES[(self.zone, self.tier)]

    @property
    def tag(self):
        return f"drone-{self.zone.lower()}-{self.opened:%Y%m%dT%H%M%S}"

    def report(self, message, named, weight, chained):
        """Fold one report in. A channel restating within `ECHO` what another channel
        just said, naming no place of its own, is half a source -- the aggregator echo
        `channel-eval-kyiv_nebo.md` measured, not a second pair of eyes."""
        echoing = (self.echo and message.channel != self.echo[2]
                   and message.time - self.echo[0] <= ECHO
                   and not set(named) - self.echo[1])
        contribution = weight * PARTIAL if echoing else weight
        self.weights[message.channel] = max(self.weights.get(message.channel, 0.0),
                                            contribution)
        self.places |= set(named)
        self.chained |= chained
        self.echo = (message.time, set(named), message.channel)
        self.last = message.time


def replay(messages, config, sink, store=None):
    """Feed messages through the rules and push what the household would have seen."""
    weights = config["channels"]
    resound_gap = timedelta(minutes=config["ballistic"]["resound_gap_min"])
    home, nearby = set(config["home"]), set(config["nearby"])
    default_type = config.get("default_type", {})
    cooldown = {tier: timedelta(minutes=minutes)
                for tier, minutes in config["drone"]["cooldown_min"].items()}

    event = None
    threat_until = None
    context = Context()
    drones = {}          # zone -> the live Drone event there
    sounded = {}         # (zone, tier) -> when it last made a noise, for the cooldowns
    tracked = {}         # (channel, msg id) -> (time, zone) of a drone report

    for message in messages:
        text = " ".join(message.text.split())
        parse = rules.classify(text)
        pushes = []

        def emit(kind, tier, title, tag=None):
            push = Push(message.time, kind, tier, title,
                        f"{message.channel}: {text[:120]}",
                        tag or (event.tag if event else
                                f"threat-{message.time:%Y%m%dT%H%M%S}"))
            sink(push)
            pushes.append(push)

        def done(with_event=True):
            if store:
                store.record(message, parse, event if with_event else None, pushes)

        if not text or parse.is_noise:
            done()
            continue

        # spec order is noise -> context -> rules: an ad must not set the channel's type
        in_context, threat_type = context.assemble(message, text, parse)
        if in_context is None:      # a bump: the same text re-posted as a reply
            done()
            continue
        parse = in_context
        threat_type = threat_type or default_type.get(message.channel)

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

        # -- drones. A report is a place plus a type; the type is usually not in the
        # message ("Нивки"), it is what the channel has been talking about. Reports about
        # cities we do not cover, recon flights and all-clears are stored, never pushed.
        drone_report = (threat_type == "drone" and parse.places and parse.terse
                        and not parse.names_non_kyiv and not parse.is_clear
                        and not parse.is_recon)
        zone = rules.zone(parse.places, home, nearby) if drone_report else None
        if zone:
            tracked = {k: v for k, v in tracked.items()
                       if message.time - v[0] <= DRONE_WINDOW}
            # progression, not repetition: the channel tracked this drone through some
            # other zone and now puts it here. Replying to its own report of the same
            # zone is the same fact again and must not buy a channel its second source.
            parent = tracked.get((message.channel, message.reply_to))
            chained = bool(parent) and parent[1] != zone
            tracked[(message.channel, message.id)] = (message.time, zone)

            drone = drones.get(zone)
            fresh = drone is None or message.time - drone.last > DRONE_WINDOW
            if fresh:
                drone = drones[zone] = Drone(zone, message.time, message.time)
            was = drone.tier
            drone.report(message, parse.places, weights.get(message.channel, 0.0), chained)

            kind = "NEW" if fresh else "PROMOTE" if drone.tier != was else "UPDATE"
            # The cooldown gates the sound, not the notification: a gated NEW still goes
            # out silently, so the body on the phone stays current (spec story 33). It is
            # kept per zone rather than globally per tier -- a drone that has moved from
            # the ring to over the house is new information at the same tier.
            last = sounded.get((zone, drone.tier))
            if kind != "UPDATE" and last and message.time - last < cooldown[drone.tier]:
                kind = "UPDATE"
            if kind != "UPDATE":
                sounded[(zone, drone.tier)] = message.time
            emit(kind, drone.tier, drone.title, drone.tag)
            # ponytail: drone events have no row of their own yet, so record no event
            # rather than the unrelated live ballistic one -- a notifications-to-events
            # join would otherwise credit these pushes to it. Every message and every
            # push is stored, so a night of drones still replays from those two tables.
            done(with_event=False)
            continue

        done()

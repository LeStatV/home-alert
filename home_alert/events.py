"""Two state machines, messages in and ntfy pushes out: the three-stage launch model
-- run once per threat type -- and drone events keyed by how close to the household
the report is.

They share nothing but the message stream -- separate event keys, separate tags,
separate sounds -- so a drone over Нивки can never mute a ballistic launch on Kyiv.
The clock is the message timestamps, so `replay` and the live path run identical code.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import profiles, rules
from .context import Context
from .notify import Push

# Fixed by the spec, not by the household -- only the resound gap is tunable.
LAUNCH_WEIGHT_MIN = 0.6          # a launch on Kyiv from any channel this trusted is URGENT
THREAT_WINDOW = timedelta(minutes=15)
PENDING_TTL = timedelta(seconds=90)   # a launch nobody gave a target stops mattering
EVENT_TTL = timedelta(minutes=5)      # an event closes after this long without launches

THREAT_TITLE = "Загроза балістики"
# One machine, three event types. `other` is a launch on a city we do not cover: it gets
# a real event so `replay` and the events table can show it, and never a push (story 12).
TITLES = {
    ("ballistic", True): "Пуск балістики, ціль уточнюється",
    ("ballistic", False): "БАЛІСТИКА на Київ",
    ("missile", True): "Пуск ракет, ціль уточнюється",
    ("missile", False): "КРИЛАТІ РАКЕТИ на Київ",
}
OTHER_TITLE = "Пуск на інше місто"

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
    """One live wave of one type. Ballistic and missile events run side by side and
    share nothing -- separate tag, separate resound clock, separate pending flag -- so a
    Zircon WATCH can never quiet, promote or re-tag a ballistic launch on Kyiv."""
    type: str                # ballistic | missile | other
    opened: datetime
    last_launch: datetime    # drives the close: the spec closes on launches, not chatter
    sounded: datetime        # last push that made a noise
    pending: bool            # a launch whose target has not been named yet
    launches: int = 1
    places: set = field(default_factory=set)
    sources: set = field(default_factory=set)
    counts: dict = field(default_factory=dict)   # channel -> its own largest figure
    last_text: str = ""      # the last launch call folded in, verbatim

    @property
    def tier(self):
        # `other` never reaches ntfy, so its column in the events table says so rather
        # than claiming a tier the household was never sent.
        if self.type == "other":
            return "LOG"
        return "WATCH" if self.pending else "URGENT"

    @property
    def title(self):
        return OTHER_TITLE if self.type == "other" else TITLES[(self.type, self.pending)]

    @property
    def tag(self):
        return f"{self.type[:3]}-{self.opened:%Y%m%dT%H%M%S}"

    @property
    def count(self):
        """`>=N`: the largest figure any one channel gave, never the sum of them. Five
        channels each counting the same six missiles is six missiles (story 23)."""
        return max(self.counts.values(), default=0)

    def fold(self, message, parse, target):
        self.places |= set(target)
        self.sources.add(message.channel)
        self.counts[message.channel] = max(self.counts.get(message.channel, 0), parse.count)


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
    channels = profiles.load(config["profiles"])
    resound_gap = timedelta(minutes=config["ballistic"]["resound_gap_min"])
    home, nearby = set(config["home"]), set(config["nearby"])
    cooldown = {tier: timedelta(minutes=minutes)
                for tier, minutes in config["drone"]["cooldown_min"].items()}

    live = {}            # event type -> the one live event of that type
    threat_until = None
    context = Context()
    drones = {}          # zone -> the live Drone event there
    sounded = {}         # (zone, tier) -> when it last made a noise, for the cooldowns
    tracked = {}         # (channel, msg id) -> (time, zone) of a drone report

    for message in messages:
        profile = channels.get(message.channel)
        if profile is None:      # no profile, no channel: the files are the channel list
            continue
        text = " ".join(message.text.split())
        parse = rules.classify(text, profile)
        pushes = []

        def emit(kind, tier, title, tag, count=0):
            shown = f"≥{count} · " if count >= 2 else ""
            push = Push(message.time, kind, tier, title,
                        f"{shown}{message.channel}: {text[:120]}", tag)
            sink(push)
            pushes.append(push)

        def done(event=None):
            if store:
                store.record(message, parse, event, pushes)

        if not text or parse.is_noise:
            done()
            continue

        # spec order is noise -> context -> rules: an ad must not set the channel's type
        in_context, threat_type = context.assemble(message, text, parse)
        if in_context is None:      # a bump: the same text re-posted as a reply
            done()
            continue
        parse = in_context
        threat_type = threat_type or profile.default_type

        # the message clock closes stale events and expires unconfirmed launches
        for etype, stale in list(live.items()):
            if (message.time - stale.last_launch > EVENT_TTL
                    or (stale.pending and message.time - stale.opened > PENDING_TTL)):
                del live[etype]

        # -- stage 1: declared threat -> one silent INFO per window
        if parse.is_threat:
            # a threat during a live event is noise: the household is already alarmed
            if "ballistic" not in live and (threat_until is None
                                            or message.time > threat_until):
                emit("NEW", "INFO", THREAT_TITLE, f"threat-{message.time:%Y%m%dT%H%M%S}")
            threat_until = message.time + THREAT_WINDOW
            done()
            continue

        ballistic_context = (parse.names_ballistic or "ballistic" in live
                             or (threat_until is not None and message.time <= threat_until))
        # a cruise missile says so in its own words. war_monitor's `Nx ...` house style is
        # not a drone marker: 54 of those posts are KP, KAB and PRR (issue #4 note).
        missile = parse.names_missile and not parse.is_drone

        # -- stage 2: launch. Three ways a cruise wave becomes ours: a bearing that says
        # Kyiv (`у напрямку Києва` -- a WATCH, never an immediate URGENT), an approach
        # word over a Kyiv place (`БРОВАРИ ПІДЛІТ КР!`), or a launch call with no target
        # at all (`Вихід другого Циркону`). An approach word alone is somebody else's
        # city: eleven of those in the corpus (Новий Буг, Оржиця, Козельщина, Канів).
        # A drone report is never a launch, however much it reads like one
        # ("1 Заворичі на вихід" names Київщина and matches the launch vocabulary).
        launching = parse.is_launch or (missile and (parse.is_direction
                                                     or (parse.is_approach and parse.places)))
        if (launching and (ballistic_context or missile or parse.places)
                and (parse.names_ballistic or missile or not parse.is_drone)
                and profile.weight >= LAUNCH_WEIGHT_MIN):
            etype = "missile" if missile else "ballistic"
            # gating is on the target, not on every name: `на Київ повз Прилуки, Ніжин`
            # and `повз Ічню у напрямку Київщини` are ours, `Ціль на Ромни!` is a
            # log-only event of its own. Without the bearing here the oblasts a wave
            # transits swallow the only Kyiv-ward signal a channel ever gives.
            if parse.names_non_kyiv and not (parse.targets_kyiv or parse.is_direction):
                etype = "other"
            target = parse.places if etype != "missile" or parse.is_approach else ()
            event = live.get(etype)
            if event is None:
                event = live[etype] = Event(etype, message.time, message.time,
                                            message.time, pending=not target)
                kind = "NEW"
            else:
                event.launches += 1
                event.last_launch = message.time
                # a launch call re-posted verbatim is the same fact twice, whatever the
                # gap. `context` only catches it while the parent is still in its 3-min
                # window; nebo_raketa's 21 Aug 22:15:36 re-post came 3 m 30 s later.
                kind = ("PROMOTE" if event.pending and target else
                        "RESOUND" if not event.pending and text != event.last_text
                        and message.time - event.sounded >= resound_gap else "UPDATE")
                if kind != "UPDATE":
                    event.pending = False
                    event.sounded = message.time
            event.fold(message, parse, target)
            event.last_text = text
            if etype != "other":
                emit(kind, event.tier, event.title, event.tag, event.count)
            done(event)
            continue

        # -- stage 3: trajectory -- bare place names while the ballistic event is live.
        # ponytail: a live *missile* event deliberately does not claim them. Its body
        # then follows only the launch and approach calls, but on 19 Aug 22:33 a Калібр
        # wave would otherwise have swallowed the bare `Нивки` reports for five minutes
        # and cost the household its drone URGENT over the home set. The trade goes the
        # other way when replace-in-place is actually wired up (notify.py).
        event = live.get("ballistic")
        if (event and parse.places and parse.terse
                and not parse.names_non_kyiv and not parse.is_drone and not parse.is_recon):
            event.fold(message, parse, parse.places)
            if event.pending:
                event.pending = False
                event.sounded = message.time
                emit("PROMOTE", "URGENT", event.title, event.tag, event.count)
            else:
                emit("UPDATE", event.tier, event.title, event.tag, event.count)
            done(event)
            continue

        # -- stage 4: impact / all-clear -- body update only, never a sound
        if event and parse.is_clear:
            emit("UPDATE", event.tier, event.title, event.tag, event.count)
            done(event)
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
            drone.report(message, parse.places, profile.weight, chained)

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
            done()
            continue

        done()

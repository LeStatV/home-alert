"""Two state machines, messages in and ntfy pushes out: the three-stage launch model
-- run once per threat type -- and drone events keyed by how close to the household
the report is.

They share nothing but the message stream -- separate event keys, separate tags,
separate sounds -- so a drone over Нивки can never mute a ballistic launch on Kyiv.
The clock is the message timestamps, so `replay` and the live path run identical code.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import llm as enrichment, profiles, rules
from .context import Context
from .notify import SYSTEM_TOPIC, Push

# Timestamps in this project are naive UTC end to end (`notify.now`); the household's
# phone is the one place that clock is read by a person, so only there it is rendered
# in Kyiv wall time. Storage, tags, logs and `replay` stay UTC (#20 owns the CLI call).
KYIV_TZ = ZoneInfo("Europe/Kyiv")


def wall(when):
    """A naive-UTC datetime as Kyiv wall clock, for push bodies only."""
    return when.replace(tzinfo=timezone.utc).astimezone(KYIV_TZ)

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

# -- the official siren feed. Read for one bit and never as a gate (ADR 17): is the
# siren sounding in м. Київ? @air_alert_ua posts one region per message, naming it
# twice -- in prose (`Повітряна тривога в м. Київ`) and as a trailing `#м_Київ`. The
# rest of the oblast is posted per raion (`#Вишгородський_район`, `#Бучанський_район`,
# never `#Київська_область`): a different siren, and not ours. Verified against 3580
# real posts in #23; `tests/test_siren.py` holds the labelled sample.
SIREN_CHANNEL = "air_alert_ua"
# `{0,2}` because the prose form is `м. Київ` -- a dot *and* a space -- while the
# hashtag is `м_Київ`. `\b` so that a word merely ending in `м` before Київ (`...ським
# Київська`) is not the city. The lookahead is the other half: `м. Київська область`
# and `м Київський район` are the oblast, not м. Київ. It rejects a Cyrillic letter
# rather than requiring a word boundary, because `_` and space must both still end the
# name -- the channel writes compound tags like `#м_Харків_та_Харківська_...`.
SIREN_KYIV = re.compile(r"\bм[._ ]{0,2}київ(?![а-яїієґ])", re.I)
SIREN_ON = re.compile(r"повітряна тривога", re.I)
SIREN_OFF = re.compile(r"відбій тривоги", re.I)
SIREN_LABEL = {True: "🔴 тривога", False: "🟢 відбій", None: "⚪ сирена невідома"}


def siren_verdict(text):
    """What one @air_alert_ua post says about the siren in м. Київ.

    `"on"` and `"off"` are the only two that move anything; `"not-kyiv"` is somebody
    else's siren and `"not-siren"` is one of the channel's many non-alert posts (a КАБ
    advisory, an evacuation notice, a `тривога ще триває у:` reminder). Named verdicts
    rather than a bare bool so a test can tell the two no-ops apart.
    """
    text = " ".join(text.split())
    on, off = SIREN_ON.search(text), SIREN_OFF.search(text)
    if not on and not off:
        return "not-siren"
    if not SIREN_KYIV.search(text):
        return "not-kyiv"
    return "on" if on else "off"

# A channel that has posted this recently is one of the `N/6 каналів активні` the body
# shows; the number is the household's own measure of how much to trust a lone report.
ACTIVE_WINDOW = timedelta(minutes=30)
# The corridor signal: this long without a report over the house or in the ring, and
# somebody saying it is over, and the household is told it can come out (ADR 10).
ALL_CLEAR_QUIET = timedelta(minutes=10)
# Every channel quiet this long while the Kyiv siren sounds means the household's eyes
# are shut, and only the owner's `system` topic hears about it (SPEC story 15).
SILENT_WARN = timedelta(minutes=10)
SILENT_TITLE = "Канали мовчать під тривогою"
CHAIN = 6                # places shown in the body; a night-long event names dozens

# The all-clear is titled by zone, not by the event's tier: "Відбій — БпЛА над домом"
# is what the household is waiting to read, whether the pass was an URGENT or a WATCH.
ALL_CLEAR_TITLES = {"HOME": "Відбій — БпЛА над домом", "NEARBY": "Відбій — БпЛА поруч"}

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
    last: datetime = None    # last report of any kind -- the body shows its age
    places: list = field(default_factory=list)   # in the order they were reported
    sources: list = field(default_factory=list)
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
    def clock(self):
        """The `events.last` column: for a wave that is the last *launch*, the clock
        the close runs on -- not the last report, which trajectory calls also move."""
        return self.last_launch

    @property
    def count(self):
        """`>=N`: the largest figure any one channel gave, never the sum of them. Five
        channels each counting the same six missiles is six missiles (story 23)."""
        return max(self.counts.values(), default=0)

    def fold(self, message, parse, target):
        for place in target:
            if place not in self.places:
                self.places.append(place)
        if message.channel not in self.sources:
            self.sources.append(message.channel)
        self.counts[message.channel] = max(self.counts.get(message.channel, 0), parse.count)
        self.last = message.time


@dataclass
class Drone:
    """A drone tracked in one zone. The zone is the event key, so the household gets one
    live notification for "over us" and one for "in the ring", not one per report."""
    zone: str
    opened: datetime
    last: datetime            # a zone falls quiet for DRONE_WINDOW and the event closes
    weights: dict = field(default_factory=dict)   # channel -> its best contribution here
    places: list = field(default_factory=list)    # in the order they were reported
    chained: bool = False     # a channel followed its own reply chain into this zone
    count: int = 0            # largest figure any one channel gave, never their sum
    echo: tuple = None        # (time, places, channel) of the last report folded in
    left: bool = False        # the drone has been reported in another zone since

    # A drone event has no launch concept: nothing launches, so there is nothing to
    # count and no launch clock. `events.launches` is NULL for these rows, never 0 --
    # a 0 would read as "we counted, and it was none". Not a field: nothing sets it.
    launches = None

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

    @property
    def clock(self):
        """The `events.last` column: any report keeps a zone alive, so the last one is
        both the age the body shows and the clock the event closes on."""
        return self.last

    @property
    def sources(self):
        return tuple(self.weights)      # insertion-ordered: who reported it, first first

    def report(self, message, named, weight, chained, count=0):
        """Fold one report in. A channel restating within `ECHO` what another channel
        just said, naming no place of its own, is half a source -- the aggregator echo
        `channel-eval-kyiv_nebo.md` measured, not a second pair of eyes."""
        echoing = (self.echo and message.channel != self.echo[2]
                   and message.time - self.echo[0] <= ECHO
                   and not set(named) - self.echo[1])
        contribution = weight * PARTIAL if echoing else weight
        self.weights[message.channel] = max(self.weights.get(message.channel, 0.0),
                                            contribution)
        for place in named:
            if place not in self.places:
                self.places.append(place)
        self.chained |= chained
        self.count = max(self.count, count)
        if weight:
            # a weightless story-30 report is not a fact worth halving a real second
            # source against: it would turn the wake-up into a WATCH, which is the one
            # thing a fail-safe path must never do. Nor does it keep the event alive:
            # a report nothing could type must not hold the zone's re-sound clock down
            # and silence the next real one (#16).
            self.echo = (message.time, set(named), message.channel)
            self.last = message.time


class Pipeline:
    """One pass of the two state machines over a message stream.

    `replay` and the live reader both hand messages in here one at a time; nothing
    downstream of this point knows which of the two it is talking to.
    """

    def __init__(self, config, sink, store=None, enricher=None):
        self.channels = profiles.load(config["profiles"])
        # the optional second opinion: `llm.provider: none` (the default) is no client
        # at all, and every path below is written to work without one
        self.enricher = enricher or enrichment.client(config.get("llm"))
        self.resound_gap = timedelta(minutes=config["ballistic"]["resound_gap_min"])
        self.urgent_floor = timedelta(minutes=config["urgent_floor_min"])
        self.home, self.nearby = set(config["home"]), set(config["nearby"])
        self.cooldown = {tier: timedelta(minutes=minutes)
                         for tier, minutes in config["drone"]["cooldown_min"].items()}
        self.sink, self.store = sink, store
        # ntfy identifies a notification by (server, topic, sequence_id), so a push
        # that changes topic starts a new entry. The all-clear has to follow its event
        # to whichever topic the event has been pushing on.
        self.topics = config["ntfy"]["topics"]

        self.siren = None         # the official siren in м. Київ: on, off, or unknown
        self.siren_off = None     # when it last ended -- half of the all-clear condition
        self.cleared_at = None    # when a channel last said it was over -- the other half
        self.last_near = None     # last report over the house or in the ring
        self.last_post = {}       # channel -> when it last posted anything at all
        self.started = None       # first message seen: nothing is "silent" before it
        self.warned = False       # the silent-channel warning, once per siren
        self.live = {}            # event type -> the one live event of that type
        self.threat_until = None
        self.context = Context()
        self.drones = {}          # zone -> the live Drone event there
        self.sounded = {}         # (zone, tier) -> when it last made a noise
        self.urgent_sounded = None    # when anything last bypassed Do-Not-Disturb
        self.tracked = {}         # (channel, msg id) -> (time, zone) of a drone report

    def floored(self, kind, tier, when):
        """One floor under every sound that bypasses Do-Not-Disturb, whatever event it
        came from: on 19 Aug a missile URGENT and a ballistic URGENT rang 18 s apart for
        one raid, each event's own clock happily kept (#16). Only a repeat is floored --
        a NEW event or a promotion is news the household has not heard yet.
        """
        if (kind == "RESOUND" and tier == "URGENT" and self.urgent_sounded
                and when - self.urgent_sounded < self.urgent_floor):
            return "UPDATE"
        if kind != "UPDATE" and tier == "URGENT":
            self.urgent_sounded = when
        return kind

    def tail(self, when, places, sources, last):
        """The body under the message itself: the chain the event has travelled, who
        reported it and how long ago, the official siren, and how many channels are
        still talking (SPEC story 9). Everything the household needs to judge it.
        """
        chain = [" → ".join(places[-CHAIN:])] if places else []
        age = when - last
        ago = ("щойно" if age < timedelta(minutes=1)
               else f"{int(age.total_seconds() // 60)} хв тому")
        return chain + [
            f"джерела: {', '.join(sources)} · звіт {wall(last):%H:%M:%S} ({ago})",
            f"{SIREN_LABEL[self.siren]} · {self.active(when)}/{len(self.channels)}"
            " каналів активні",
        ]

    def stand_down(self, when):
        """The all-clear, and the pushes it sends: one silent INFO per live event over
        the house or in the ring, once both halves of ADR 10 hold -- ten minutes with
        no report from either set, AND somebody saying it is over, a channel's own
        clear call or the official siren ending. Quiet alone is not an all-clear: a
        drone that stops being reported may only have stopped being seen.

        ponytail: arrival-driven, like everything else in this file -- the condition is
        tested on each incoming message, so the all-clear lands on the first message
        after the ten minutes are up, not on the second they elapse. The siren feed
        alone posts nationwide every few minutes, so live that is seconds; if every
        channel goes dark at once the all-clear waits, which is the honest answer.
        """
        said = max([at for at in (self.cleared_at, self.siren_off) if at], default=None)
        if (self.last_near is None or when - self.last_near < ALL_CLEAR_QUIET
                or said is None or said < self.last_near):
            return []
        sent = []
        for zone in ("HOME", "NEARBY"):
            drone = self.drones.pop(zone, None)
            if drone is None:
                continue
            # `drone.tier` only ever rises, so it is still the tier of the event's last
            # push: the all-clear replaces that entry in place instead of opening a
            # third one somewhere else, and the family -- who subscribe `urgent` alone
            # -- get the one push that says they can come out of the corridor.
            #
            # ponytail: a WATCH that was promoted left a stale entry behind on the
            # topic it started on, and this cannot reach it. ntfy has
            # `PUT /<topic>/<sequence_id>/clear` for exactly that; wiring it is the
            # owner's call, since it dismisses a notification he may not have read.
            push = Push(when, "CLEAR", "INFO", ALL_CLEAR_TITLES[zone],
                        "\n".join(self.tail(when, drone.places, drone.sources,
                                            drone.last)),
                        drone.tag, topic=self.topics[drone.tier])
            self.sink(push)
            sent.append(push)
        return sent

    def coverage(self, when):
        """Warn the owner, once per siren, when the household's eyes have shut: the
        Kyiv siren is sounding and every channel that is not inside its profile's
        `quiet_hours` has been quiet for ten minutes (SPEC story 15).

        The exemption is what keeps kyiv_nebo's nightly 03:00-07:00 blackout from
        crying wolf every night; a channel that is merely asleep is not an outage.
        """
        quiet = [channel for channel, profile in sorted(self.channels.items())
                 if not profile.expected_silent(when)
                 and when - self.last_post.get(channel, self.started) >= SILENT_WARN]
        awake = sum(1 for profile in self.channels.values()
                    if not profile.expected_silent(when))
        if (not self.siren or self.warned or not quiet or len(quiet) < awake
                or when - self.started < SILENT_WARN):
            return []
        self.warned = True
        # not `self.tail`: the N/6 label counts a wider window than this warning does,
        # and printing both here only invites the owner to reconcile two numbers
        push = Push(when, "SYSTEM", "INFO", SILENT_TITLE,
                    f"{SIREN_LABEL[self.siren]}, а мовчать понад "
                    f"{int(SILENT_WARN.total_seconds() // 60)} хв: {', '.join(quiet)}",
                    f"silent-{when:%Y%m%dT%H%M%S}", topic=SYSTEM_TOPIC)
        self.sink(push)
        return [push]

    def active(self, when):
        """How many channels have posted anything at all lately -- plain recency, the
        `N/6` the household reads as "how many pairs of eyes are open right now".
        Whether a gap is expected is a different question, and only the silent-while-
        siren warning asks it."""
        return sum(1 for last in self.last_post.values() if when - last <= ACTIVE_WINDOW)

    def feed(self, message):
        """One message in, whatever it is worth in pushes out.

        ponytail: the clock is `message.time` on both paths -- live, that is Telegram's
        own timestamp, i.e. wall clock modulo delivery lag. Nothing here is timer-driven,
        so a stale event closes on the next message rather than on the second it expires.
        """
        if message.edited:
            # The spec alerts on posts, not on corrections to them: an edit is recorded
            # and goes no further. Re-running the rules would re-sound an event that has
            # already woken the house over text the channel merely tidied up.
            if self.store:
                self.store.record_edit(message)
            return
        self.started = self.started or message.time
        text = " ".join(message.text.split())
        if message.channel == SIREN_CHANNEL:
            # The one channel with no profile and no weight. It classifies nothing and
            # scores nothing; it flips one bit that every push then shows.
            verdict = siren_verdict(text)
            if verdict == "on":
                if not self.siren:          # a new siren, a new chance to warn
                    self.warned = False
                self.siren = True
            elif verdict == "off":
                if self.siren:
                    self.siren_off = message.time
                self.siren = False
            pushes = self.stand_down(message.time) + self.coverage(message.time)
            if self.store:
                self.store.record(message, rules.classify(text), None, pushes)
            return
        profile = self.channels.get(message.channel)
        if profile is None:      # no profile, no channel: the files are the channel list
            return
        self.last_post[message.channel] = message.time     # even an ad proves it is alive
        parse = rules.classify(text, profile)
        if parse.is_clear:
            self.cleared_at = message.time
        pushes = self.stand_down(message.time)

        def emit(kind, tier, title, tag, count=0, event=None):
            shown = f"≥{count} · " if count >= 2 else ""
            lines = [f"{shown}{message.channel}: {text[:120]}"]
            lines += self.tail(message.time,
                               event.places if event else parse.places,
                               event.sources if event else (message.channel,),
                               (event.last if event else None) or message.time)
            push = Push(message.time, kind, tier, title, "\n".join(lines), tag,
                        source=f"https://t.me/{message.channel}/{message.id}")
            self.sink(push)
            pushes.append(push)

        def done(event=None):
            if self.store:
                self.store.record(message, parse, event, pushes, self.siren)

        if not text or parse.is_noise:
            done()
            return

        # spec order is noise -> context -> rules: an ad must not set the channel's type
        in_context, threat_type = self.context.assemble(message, text, parse)
        if in_context is None:      # a bump: the same text re-posted as a reply
            done()
            return
        parse = in_context
        threat_type = threat_type or profile.default_type

        # -- the optional second opinion, on the leftovers only (SPEC story 29). A
        # launch call, a threat declaration and a ballistic word all type themselves
        # through `rules.type_of`, so the launch path can never reach this line --
        # which is the whole of story 32. Anything the provider says is folded in
        # upwards or not at all, and a provider that is slow, down or talking nonsense
        # leaves the rules verdict exactly where it was.
        #
        # ponytail: synchronous, like the ntfy push -- live, this blocks the Telethon
        # handler on a message nothing else could type. `llm.TIMEOUT` is asked of the
        # transport and enforced by nobody (see `llm.py`), so the real ceiling is
        # "however long the provider takes to give up", and only these messages are
        # ever exposed to it. `await asyncio.to_thread(...)` with a deadline is the
        # upgrade the day a provider is configured.
        if self.enricher and enrichment.unresolved(parse, threat_type):
            parse = enrichment.merge(parse, self.enricher.enrich(message))
            # deliberately not written into `self.context`: the model typed this one
            # message, not the next twenty bare place names from the channel
            threat_type = rules.type_of(parse)

        # the message clock closes stale events and expires unconfirmed launches
        for etype, stale in list(self.live.items()):
            if (message.time - stale.last_launch > EVENT_TTL
                    or (stale.pending and message.time - stale.opened > PENDING_TTL)):
                del self.live[etype]

        # -- stage 1: declared threat -> one silent INFO per window
        if parse.is_threat:
            # a threat during a live event is noise: the household is already alarmed
            if "ballistic" not in self.live and (self.threat_until is None
                                                 or message.time > self.threat_until):
                emit("NEW", "INFO", THREAT_TITLE, f"threat-{message.time:%Y%m%dT%H%M%S}")
            self.threat_until = message.time + THREAT_WINDOW
            done()
            return

        ballistic_context = (parse.names_ballistic or "ballistic" in self.live
                             or (self.threat_until is not None
                                 and message.time <= self.threat_until))
        # a cruise missile says so in its own words. war_monitor's `Nx ...` house style is
        # not a drone marker: 54 of those posts are KP, KAB and PRR (issue #4 note).
        missile = rules.type_of(parse) == "missile"

        # -- stage 2: launch. Three ways a cruise wave becomes ours: a bearing that says
        # Kyiv (`у напрямку Києва` -- a WATCH, never an immediate URGENT), an approach
        # word over a Kyiv place (`БРОВАРИ ПІДЛІТ КР!`), or a launch call with no target
        # at all (`Вихід другого Циркону`). An approach word alone is somebody else's
        # city: eleven of those in the corpus (Новий Буг, Оржиця, Козельщина, Канів).
        # A drone report is never a launch, however much it reads like one
        # ("1 Заворичі на вихід" names Київщина and matches the launch vocabulary).
        launching = rules.stage(parse) == "launch"
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
            event = self.live.get(etype)
            if event is None:
                event = self.live[etype] = Event(etype, message.time, message.time,
                                                 message.time, pending=not target)
                kind = self.floored("NEW", event.tier, message.time)
            else:
                event.launches += 1
                event.last_launch = message.time
                # a launch call re-posted verbatim is the same fact twice, whatever the
                # gap. `context` only catches it while the parent is still in its 3-min
                # window; nebo_raketa's 21 Aug 22:15:36 re-post came 3 m 30 s later.
                kind = ("PROMOTE" if event.pending and target else
                        "RESOUND" if not event.pending and text != event.last_text
                        and message.time - event.sounded >= self.resound_gap else "UPDATE")
                # a promotion is pushed as URGENT: the flag it clears is set below
                kind = self.floored(kind, "URGENT" if kind == "PROMOTE" and etype != "other"
                                    else event.tier, message.time)
                if kind != "UPDATE":
                    event.pending = False
                    event.sounded = message.time
            event.fold(message, parse, target)
            event.last_text = text
            if etype != "other":
                emit(kind, event.tier, event.title, event.tag, event.count, event)
            done(event)
            return

        # -- stage 3: trajectory -- bare place names while the ballistic event is live.
        # ponytail: a live *missile* event deliberately does not claim them. Its body
        # then follows only the launch and approach calls, but on 19 Aug 22:33 a Калібр
        # wave would otherwise have swallowed the bare `Нивки` reports for five minutes
        # and cost the household its drone URGENT over the home set. The trade goes the
        # other way when replace-in-place is actually wired up (notify.py).
        event = self.live.get("ballistic")
        if (event and parse.places and parse.terse
                and not parse.names_non_kyiv and not parse.is_drone and not parse.is_recon):
            event.fold(message, parse, parse.places)
            if event.pending:
                event.pending = False
                event.sounded = message.time
                # a promotion is never floored; it still stamps the floor for what follows
                emit(self.floored("PROMOTE", "URGENT", message.time),
                     "URGENT", event.title, event.tag, event.count, event)
            else:
                emit("UPDATE", event.tier, event.title, event.tag, event.count, event)
            done(event)
            return

        # -- stage 4: impact / all-clear -- body update only, never a sound
        if event and parse.is_clear:
            emit("UPDATE", event.tier, event.title, event.tag, event.count, event)
            done(event)
            return

        # -- drones. A report is a place plus a type; the type is usually not in the
        # message ("Нивки"), it is what the channel has been talking about. Reports about
        # cities we do not cover, recon flights and all-clears are stored, never pushed.
        drone_report = (threat_type == "drone" and parse.places and parse.terse
                        and not parse.names_non_kyiv and not parse.is_clear
                        and not parse.is_recon)
        # -- SPEC story 30, the rules-only failure mode: a terse report naming the house
        # or the ring that nothing could type -- not the rules, not the reply chain, not
        # the channel's memory, not the model. `Йде Виноградар на Антонов!` is a drone
        # over the home set in wording no rule knows, and a rule gap must fail safe
        # rather than silent. It is folded into the zone's drone event weightless, which
        # is the whole of the cap: it can open a WATCH and lengthen the chain, and it can
        # never on its own clear the noisy-OR bar that wakes the house.
        untyped = (not drone_report and parse.places and parse.terse
                   and not parse.names_non_kyiv
                   and enrichment.unresolved(parse, threat_type))
        zone = (rules.zone(parse.places, self.home, self.nearby)
                if drone_report or untyped else None)
        if untyped and zone not in ("HOME", "NEARBY"):
            zone = None      # an untyped report about Kyiv at large is not a report
        if zone:
            self.tracked = {k: v for k, v in self.tracked.items()
                            if message.time - v[0] <= DRONE_WINDOW}
            # progression, not repetition: the channel tracked this drone through some
            # other zone and now puts it here. Replying to its own report of the same
            # zone is the same fact again and must not buy a channel its second source.
            parent = self.tracked.get((message.channel, message.reply_to))
            chained = bool(parent) and parent[1] != zone and not untyped
            if not untyped:      # an untyped report neither earns nor grants the chain
                self.tracked[(message.channel, message.id)] = (message.time, zone)

            if zone != "KYIV":
                self.last_near = message.time
            drone = self.drones.get(zone)
            fresh = drone is None or message.time - drone.last > DRONE_WINDOW
            if fresh:
                drone = self.drones[zone] = Drone(zone, message.time, message.time)
            # a report from the ring says the drone is not over the house right now:
            # whatever comes back has news to tell. Only the house keeps this flag -- the
            # ring is where a drone passes through, the house is where it returns to --
            # and only a report something could type sets it, for the same reason a
            # weightless one brings no count: it must not become a way to ring.
            if zone == "NEARBY" and not untyped and "HOME" in self.drones:
                self.drones["HOME"].left = True
            was, counted = drone.tier, drone.count
            # a weightless report brings its places and nothing else: its count would
            # be a second way to ring on a message nobody could type (story 7)
            drone.report(message, parse.places, 0.0 if untyped else profile.weight,
                         chained, 0 if untyped else parse.count)

            # a count jump is new information and may ring again (story 7); restating
            # the same figure is the same fact, and the cooldown below gates both. So is
            # a re-entry: the drone was over the house, went out to the ring and is back
            # (#16) -- on 1-2 Sep such a pass rang once, because the event never closed
            # and every return was a silent body update.
            kind = ("NEW" if fresh else "PROMOTE" if drone.tier != was
                    else "RESOUND" if drone.count > counted or drone.left else "UPDATE")
            # The cooldown gates the sound, not the notification: a gated NEW still goes
            # out silently, so the body on the phone stays current (spec story 33). It is
            # kept per zone rather than globally per tier -- a drone that has moved from
            # the ring to over the house is new information at the same tier.
            last = self.sounded.get((zone, drone.tier))
            if (kind != "UPDATE" and last
                    and message.time - last < self.cooldown[drone.tier]):
                kind = "UPDATE"
            kind = self.floored(kind, drone.tier, message.time)
            if kind != "UPDATE":
                # the return has been announced; the next one has to be earned again
                drone.left = False
                self.sounded[(zone, drone.tier)] = message.time
            emit(kind, drone.tier, drone.title, drone.tag, drone.count, drone)
            done(drone)
            return

        done()


def replay(messages, config, sink, store=None, enricher=None):
    """Feed messages through the rules and push what the household would have seen."""
    pipeline = Pipeline(config, sink, store, enricher)
    for message in messages:
        pipeline.feed(message)

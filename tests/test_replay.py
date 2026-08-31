import json
import re
from datetime import datetime
from unittest import mock

import yaml

from home_alert import cli, events, notify, reader, store
from home_alert.notify import Push
from harness import FIXTURES, ROOT, audible, bodies, replay, sent, sounds


def test_21_aug_ballistic_launch_watch_then_urgent():
    """21 Aug 21:54-22:06: AerisRimor's target-less `ЦІЛЬ` is a WATCH at 21:58:35,
    promoted to URGENT one second later when Ukrainian_Intelligence names Kyiv.

    Four minutes after the ballistic wave is over, a Бандероль cruise wave follows
    (`3 Бандеролі ... ймовірно на Київ`, `Один Бандероль на Згурівку/Бровари!`,
    `2-3 Бандеролі в бік Києва`) -- its own event, its own tag, and before #5 it was
    thirteen silent body updates on the ballistic notification.
    """
    assert sounds("2026-08-21T21-54_22-06") == [
        ("21:56:24", "NEW", "INFO", "Загроза балістики"),
        ("21:58:35", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("21:58:36", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
        ("22:02:12", "NEW", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
        ("22:04:45", "RESOUND", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
    ]


def test_21_aug_trajectory_and_impact_never_sound():
    """Everything after the promotion is a silent body update *on the ballistic event*:
    a cruise wave four minutes later is a separate event and may sound on its own."""
    after = [p for p in replay("2026-08-21T21-54_22-06")
             if p[0] > "21:58:36" and p[3] == "БАЛІСТИКА на Київ"]
    assert after, "expected trajectory/impact body updates"
    assert {p[1] for p in after} == {"UPDATE"}


def test_27_aug_urgent_long_before_the_official_channel():
    """27 Aug 00:00-00:30: `Вихід балістики з Брянська` opens a WATCH; kyiv_nebo
    names Kyiv 21 s later and promotes it -- 26 minutes before kpszsu's 00:26:40.

    Three of the old resounds were bumps -- war_monitor and Ukrainian_Intelligence
    re-posting their own launch as a reply (00:02:41, 00:04:58, 00:28:56). A bump is
    a no-op, so the second sound is now AerisRimor's own next launch call at 00:02:47.

    The 00:09:50 threat INFO is an edge of the slice, not a result worth reading into:
    the fixture starts at 00:00, so no earlier declaration is in scope to open the
    15-min threat window that would otherwise dedup it.

    The 00:16:49 INFO is war_monitor's `1х реактивний БпЛА над київським водосховищем`:
    a drone somewhere in the oblast, its own event, priority 2 and silent.
    """
    assert sounds("2026-08-27T00-00_00-30") == [
        ("00:00:18", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("00:00:39", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
        ("00:02:47", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("00:09:50", "NEW", "INFO", "Загроза балістики"),
        ("00:16:49", "NEW", "INFO", "БпЛА над Києвом"),
        ("00:24:54", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("00:26:22", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
    ]


def test_bump_reposts_are_a_no_op():
    """27 Aug: war_monitor's 00:28:56 re-post of `Київ — спуск балістики! Третя`
    as a reply to itself is the same fact twice -- no event, no update, no sound."""
    bumps = {"00:00:36", "00:00:51", "00:02:41", "00:26:34", "00:28:56"}
    assert [p for p in replay("2026-08-27T00-00_00-30") if p[0] in bumps] == []


def test_target_less_launch_expires_without_ever_sounding_urgent():
    """28 Aug 23:28-23:33: AerisRimor's `ЦІЛЬ` at 23:30:05 is followed only by
    Mykolaiv-area places, so the WATCH expires after 90 s. It is never promoted
    and never re-sounds."""
    assert sounds("2026-08-28T23-28_23-33") == [
        ("23:28:06", "NEW", "INFO", "Загроза балістики"),
        ("23:30:05", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
    ]


def test_nightly_summary_alone_produces_nothing():
    """22 Aug 06:09-06:12: kpszsu's `ЗБИТО/ПОДАВЛЕНО 191 ЦІЛЬ ПРОТИВНИКА` digest
    is a report of what already happened, not a launch."""
    assert replay("2026-08-22T06-09_06-12") == []


def test_22_aug_past_tense_and_promotion_post_never_sound():
    """22 Aug 08:36-08:50: AerisRimor's target-less `ЦІЛЬ` is a WATCH at 08:39:49 and
    Ukrainian_Intelligence's `КИЇВ ЦІЛЬ` promotes it to URGENT one second later -- 14 s
    before kpszsu, the official channel, posts `Балістичні ракети на Київ.` at 08:40:04.
    Afterwards AerisRimor's past-tense `Цілі були або Іскандери…` and nebo_raketa's
    `@Kyiv` cross-promo push nothing."""
    assert sounds("2026-08-22T08-36_08-50") == [
        ("08:37:48", "NEW", "INFO", "Загроза балістики"),
        ("08:39:49", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("08:39:50", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
        ("08:41:52", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("08:44:14", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
    ]
    assert [p for p in replay("2026-08-22T08-36_08-50") if p[0] == "08:47:46"] == []


def test_19_aug_ballistic_wave_is_eight_sounds_in_twenty_six_minutes():
    """19 Aug 20:50-21:16, the corpus's heaviest raid: URGENT at 20:52:25, the first
    launch message any channel posted. AerisRimor's `ЦІЛЬ` -> `КИЇВ` -> `Балістика` ->
    `На Бровари!!` burst three seconds later resolves into that same event -- never a
    WATCH of its own -- and the seven waves that follow re-sound at most once every two
    minutes. Eight audible ballistic pushes in 26 minutes, the number BEHAVIOR.md
    measured, and the Zircon wave alongside them is three more on its own event.

    The third ballistic sound moved from 20:58:01 to 20:57:58, kpszsu's `Балістичні
    ракети на Сумщині, Чернігівщині та Полтавщині курсом на Київ.`: Kyiv-gating is now
    on the target, so the oblasts a wave crosses no longer suppress a call that says
    Kyiv is the target. The official channel gets three seconds it used to lose.

    The threat declaration at 20:52:17 is INFO: priority 2, silent by spec, not a sound.
    """
    assert [p for p in audible("2026-08-19T20-50_21-16")
            if p[3] == "БАЛІСТИКА на Київ"] == [
        ("20:52:25", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
        ("20:54:40", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("20:57:58", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:00:40", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:03:16", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:05:40", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:09:38", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:11:45", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
    ]
    assert [p for p in replay("2026-08-19T20-50_21-16")
            if p[3] == "Загроза балістики"] == [
        ("20:52:17", "NEW", "INFO", "Загроза балістики")]


def test_19_aug_launches_on_other_cities_stay_below_the_notifier():
    """The launch calls naming Ромни, Лубни, Миргород, Курщина and Чернігів push
    nothing, even while the Kyiv event is live."""
    non_kyiv = {"20:55:45", "20:55:51", "20:57:11", "20:57:12", "20:57:15", "20:57:21",
                "21:05:44", "21:09:29"}
    assert [p for p in replay("2026-08-19T20-50_21-16") if p[0] in non_kyiv] == []


def test_25_aug_a_bumped_target_call_never_becomes_a_kyiv_urgent():
    """25 Aug 20:54-20:58: the night's ballistics went to Ромни and Полтава. Before the
    bump was a no-op, nebo_raketa re-posting its own `🚀Ціль` as a reply opened a WATCH
    inside kpszsu's threat window, and kyiv_nebo's `Київ, зреагуйте` promoted it to a
    false URGENT -- the 25 Aug false positive BEHAVIOR.md records. Only the threat INFO
    is left."""
    assert replay("2026-08-25T20-54_20-58") == [
        ("20:55:17", "NEW", "INFO", "Загроза балістики"),
    ]


def test_resound_gap_is_configuration():
    """Widening the resound gap collapses the repeat launch calls into the body."""
    assert [p[1] for p in audible("2026-08-27T00-00_00-30", resound_gap_min=10)] == [
        "NEW", "PROMOTE", "NEW", "PROMOTE"]


def test_cold_burst_launch_on_kyiv_needs_no_prior_context():
    """SYNTHETIC fixture -- the one shape the corpus never supplies: a launch burst
    that opens with no declared threat and no ballistic word anywhere. SPEC story 4
    is unconditional, so naming Kyiv in a launch call is context enough.

    The last message is the same call with trailing punctuation, far enough after the
    first burst that the event has closed: it can only push via the launch branch, so
    it pins the `<PLACE> ЦІЛЬ!` family that AerisRimor and war_monitor actually type.
    """
    assert replay("synthetic-cold-launch-burst") == [
        ("08:39:50", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
        ("08:39:58", "UPDATE", "URGENT", "БАЛІСТИКА на Київ"),
        ("08:46:00", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
    ]


def test_29_aug_onyx_on_odesa_never_becomes_a_kyiv_alert():
    """29 Aug 02:33-02:40: an Onyx over the Azov-Black Sea approaches Odesa. The
    declared Crimea threat is a real INFO; nothing else may sound. `Ціль через АЧМ`,
    `Київ/Київщина — дорозвідка` and Odesa's `Київський район/Аркадія` must not
    combine into a Kyiv ballistic event. nebo_raketa's `Вишневе` is a real drone in the
    oblast and opens its own silent INFO -- a separate event key, no sound."""
    assert replay("2026-08-29T02-33_02-40") == [
        ("02:35:16", "NEW", "INFO", "БпЛА над Києвом"),
        ("02:35:23", "NEW", "INFO", "Загроза балістики"),
    ]


def test_19_aug_modifier_apostrophe_target_call_is_a_launch():
    """AerisRimor types `ЦІЛЬʼ` with U+02BC, which is a word character. The message
    names no place, so the launch branch is the only way it can push at all."""
    pushes = replay("2026-08-19T21-04_21-12")
    assert [p for p in pushes if p[0] == "21:09:38"] == [
        ("21:09:38", "RESOUND", "URGENT", "БАЛІСТИКА на Київ")]
    assert [p for p in pushes if p[1] in ("NEW", "PROMOTE", "RESOUND")] == [
        ("21:05:45", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("21:05:46", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:09:38", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("21:11:45", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
    ]


def test_a_kyiv_place_promotes_a_pending_launch_whatever_the_channel_said_before():
    """SYNTHETIC fixture -- the corpus never puts a drone report and a target-less
    ballistic WATCH close enough together to make the choice visible. Wording is
    verbatim from the corpus (AerisRimor's `Реактив сектор Білогородка - Бузова.` and
    `Київ увага!`, Ukrainian_Intelligence's `‼️ Вихід балістики з Брянська`).

    A target-less launch opens a WATCH 2 min after the channel's last drone post, and a
    bare `Київ увага!` follows 20 s later. SPEC promotes on "the next Kyiv place from
    ANY channel" with no type qualifier, so it promotes: only a drone word in the
    message's own text may veto, never an inherited or remembered type. Getting this
    wrong leaves the WATCH to expire and the household asleep.

    The opening drone report is its own silent INFO event (Білогородка is oblast, not the
    ring): drone and ballistic events share the message stream and nothing else.
    """
    assert replay("synthetic-drone-context-still-promotes") == [
        ("01:00:00", "NEW", "INFO", "БпЛА над Києвом"),
        ("01:02:00", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("01:02:20", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
    ]


def test_30_aug_the_ring_warns_before_home_wakes_the_house():
    """30 Aug 09:40-10:20, the nightly jet-drone loop Оболонь -> Нивки -> Вишневе.

    The ring warns first: AerisRimor puts the drone over Шулявка at 09:45:05, a minute
    before kyiv_nebo's bare `Нивки, Святошин` reaches the home set. kyiv_nebo alone is
    w=0.6 -- not enough to wake the house -- so that is a WATCH; AerisRimor's
    `Підвернув на анонов!` four seconds later is a second, independent pair of eyes
    (it names Антонов, which kyiv_nebo did not, so it is no echo) and the noisy-OR
    clears 0.8. One URGENT for a drone that circles overhead for the next 22 minutes;
    everything after is a body update on the same notification.
    """
    assert sounds("2026-08-30T09-40_10-20") == [
        ("09:41:27", "NEW", "INFO", "БпЛА над Києвом"),
        ("09:45:05", "NEW", "WATCH", "БпЛА поруч"),
        ("09:46:01", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("09:46:05", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_30_aug_typo_places_land_on_the_right_event():
    """`Нивки на Шулявку.` reaches the home set and updates the URGENT in place;
    AerisRimor's next line `Ні на Оболонь.` resolves to Оболонь -- Kyiv, but neither
    home nor ring -- and lands on the INFO event instead. Under the placeholder
    HOME=Оболонь of BEHAVIOR.md that same line fired an URGENT; with the real home set
    it must not, and the two lines must not end up on the same notification.
    """
    assert [p for p in replay("2026-08-30T09-40_10-20")
            if p[0] in ("09:50:32", "09:50:39")] == [
        ("09:50:32", "UPDATE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("09:50:39", "UPDATE", "INFO", "БпЛА над Києвом"),
    ]


def test_28_aug_every_home_pass_of_the_worst_night_rings_the_phone():
    """28 Aug 00:30-08:00, the corpus's worst night: a drone loops back over Нивки and
    Антонов all night. Every pass BEHAVIOR.md counted (00:35, 02:17, 02:45, 02:54,
    05:09, 05:41, 07:08, 07:55) rings, and nothing between them does -- the reports
    inside one pass are body updates on the live notification.

    06:31 is the pass war_monitor's loitering marker `🔄 Гостомель` keeps alive: without
    it the channel's 3-min type memory has expired by the time it posts the untyped
    `Київ / 2х Нивки Новобіличі, Пріорка` and the pass goes unreported.

    05:09 is the WATCH-then-promotion case: AerisRimor (w=0.7) alone says
    `2 реактива Оболонь - Нивки київ.` and that is a WATCH; nebo_raketa's bare `Нивки`
    41 s later is the second source that makes it URGENT. 07:55 is reply-chain
    progression: AerisRimor's lone `Антонов.` is a reply into the chain it has been
    tracking the drone through, so 0.7 is enough on its own.

    Nine passes, nine sounds -- the night BEHAVIOR.md describes as "9 alarms between
    00:35 and 07:55".

    06:32:14 is the tenth audible push and not a home pass: war_monitor's `🅿️ 2х
    Борщагівки, Святопетрівське` raises the ring event's count from nothing to two,
    fifteen minutes after the ring last rang. A count jump is one of the four things
    SPEC story 7 allows to sound again, and the per-tier cooldown gates it like any
    other sound.

    Four of these are the story-30 fallback (#9): reports naming the house or the ring
    that nothing could type -- nebo_raketa's bare `Софіївська Борщагівака` at 00:37:07,
    its `Виноградар` at 00:53:33 and `Святошинський район` at 03:21:34, and AerisRimor's
    `Йде Виноградар на Антонов!` at 00:54:16. All four are WATCH: an untyped report
    joins its zone's event weightless and can never wake the house by itself. The ring
    WATCH that used to open at 00:55:22 now opens at 00:53:33 -- 1 m 49 s earlier, on
    the same event -- and 00:55:22 is a body update on it.
    """
    assert audible("2026-08-28T00-30_08-00") == [
        ("00:35:53", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("00:37:07", "NEW", "WATCH", "БпЛА поруч"),
        ("00:53:33", "NEW", "WATCH", "БпЛА поруч"),
        ("00:54:16", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("02:17:14", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:45:44", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:54:38", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("03:21:34", "NEW", "WATCH", "БпЛА поруч"),
        ("05:09:08", "NEW", "WATCH", "БпЛА поруч"),
        ("05:09:37", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("05:10:18", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("05:41:12", "NEW", "WATCH", "БпЛА поруч"),
        ("05:41:58", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("06:17:12", "NEW", "WATCH", "БпЛА поруч"),
        ("06:31:29", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("06:32:14", "RESOUND", "WATCH", "БпЛА поруч"),
        ("07:05:30", "NEW", "WATCH", "БпЛА поруч"),
        ("07:08:12", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("07:51:24", "NEW", "WATCH", "БпЛА поруч"),
        ("07:55:39", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_28_aug_the_cooldown_changes_the_sounds_and_nothing_else():
    """The lever the owner gets for "nine alarms in seven hours" (SPEC story 33) is the
    per-tier cooldown, and it is the only thing that moves: same fixture, same rules,
    a wider URGENT cooldown, and the phone rings five times instead of nine. The
    notification count is identical -- the passes that no longer ring still update the
    body in place, so the shade is as current either way.
    """
    quiet = audible("2026-08-28T00-30_08-00", cooldown_min={"URGENT": 60})
    assert [p for p in quiet if p[2] == "URGENT"] == [
        ("00:35:53", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:17:14", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("05:10:18", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("06:31:29", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("07:55:39", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
    ]
    assert (len(replay("2026-08-28T00-30_08-00", cooldown_min={"URGENT": 60}))
            == len(replay("2026-08-28T00-30_08-00")))


def test_30_aug_drones_over_other_regions_never_reach_the_phone():
    """Reports whose only places are outside Kyiv and its oblast -- Чернігівщина,
    Полтавщина, Дніпропетровщина -- are stored like every other message and pushed
    nowhere, even while a drone is live over the home set (SPEC story 12)."""
    other_regions = {"09:59:46", "10:08:36", "10:10:00", "10:17:29"}
    assert [p for p in replay("2026-08-30T09-40_10-20")
            if p[0] in other_regions] == []


def test_faina_taun_resolves_to_the_home_set():
    """SYNTHETIC fixture -- the corpus never says `файна таун`, so it cannot supply this
    one. ЖК Файна Таун is where the household lives; ADR 6 makes it an alias of the home
    set, and war_monitor's own `Київ: 🅿️ 1х реактив <place>` template carries it.
    war_monitor is w=0.9, so one channel is enough to wake the house.

    The other home alias, AerisRimor's misspelt `анонов`, is exercised on the real
    30 Aug slice, where it is what promotes the home WATCH to URGENT at 09:46:05.
    """
    assert sounds("synthetic-home-alias-faina-taun") == [
        ("04:00:00", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_an_aggregator_echo_is_half_a_source_and_a_fresh_report_is_whole():
    """SYNTHETIC fixture -- the corpus never lands an echo where it would change a tier,
    so it cannot supply this one. Wording is verbatim (AerisRimor's `2 реактива Оболонь -
    Нивки київ.` of 28 Aug 05:09:37, kyiv_nebo's bare `Нивки`, Ukrainian_Intelligence's
    `Київ - реактивний на <place> ⚠️` template) with the home place substituted in.

    AerisRimor (w=0.7) alone is a WATCH. kyiv_nebo (w=0.6) ten seconds later adds no
    place AerisRimor had not already named -- the aggregator echo `channel-eval-kyiv_nebo`
    measured -- so it counts half and the house stays asleep (0.79). Ukrainian_Intelligence
    at the same w=0.6, fifty seconds later and outside the echo window, is a real second
    pair of eyes and wakes it. Same weight, same place: only the fifteen seconds differ.
    """
    assert sounds("synthetic-echo-is-half-a-source") == [
        ("03:30:00", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("03:31:00", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_the_ntfy_boundary_never_makes_an_info_or_an_update_audible():
    """The tier-to-priority mapping is what "INFO never sounds" actually rests on, so
    assert it where the household's phone sees it: INFO is 2 and a body update is 1,
    both below the threshold that rings anything, while URGENT is 5 and bypasses DND."""
    sent = []
    ntfy = notify.Ntfy({"url": "https://ntfy.example.net",
                        "topics": {"URGENT": "urgent", "WATCH": "all", "INFO": "all"}})
    with mock.patch.object(notify.urllib.request, "urlopen") as urlopen:
        urlopen.side_effect = lambda request, timeout=None: sent.append(
            json.loads(request.data)) or mock.MagicMock()
        for kind in ("NEW", "UPDATE"):
            for tier in ("URGENT", "WATCH", "INFO"):
                ntfy(Push(datetime(2026, 8, 28, 2, 17), kind, tier, "t", "b", "tag"))

    assert [(p["topic"], p["priority"]) for p in sent] == [
        ("urgent", 5), ("all", 4), ("all", 2),      # NEW: URGENT bypasses DND, INFO silent
        ("urgent", 1), ("all", 1), ("all", 1),      # UPDATE: a body update never sounds
    ]


def test_20_aug_cruise_missiles_watch_on_direction_then_urgent_on_approach():
    """20 Aug 02:20-02:30: a cruise-missile wave crosses Полтавщина/Чернігівщина and
    turns on Kyiv. war_monitor's `3 групи КР повз Переяслав у напрямку Києва` names a
    direction and no target, so it is a WATCH; AerisRimor's `БРОВАРИ ПІДЛІТ КР!` 63 s
    later names a Kyiv-oblast place with an approach word and promotes it to URGENT --
    the 2-3 minute budget before the first group is over the city.

    Before this, every one of those messages read as a drone body update (AerisRimor's
    `єППО на реактивні БПЛА і КР` had set the channel's type to drone), so the whole
    cruise approach arrived silent at priority 2.
    """
    assert sounds("2026-08-20T02-20_02-30") == [
        ("02:20:45", "NEW", "INFO", "БпЛА над Києвом"),
        ("02:26:37", "NEW", "WATCH", "Пуск ракет, ціль уточнюється"),
        ("02:27:40", "PROMOTE", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
    ]


def test_19_aug_zircon_wave_is_a_watch_then_an_urgent_with_the_count_it_was_given():
    """19 Aug 20:55-21:04: while the ballistic waves are still coming, Zircons launch
    from Курськ, Воронеж and Ростов. war_monitor's `Вихід другого Циркону, Курськ.`
    names no target and opens a missile WATCH at 20:56:34; Ukrainian_Intelligence's
    `5 Цирконів на Київ повз Прилуки, Ніжин та Пирятин` promotes it 66 s later --
    a launch that transits three other oblasts but says Kyiv is the target.

    The count is that channel's own figure, shown `>=5`, and it rises to `>=7` when
    war_monitor says `П'ятий, шостий та сьомий` -- never the sum of the two (SPEC 23).
    Before #5 every one of these pushed nothing at all: `5 Цирконів на Київ` was
    suppressed by the oblasts it flew over, and the rest were silent body updates on
    the ballistic notification.
    """
    zircons = [p for p in bodies("2026-08-19T20-50_21-16")
               if p[3] in ("Пуск ракет, ціль уточнюється", "КРИЛАТІ РАКЕТИ на Київ")
               and p[1] != "UPDATE"]
    assert [p[:4] for p in zircons] == [
        ("20:56:34", "NEW", "WATCH", "Пуск ракет, ціль уточнюється"),
        ("20:57:40", "PROMOTE", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
        ("21:03:10", "RESOUND", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
    ]
    assert zircons[1][4].startswith("≥5 ")
    assert zircons[2][4].startswith("≥7 ")


def test_19_aug_a_count_is_the_best_single_source_not_the_sum_of_five():
    """Five channels report launches into the 19 Aug Kyiv ballistic event and each
    counts the same missiles again: AerisRimor reaches `4 цілі`, kyiv_nebo `До 4 ракет`,
    Ukrainian_Intelligence `Ще 2`, war_monitor `Перша ... Сьома` and then `8 та 9`.
    Summing them is how the prototype printed `#48` for six missiles (BEHAVIOR.md
    fix 2). The largest figure any one channel gave is war_monitor's 9, and no push
    in the whole slice ever shows more than that.
    """
    shown = [int(re.match(r"≥(\d+)", p[4]).group(1))
             for p in bodies("2026-08-19T20-50_21-16") if p[4].startswith("≥")]
    assert shown, "expected counted pushes"
    assert max(shown) == 9
    reporting = {p[4].split(":")[0].split("· ")[-1] for p in bodies("2026-08-19T20-50_21-16")
                 if p[3] == "БАЛІСТИКА на Київ"}
    assert len(reporting) >= 5, reporting


def test_19_aug_a_launch_on_another_city_neither_sounds_nor_changes_the_count():
    """`Ціль на Ромни!` and `ЛУБНИ ЦІЛЬ!` arrive 40 s apart in the middle of a live
    Kyiv ballistic event and a live Zircon event. They open a log-only event of their
    own: no push at all, and the count on either Kyiv notification is the same one
    push before them as one push after (SPEC story 12)."""
    pushes = bodies("2026-08-19T20-50_21-16")
    assert [p for p in pushes if p[0] in ("20:57:11", "20:57:12", "20:57:15")] == []
    ballistic = [p for p in pushes if p[3] == "БАЛІСТИКА на Київ"]
    before = [p for p in ballistic if p[0] < "20:57:11"][-1]
    after = [p for p in ballistic if p[0] > "20:57:15"][0]
    assert before[4].startswith("≥4 ") and after[4].startswith("≥4 ")


def test_21_aug_a_relaunched_call_never_rings_twice_and_the_tail_wakes_nobody():
    """21 Aug 22:12-22:29, the end of the Бандероль wave. Two things must hold.

    nebo_raketa posts `Нові два Бандеролі залітаються на Згурівку у бік Броварів` at
    22:12:06 -- an approach word over Бровари, so URGENT -- and re-posts it verbatim as
    a reply 3 m 30 s later. `context` no longer recognises the bump: its parent left the
    3-min window. The event does, because the launch call it last folded in is the same
    string, so 22:15:36 is a body update and the phone stays quiet.

    Then the last one turns away down the Dnipro and AerisRimor calls `Канів підліт 5хв
    Бандероль.` twice. `підліт` is the word that wakes the house when it comes with a
    Kyiv place; with Канів and Черкащина it is somebody else's five minutes (story 12).
    """
    assert replay("2026-08-21T22-12_22-29") == [
        ("22:12:06", "NEW", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
        ("22:14:51", "NEW", "INFO", "БпЛА над Києвом"),
        ("22:15:21", "UPDATE", "INFO", "БпЛА над Києвом"),
        ("22:15:36", "UPDATE", "URGENT", "КРИЛАТІ РАКЕТИ на Київ"),
        ("22:18:42", "UPDATE", "INFO", "БпЛА над Києвом"),
        ("22:22:42", "UPDATE", "INFO", "БпЛА над Києвом"),
    ]
    assert [p for p in audible("2026-08-21T22-12_22-29") if p[0] > "22:12:06"] == []


def test_21_aug_a_bearing_on_kyiv_survives_the_oblasts_the_wave_crosses():
    """21 Aug 23:35-23:45: kpszsu (w=1.0) posts `Чернігівщина: "Бандероль" повз Ічню у
    напрямку Київщини.` -- the only Kyiv-ward signal any channel gives that night before
    the wave reaches Бровари twelve minutes later. It names Чернігівщина, so a gate on
    "names another city" would file it as somebody else's launch and push nothing.

    Kyiv-gating is on the target, and a bearing that says Kyiv is a target statement:
    WATCH, never an immediate URGENT (SPEC story 11).
    """
    assert replay("2026-08-21T23-35_23-45") == [
        ("23:39:15", "NEW", "WATCH", "Пуск ракет, ціль уточнюється"),
    ]


def test_19_aug_the_evening_essay_never_declares_a_threat():
    """19 Aug 18:11-18:20: war_monitor's nightly `Загальна оцінка загроз ... на ніч`
    briefing runs to 1.5k characters and mentions ballistics among everything else it
    surveys. It is an essay, not a report -- before it was filtered it pushed an INFO
    `Загроза балістики` three times in the corpus (story 22)."""
    assert replay("2026-08-19T18-11_18-20") == []


def test_the_kyiv_siren_is_a_signal_in_every_push_and_never_a_gate():
    """SYNTHETIC fixture -- the corpus has no `@air_alert_ua` file, so the siren feed
    cannot come from it. Wording follows the channel's own two lines, a region hashtag
    and a state (`🔴 #м_Київ / Повітряна тривога!`, `🟢 #м_Київ / Відбій тривоги!`).

    The siren feed carries no profile and no weight: it is read for one bit, the state
    of the siren in м. Київ, which every push then shows (SPEC story 24). Kharkiv's
    siren is not ours and moves nothing. And the bit never gates a tier -- the drone
    over the home set is URGENT under a live siren and URGENT after the all-clear.
    """
    pushes = bodies("synthetic-siren-signal")
    assert [p[:4] for p in pushes] == [
        ("04:00:30", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("04:02:00", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
        ("04:05:00", "UPDATE", "URGENT", "БпЛА НАД ДОМОМ"),
    ]
    assert "🔴" in pushes[0][4], pushes[0][4]
    assert "🟢" in pushes[2][4], pushes[2][4]


def test_28_aug_the_body_carries_the_chain_its_sources_and_the_age_of_the_report():
    """SPEC story 9, on the 05:09 pass of the corpus's worst night. AerisRimor opens the
    home event with `2 реактива Оболонь - Нивки київ.` and nebo_raketa's bare `Нивки`
    41 s later promotes it; the body of that one notification carries the chain the
    drone has flown, both channels that reported it, when the last report came in, the
    official siren and how many of the six channels are still talking.

    The full loop of AC 1, `Оболонь → Нивки → Вишневе`, spans two notifications and not
    one: the event key is the zone (#4), Нивки is the home set and Вишневе is neither
    home nor ring, so war_monitor's `через Оболонь у напрямку Вишневе` six seconds
    earlier updates the Kyiv-wide INFO instead. Each body shows its own places.
    """
    pushes = bodies("2026-08-28T00-30_08-00")
    home = [p for p in pushes if p[0] == "05:10:18"][0]
    assert home[:4] == ("05:10:18", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ")
    assert "Оболонь → Нивки" in home[4], home[4]
    assert "AerisRimor" in home[4] and "nebo_raketa" in home[4], home[4]
    assert "звіт 08:10:18 (щойно)" in home[4], home[4]
    assert re.search(r"\b[1-6]/6 каналів активні", home[4]), home[4]

    kyiv = [p for p in pushes if p[0] == "05:10:12"][0]
    assert kyiv[:4] == ("05:10:12", "UPDATE", "INFO", "БпЛА над Києвом")
    assert "Оболонь → Вишневе" in kyiv[4], kyiv[4]


def sent_payloads(*pushes):
    """What the ntfy client actually puts on the wire for these pushes."""
    sent = []
    ntfy = notify.Ntfy({"url": "https://ntfy.example.net",
                        "topics": {"URGENT": "urgent", "WATCH": "all", "INFO": "all"}})
    with mock.patch.object(notify.urllib.request, "urlopen") as urlopen:
        urlopen.side_effect = lambda request, timeout=None: sent.append(
            json.loads(request.data)) or mock.MagicMock()
        for push in pushes:
            ntfy(push)
    return sent


def test_the_ntfy_boundary_replaces_the_live_notification_and_links_the_source():
    """One event, one entry in the notification shade (SPEC story 6). ntfy links
    messages into a sequence: publish again with the same `sequence_id` and the client
    replaces the notification it already showed, rather than stacking a new one
    (docs.ntfy.sh/publish "Updating notifications", server + Android >= 2.16). The
    event tag is that id, so the trajectory updates in place.

    The source post rides along as ntfy's `view` action -- one tap opens the Telegram
    message the alert was read from (SPEC story 10).
    """
    when = datetime(2026, 8, 28, 2, 17)
    tag = "drone-home-20260828T021714"
    first, update = sent_payloads(
        Push(when, "NEW", "URGENT", "БпЛА НАД ДОМОМ", "AerisRimor: Нивки", tag,
             source="https://t.me/AerisRimor/12345"),
        Push(when, "UPDATE", "URGENT", "БпЛА НАД ДОМОМ", "nebo_raketa: Нивки", tag))

    assert first["sequence_id"] == tag and update["sequence_id"] == tag
    assert first["actions"] == [{"action": "view", "label": "Джерело",
                                 "url": "https://t.me/AerisRimor/12345"}]
    assert "actions" not in update      # nothing to link: no source, no button


def test_the_all_clear_is_one_silent_info_after_ten_quiet_minutes_and_a_clear_call():
    """SYNTHETIC fixture -- the household's own corridor signal, and the corpus has no
    slice that puts a home pass, a clear call and ten quiet minutes in one window.
    Wording is verbatim (war_monitor's `Київ: 🅿️ 1х реактив <place>` template,
    AerisRimor's `Чисто.`, war_monitor's oblast drone line).

    A drone over the home set wakes the house at 02:00. AerisRimor says it is clear a
    minute later, then nothing touches the home set or the ring for ten minutes: the
    household gets one silent INFO telling it to come out of the corridor (story 8),
    and only one -- the next message does not repeat it.
    """
    pushes = bodies("synthetic-all-clear-after-quiet")
    assert [p[:4] for p in pushes] == [
        ("02:00:00", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:12:00", "CLEAR", "INFO", "Відбій — БпЛА над домом"),
    ]
    # and the age of that last report is the point of it: twelve minutes of nothing
    assert "звіт 05:00:00 (12 хв тому)" in pushes[1][4], pushes[1][4]


def test_quiet_alone_is_never_an_all_clear():
    """SYNTHETIC fixture. The same night without the clear call: eleven quiet minutes
    pass with the Kyiv siren still sounding and no all-clear is sent -- a drone that
    stops being reported may just have stopped being seen (ADR 10). The official siren
    ending is the other half of the AND, and it releases the all-clear on the first
    message after it.
    """
    assert replay("synthetic-all-clear-needs-more-than-quiet") == [
        ("03:00:30", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("03:13:00", "CLEAR", "INFO", "Відбій — БпЛА над домом"),
    ]


def test_a_count_jump_over_the_home_set_rings_again():
    """SYNTHETIC fixture -- the corpus never raises a count over the home set outside
    the cooldown, so it cannot supply this one. Wording is war_monitor's own
    `Київ: 🅿️ Nх реактив <place>` template.

    One drone over the house wakes the household. Six minutes later the same channel
    says there are four: that is new information, not the same chatter, and SPEC story
    7 lists a count jump among the four things allowed to ring again. The count itself
    goes in the body, `≥4`, from the best single source (story 23). Restating four
    changes nothing -- the same count is the same fact, whatever the cooldown allows.
    """
    pushes = bodies("synthetic-count-jump")
    assert [p[:4] for p in pushes] == [
        ("02:00:00", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:06:00", "RESOUND", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:07:00", "UPDATE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:12:00", "UPDATE", "URGENT", "БпЛА НАД ДОМОМ"),
    ]
    assert pushes[1][4].startswith("≥4 "), pushes[1][4]


def test_the_system_topic_warns_when_every_channel_goes_quiet_under_a_siren():
    """SYNTHETIC fixture -- coverage going dark is the one thing the corpus cannot
    show, since the corpus is what the channels did post. The siren feed's own
    nationwide traffic is what keeps the clock running while the six are silent.

    A drone over the house at 03:30, the Kyiv siren from 03:30:05, and then nobody
    says anything for eleven minutes: the owner is told his eyes are shut (story 15).
    Once per siren, on the `system` topic, and never again while it lasts.

    03:30-03:45 UTC is inside kyiv_nebo's 03:00-07:00 blackout, so that channel's
    silence is its habit and is exempt -- the warning here is the other five.
    """
    pushes = sent("synthetic-silent-while-siren")
    assert [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title) for p in pushes] == [
        ("03:30:00", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("03:41:00", "SYSTEM", "INFO", "Канали мовчать під тривогою"),
    ]
    assert pushes[1].topic == "system"
    assert "kyiv_nebo" not in pushes[1].body, pushes[1].body
    assert "war_monitor" in pushes[1].body, pushes[1].body


def test_the_siren_state_is_stored_on_the_event(tmp_path):
    """Not just shown: kept, so the household can later ask how often an URGENT beat
    the siren (SPEC story 24). The events table is where the answer will come from.
    Read here at the store because that is the boundary the criterion names."""
    saved = stored("synthetic-siren-signal", tmp_path)
    assert saved.db.execute(
        "select title, siren from events order by opened").fetchall() == [
        ("БпЛА НАД ДОМОМ", "off"),        # its last report came after the all-clear
        ("БАЛІСТИКА на Київ", "on")]


def stored(fixture, tmp_path):
    """Replay a fixture into a `Store` and hand it back, for the two questions only the
    database can answer: what an event row says, and what a push joins to."""
    saved = store.Store(str(tmp_path / "home-alert.db"))
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["profiles"] = ROOT / "profiles"
    events.replay(reader.read_corpus(FIXTURES / f"{fixture}.jsonl"),
                  config, notify.Recorder(), saved)
    return saved


def test_a_drone_event_is_stored_like_any_other_minus_the_launches_it_never_had(tmp_path):
    """A drone event writes its own row, so the siren state at the time it woke the
    house is kept (#22). It has no launch concept -- no launch clock, nothing to count
    -- so those two columns are NULL rather than a zero that would read as a fact.
    """
    saved = stored("synthetic-siren-signal", tmp_path)
    assert saved.db.execute(
        "select tag, opened, last, tier, launches, places, sources from events "
        "where tag like 'drone-%'").fetchall() == [
        ("drone-home-20260828T040030", "2026-08-28T04:00:30", "2026-08-28T04:05:00",
         "URGENT", None, '["Київ", "Нивки"]', '["war_monitor"]')]


def test_urgent_without_a_siren_is_countable_for_drones_too(tmp_path):
    """SPEC story 24's question, asked of the database: which URGENTs woke the house
    with no official siren? Until #22 the answer could only ever be a ballistic or a
    missile one -- the threat types that wake it least.

    Every push joins to the event that produced it and to no other, which is what the
    tag is for: three URGENT pushes, three joined rows, no push credited twice and none
    credited to a neighbouring event.
    """
    saved = stored("synthetic-siren-signal", tmp_path)
    joined = saved.db.execute(
        "select n.title, e.tier, e.siren from notifications n "
        "join events e on e.tag = n.tag order by n.time").fetchall()
    assert joined == [
        ("БпЛА НАД ДОМОМ", "URGENT", "off"),
        ("БАЛІСТИКА на Київ", "URGENT", "on"),
        ("БпЛА НАД ДОМОМ", "URGENT", "off")]
    assert len(joined) == saved.db.execute(
        "select count(*) from notifications").fetchone()[0]

    assert saved.db.execute(
        "select n.time, n.title from notifications n join events e on e.tag = n.tag "
        "where n.tier = 'URGENT' and (e.siren is null or e.siren = 'off') "
        "order by n.time").fetchall() == [
        ("2026-08-28T04:00:30", "БпЛА НАД ДОМОМ"),
        ("2026-08-28T04:05:00", "БпЛА НАД ДОМОМ")]


def test_replay_over_the_live_database_reproduces_the_recorded_pushes(tmp_path, capsys,
                                                                     monkeypatch):
    """SPEC story 34 against the live trail instead of the corpus. Everything the agent
    receives is stored, so any night can be re-run through the current rules straight
    out of `data/home-alert.db` -- and re-running a night nobody has changed the rules
    for must reproduce, push for push, what the household was actually sent.

    The notifications table is the household's copy of that; comparing to it is the
    criterion's own boundary.
    """
    db = str(tmp_path / "home-alert.db")
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["profiles"] = ROOT / "profiles"

    live = store.Store(db)          # pass 1: a night, as `run` would have written it
    events.replay(reader.read_corpus(FIXTURES / "2026-08-27T00-00_00-30.jsonl"),
                  config, notify.Recorder(), live)

    again = notify.Recorder()       # pass 2: the same night, back out of the store
    events.replay(live.messages(datetime(2026, 8, 27), datetime(2026, 8, 28)),
                  config, again, store.Store(":memory:"))

    assert again.pushes, "expected the stored night to push something"
    assert [(p.time.isoformat(), p.kind, p.tier, p.title) for p in again.pushes] == \
        live.db.execute("select time, kind, tier, title from notifications").fetchall()

    monkeypatch.chdir(ROOT)         # and the same thing through the command line
    capsys.readouterr()
    assert cli.main(["replay", "2026-08-27T00:00", "2026-08-27T00:30",
                     "--db", db, "--from-db"]) == 0
    printed = capsys.readouterr().out
    assert printed.splitlines()[0].endswith("2026-08-27T00:00 .. 2026-08-27T00:30")
    assert "БАЛІСТИКА на Київ" in printed


def test_the_all_clear_follows_its_event_to_the_topic_it_woke_the_house_on():
    """ntfy identifies a notification by (server, topic, sequence_id), so the same tag
    on another topic is another notification. A home event that opens as a WATCH on
    `all` and is promoted to URGENT on `urgent` has to be closed on `urgent`: anywhere
    else and the household is left with a live alarm on the phone and an all-clear
    filed under a topic the family does not even subscribe to.

    The same fixture as the echo test, plus a clear call and eleven quiet minutes.
    """
    clear = [p for p in sent("synthetic-echo-is-half-a-source") if p.kind == "CLEAR"]
    assert [(f"{p.time:%H:%M:%S}", p.tier, p.title, p.topic) for p in clear] == [
        ("03:42:00", "INFO", "Відбій — БпЛА над домом", "urgent")]
    # and it is filed under the URGENT topic without ringing like one
    assert sent_payloads(clear[0])[0]["priority"] == 1


def test_28_aug_an_unparsed_report_over_the_house_still_reaches_the_household():
    """SPEC story 30, on the corpus's worst night. At 00:54:16 AerisRimor posts
    `Йде Виноградар на Антонов!` -- a real drone over the home set, twenty minutes
    into the raid, in wording no rule types: no drone word, no reply parent, and the
    channel's 3-minute type memory has expired. Before this it produced nothing at all.

    A rule gap must fail safe rather than silent, so it is a report at WATCH: the
    household is told something is over the house from one source, and only a typed
    report from a channel the owner trusts can raise that to the URGENT that wakes it.
    """
    assert ("00:54:16", "NEW", "WATCH", "БпЛА над домом — одне джерело") \
        in audible("2026-08-28T00-30_08-00")


def test_an_untyped_report_is_capped_at_watch_and_still_lets_two_sources_wake_the_house():
    """SYNTHETIC fixture -- the corpus never puts an untyped report and two typed ones
    close enough together to make either half of this visible. Wording is corpus
    wording (AerisRimor's `Реактив <place>.`, kyiv_nebo's bare `Нивки`) with an untyped
    call in war_monitor's voice.

    war_monitor is w=0.9: a *typed* drone it puts over the house wakes the household on
    its own. The same report in wording nothing can type is a WATCH and stays one -- the
    story-30 fallback folds it in weightless, and that is the whole of the cap.

    And it must not cost the household the wake-up it would have had: AerisRimor names
    only a place the untyped report already named, which for two real sources is the
    aggregator echo that counts half. A weightless report is not a source to be echoed,
    so AerisRimor is whole (0.7), kyiv_nebo's `Нивки` twenty seconds later is the second
    pair of eyes (0.6), and the noisy-OR reaches 0.88.
    """
    assert replay("synthetic-untyped-report-is-capped-at-watch") == [
        ("02:00:00", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("02:00:08", "UPDATE", "WATCH", "БпЛА над домом — одне джерело"),
        ("02:00:20", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_the_untyped_fallback_never_fires_on_an_ad_an_essay_or_another_city():
    """SYNTHETIC fixture. The fallback is for terse reports about our geometry that
    nothing could type -- not for the three things that also carry no type: a
    cross-promotion that happens to list the home set, a calm evening essay that
    mentions it, and a terse report about somebody else's city (SPEC stories 22, 12).
    """
    assert replay("synthetic-untyped-report-negatives") == []

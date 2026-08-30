from harness import audible, replay, sounds


def test_21_aug_ballistic_launch_watch_then_urgent():
    """21 Aug 21:54-22:06: AerisRimor's target-less `ЦІЛЬ` is a WATCH at 21:58:35,
    promoted to URGENT one second later when Ukrainian_Intelligence names Kyiv."""
    assert sounds("2026-08-21T21-54_22-06") == [
        ("21:56:24", "NEW", "INFO", "Загроза балістики"),
        ("21:58:35", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("21:58:36", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
    ]


def test_21_aug_trajectory_and_impact_never_sound():
    """Everything after the promotion is a silent body update."""
    after = [p for p in replay("2026-08-21T21-54_22-06") if p[0] > "21:58:36"]
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
    minutes. Eight audible pushes in 26 minutes, the number BEHAVIOR.md measured.

    The threat declaration at 20:52:17 is INFO: priority 2, silent by spec, not a sound.
    """
    assert audible("2026-08-19T20-50_21-16") == [
        ("20:52:25", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
        ("20:54:40", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("20:58:01", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
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

    05:09 is the WATCH-then-promotion case: AerisRimor (w=0.7) alone says
    `2 реактива Оболонь - Нивки київ.` and that is a WATCH; nebo_raketa's bare `Нивки`
    41 s later is the second source that makes it URGENT. 07:55 is reply-chain
    progression: AerisRimor's lone `Антонов.` is a reply into the chain it has been
    tracking the drone through, so 0.7 is enough on its own.

    BEHAVIOR.md's ninth alarm of that day is `Нивки реактив!` at 15:28 -- outside this
    slice. Eight passes fall in 00:30-08:00 and eight sound.
    """
    assert audible("2026-08-28T00-30_08-00") == [
        ("00:35:53", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("00:55:22", "NEW", "WATCH", "БпЛА поруч"),
        ("02:17:14", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:45:44", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:54:38", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("05:09:08", "NEW", "WATCH", "БпЛА поруч"),
        ("05:09:37", "NEW", "WATCH", "БпЛА над домом — одне джерело"),
        ("05:10:18", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("05:41:12", "NEW", "WATCH", "БпЛА поруч"),
        ("05:41:58", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("06:17:12", "NEW", "WATCH", "БпЛА поруч"),
        ("07:05:30", "NEW", "WATCH", "БпЛА поруч"),
        ("07:08:12", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("07:51:24", "NEW", "WATCH", "БпЛА поруч"),
        ("07:55:39", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
    ]


def test_28_aug_the_cooldown_changes_the_sounds_and_nothing_else():
    """The lever the owner gets for "nine alarms in seven hours" (SPEC story 33) is the
    per-tier cooldown, and it is the only thing that moves: same fixture, same rules,
    a wider URGENT cooldown, and the phone rings four times instead of eight. The
    notification count is identical -- the passes that no longer ring still update the
    body in place, so the shade is as current either way.
    """
    quiet = audible("2026-08-28T00-30_08-00", cooldown_min={"URGENT": 60})
    assert [p for p in quiet if p[2] == "URGENT"] == [
        ("00:35:53", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("02:17:14", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
        ("05:10:18", "PROMOTE", "URGENT", "БпЛА НАД ДОМОМ"),
        ("07:08:12", "NEW", "URGENT", "БпЛА НАД ДОМОМ"),
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

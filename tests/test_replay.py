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
    """
    assert sounds("2026-08-27T00-00_00-30") == [
        ("00:00:18", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("00:00:39", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
        ("00:02:47", "RESOUND", "URGENT", "БАЛІСТИКА на Київ"),
        ("00:09:50", "NEW", "INFO", "Загроза балістики"),
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
    combine into a Kyiv ballistic event."""
    assert replay("2026-08-29T02-33_02-40") == [
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
    """
    assert replay("synthetic-drone-context-still-promotes") == [
        ("01:02:00", "NEW", "WATCH", "Пуск балістики, ціль уточнюється"),
        ("01:02:20", "PROMOTE", "URGENT", "БАЛІСТИКА на Київ"),
    ]

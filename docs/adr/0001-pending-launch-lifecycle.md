# ADR-0001: Pending-launch lifecycle — what opens a ballistic WATCH, and what promotes it

Status: **Accepted** — 2026-09-01. Resolves [#14](https://github.com/LeStatV/home-alert/issues/14) (split from #12, items 1, 2, 6, 25).

## Context

A ballistic launch is usually announced before its target is known: `ЦІЛЬ`, `Вихід
балістики з Брянська`. The agent opens a **pending** event — a WATCH titled `Пуск
балістики, ціль уточнюється` — and promotes it to URGENT when a Kyiv place is named.
Four questions about that window were raised across the #2–#10 reviews and answer to
each other, so they are decided together.

The corpus is `research/samples-2026-08-30/*.jsonl`; the replay slices under
`tests/fixtures/` are the measurement surface.

## Decisions

### 1. A bare, contextless `ЦІЛЬ` does **not** open a pending WATCH

A launch call opens a pending ballistic event only with ballistic context: a declared
threat within the 15-minute window, an already-live ballistic event, or a Kyiv place
named in the launch itself. `home_alert/events.py`, stage 2:

```python
ballistic_context = (parse.names_ballistic or "ballistic" in self.live
                     or (self.threat_until is not None
                         and message.time <= self.threat_until))
```

This is the gate that removes the 25 Aug 20:55 false URGENT that `research/BEHAVIOR.md`
records. Verified by removing it: nebo_raketa's 20:54:43 `🚀Ціль` reopens a WATCH and
kyiv_nebo's 20:55:30 `Київ, зреагуйте` promotes it to `БАЛІСТИКА на Київ`. Pinned by
`tests/test_replay.py::test_25_aug_a_bumped_target_call_never_becomes_a_kyiv_urgent`.

SPEC story 5 read unconditionally and is amended to match.

### 2. Any Kyiv place from any channel promotes, minus recon

Promotion wording stays wide: a terse Kyiv place name from any channel promotes a
pending event, excluding recon (`дорозвідк`, `rules.RECON`).

The narrower alternative — promote only on launch-or-trajectory wording, which would
also exclude reassurance like `Київ, зреагуйте` — was measured and buys nothing while
decision 1 stands: the one false promotion the corpus contains is already killed
upstream. It costs nothing either. It is not built until live traffic produces a false
promotion the context gate does not catch.

**These two decisions are coupled.** If decision 1 is ever reversed, the wording
restriction stops being optional — the bump no-op cannot help, because the *first*
post is what opens the event.

### 3. Inherited drone type does not veto ballistic promotion

During a pending ballistic launch, a bare Kyiv place name promotes even when the
channel's last typed post was drone chatter. A veto is only armed on a drone word in
the message's own text.

Monitoring channels post drone chatter almost continuously during a raid, so a
context-inherited veto would be armed in most 90-second pending windows. That is not a
narrow guard — it is close to disabling cross-channel promotion exactly when promotion
matters.

### 4. Edits stay store-only

An edited message is stored and never re-enters the rules, so a channel editing
`ЦІЛЬ` → `ЦІЛЬ КИЇВ` in place does not promote a pending WATCH.

Unmeasurable: the stored history carries no edit field, so the corpus cannot say how
often channels edit rather than re-post. Deferred until live traffic shows it. The
narrow fix, written down so it need not be re-derived: let an edit through the rules
only when it newly names a Kyiv place *and* the event is still pending.

## Consequences

- No code change. All four decisions describe what ships; the divergence was between
  the code and SPEC story 5, and the SPEC is what moves.
- One known blind spot accepted: edits (decision 4). One known risk accepted: a
  reassurance or non-threat message naming Kyiv inside a 90 s pending window can
  promote (decision 2).
- `research/BEHAVIOR.md`'s † note ("fix = resound only after a confirmed, non-pending
  event") is already implemented — `events.py` gates RESOUND on `not event.pending`.

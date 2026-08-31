# Spec: home-alert v1 — Telegram-monitored air-threat notifier for a Kyiv household

Published as https://github.com/LeStatV/home-alert/issues/1 (label `ready-for-agent`). The issue is the canonical copy; this file mirrors it.
Sources of truth: `research/ARCHITECTURE.md` (ADR, 20 decisions), `research/BEHAVIOR.md` (attack model + replay results), `research/RESEARCH.md`, corpus `research/samples-2026-08-30/*.jsonl`.

## Problem Statement

Air-raid sirens in Kyiv fire for the whole city and carry no threat type. Most alerts are irrelevant to a specific household (a drone over Бориспіль, a cruise missile toward Полтава), while the alerts that matter — a jet drone over Нивки/Антонов, ballistic missiles launched at Kyiv — give 2–3 minutes of warning and are only visible by reading four or five Telegram monitoring channels in parallel, each with its own wording, threading, typos, ads and blind spots. A family cannot do that at 03:00; the result is either sleeping through a real threat or waking for every siren and eventually muting everything.

## Solution

A single home-hosted agent reads a curated set of Telegram channels through a Telethon user session, understands each message in the context of its channel (reply chains, bursts of terse posts, per-channel vocabulary), fuses reports into scored *events*, and pushes to the family's phones via self-hosted ntfy at one of three tiers: **URGENT** (bypasses Do-Not-Disturb: a drone at the HOME set, a ballistic/missile *launch* toward Kyiv), **WATCH** (audible, respects DND: a drone in the NEARBY ring, a launch with target not yet named), **INFO** (silent: drones entering Kyiv oblast, declared ballistic threats, all-clear). Notifications are per event, replaced in place as the trajectory updates, re-sounded only when something genuinely new happens. Channel knowledge lives in YAML profiles that an LLM drafts and a human approves; the live alerting path is deterministic and never waits on an LLM. Everything received and sent is stored in SQLite so the household can review "what happened last night" and tune the rules.

## User Stories

1. As a household member, I want my phone to wake me only when a drone is reported over my home set or a ballistic missile is launched toward Kyiv, so that I react to real danger and don't learn to ignore the app.
2. As a household member, I want an audible-but-DND-respecting heads-up when a drone is reported in the neighbouring districts, so that I can move toward shelter before it reaches us.
3. As a household member, I want declared ballistic *threats* (`Загроза балістики`) to appear silently, so that I'm informed without being woken for something that may never launch.
4. As a household member, I want a URGENT push within seconds of the first channel reporting `Балістика на Київ` / `ЦІЛЬ` + `КИЇВ`, so that I use the whole 2–3 minute budget before impact.
5. As a household member, I want a terse `ЦІЛЬ` with no target to arrive as WATCH and be promoted to URGENT the moment any channel names a Kyiv place, so that speed and precision are both preserved.
6. As a household member, I want one live notification per event whose body updates with the trajectory (`Антонов → Вишневе → Борщагівка`), so that my notification shade isn't flooded with 80 entries during a raid.
7. As a household member, I want the alarm to re-sound only on tier promotion, a new launch after ≥2 min, a count jump, or a new event after a ≥10 min quiet gap, so that repeated chatter about the same drone doesn't keep ringing.
8. As a household member, I want a silent all-clear once the home/nearby sets have been quiet for 10 minutes *and* a channel said clear or the Kyiv siren ended, so that I know when to come out of the corridor.
9. As a household member, I want the notification body to show which channels reported it, how old the report is, how many channels are currently active, and the official siren state, so that I can judge how much to trust it.
10. As a household member, I want a "view" action opening the source Telegram post, so that I can read the original when I want detail.
11. As a household member, I want cruise/hypersonic missiles (`Циркон`, `КР`, `Бандероль`) toward Kyiv treated with the same seriousness as ballistics (WATCH on `у напрямку Києва`, URGENT on `на Київ` / `підліт` / `над містом`), so that the 19 Aug Zircon wave would have woken me.
12. As a household member, I want reports about other cities (`Ціль на Ромни!`, `балістика на Каменское`) never to trigger anything above a log entry, so that Kyiv alerts stay precise.
13. As the owner, I want to define HOME and NEARBY as lists of microdistrict names with aliases and typo tolerance (`файна таун` and `анонов` must resolve to my home set), so that I don't need coordinates or a map.
14. As the owner, I want to subscribe family phones to `urgent` only and my own phone to `all`, so that each person gets the tiers they can handle.
15. As the owner, I want a `system` topic that tells me when the agent is down, Telegram disconnected, or all channels have been silent while a Kyiv siren is on, so that I know when coverage has gone dark.
16. As the owner, I want each channel to carry a trust weight I set, with URGENT firing immediately from a single channel with weight ≥ 0.8 and weaker channels needing a second source (or reply-chain progression), so that latency and false alarms are balanced the way I choose.
17. As the owner, I want a ballistic launch toward Kyiv from any channel with weight ≥ 0.6 to be URGENT without corroboration, so that a 2-minute budget is never spent waiting.
18. As the owner, I want the agent to understand that a child message in a reply chain (`1х далі Білогородка`) inherits the parent's type and count, so that threaded channels are read correctly.
19. As the owner, I want consecutive terse posts from one channel within 45 s treated as one burst (`ЦІЛЬ` → `КИЇВ` → `На Бровари!!`), so that AerisRimor-style channels are understood.
20. As the owner, I want a channel's "current threat type" remembered for ~3 minutes, so that a bare `Троя.` after `реактив` 2 minutes earlier is still classified as a drone.
21. As the owner, I want identical text re-posted as a reply (the "bump" pattern) never to create a new event, so that bumps don't re-alarm.
22. As the owner, I want ads, cross-promotions and essays (`Хто ще досі не підписаний на @Kyiv?`, evening "no threat tonight" posts, `ЗБИТО/ПОДАВЛЕНО 186 ЦІЛЕЙ` summaries) dropped before classification, so that marketing never produces an alert.
23. As the owner, I want counts shown as `≥N` taken from the best single source (`Четверта`, `8 та 9`, `застосовано 6 ракет`), not summed across channels, so that six missiles don't read as forty-eight.
24. As the owner, I want the official siren feed read as a *signal* shown in pushes and stored per event — never as a gate — so that the 1–3 minute head-start over the siren is preserved and I can later analyse "URGENT without siren" cases.
25. As the owner, I want every received message stored with its parse result, every event, and every notification sent, so that I can replay and audit any night.
26. As the owner, I want to run `add-channel @handle`, have the last ~500 messages fetched, an LLM draft a profile (weight placeholder, threading flag, noise patterns, vocabulary, place aliases, ~30 labelled examples) and a rules coverage report printed, and then approve/edit and set the weight myself, so that adding a channel takes minutes and stays under my control.
27. As the owner, I want a `review` command (nightly and on demand) that takes unclassified or low-confidence messages from the last 24 h and proposes profile diffs — never auto-applied — so that profiles improve over time without surprise behaviour changes.
28. As the owner, I want the LLM provider to be one config line (OpenAI-compatible endpoint such as OpenRouter/Ollama/OpenAI), so that I can switch when free tiers change or vanish.
29. As the owner, I want the LLM used on the live path only for messages the rules could not fully classify, with a 3-second timeout and fail-open to the rules verdict, so that an LLM outage or rate limit never delays or blocks an alert.
30. As the owner, I want an unparsed message that names a HOME/NEARBY place to still produce a WATCH, so that a rule gap fails safe rather than silent.
31. As the owner, I want the agent packaged as `docker compose` with `agent` and `ntfy` services, persistent volumes for the Telethon session and SQLite, and an interactive first start for the Telegram login, so that deployment on the home server is a single command.
32. As the owner, I want a ballistic/missile launch to be processed with no LLM call, no corroboration wait and no I/O other than the ntfy request, so that latency from Telegram update to push is well under a second.
33. As the owner, I want the drone cooldown per tier (5/10/20 min) and the resound gap (2 min) to be configuration, so that I can tune the 28 Aug "nine alarms in seven hours" experience without code changes.
34. As the owner, I want to replay any date range of the stored corpus against the current rules and see what would have been pushed, so that every rule change is validated against real raids before it goes live.
35. As a developer, I want each profile's labelled examples to run as tests, so that a vocabulary edit that breaks classification fails immediately.
36. As a developer, I want an end-to-end replay test harness (fake clock, corpus feed, stubbed LLM, recorded notifications), so that behaviour is asserted from the outside and the internals can be refactored freely.
37. As a household member, I want the agent to keep working when the LLM, the siren feed, or any one channel is unavailable, so that partial outages degrade gracefully instead of silencing everything.
38. As the owner, I want the Telethon session file and ntfy credentials kept on a protected volume and never logged, so that full Telegram account access doesn't leak.

## Implementation Decisions

**Data source.** Telegram only, via a Telethon *user* session (push updates, edits, no message-count limit). The account must join every configured channel. NEPTUN and the siren-map APIs are explicitly rejected as sources (false ballistic reports observed). Initial channel set: `@war_monitor` (0.9), `@nebo_raketa` (0.8), `@AerisRimor` (0.7), `@Ukrainian_Intelligence` (0.6), `@kpszsu` (1.0, official anchor), `@kyiv_nebo` (0.6, supplement: cleanest and most Нивки-specific source, but a daily 03:00–07:00 UTC blackout and bare place-name posts — see `research/channel-eval-kyiv_nebo.md`), plus `@air_alert_ua` read only for siren state.

**Runtime.** One Python 3.12 asyncio process on the home server (VPS standby deferred). Modules: `reader` (Telethon → normalized message: channel, id, time, reply_to, text, edit flag), `filter` (noise), `rules` (classification), `llm` (enrichment client), `events` (fusion, scoring, cooldowns, sound policy), `notify` (ntfy), `store` (SQLite), plus CLI entry points `run`, `add-channel`, `review`, `replay`. Config is one YAML file (home/nearby sets, tiers, cooldowns, ntfy, LLM provider) plus one YAML profile per channel; secrets via environment.

**Geometry.** No coordinates. `home` and `nearby` are sets of canonical place names; v1 defaults are `home = {Нивки, Антонов}` with aliases `файна` / `файна таун` (ЖК Файна Таун) and `анонов`, and the NEARBY ring listed in the ADR. A gazetteer maps stem patterns and aliases to canonical names (`троя` → Троєщина, `ГОЛОС` → Голосіїв, `Соф борщага` → Борщагівка); profiles may add per-channel aliases. Tier by place: HOME → URGENT, NEARBY → WATCH, other Kyiv city/oblast → INFO, elsewhere → log only. Non-Kyiv place names in a launch message make it a separate, log-only event.

**Message understanding (rules first).** Pipeline per message: noise filter (links, other-channel mentions, promotional vocabulary, media-only, long-form essays) → context assembly → rules → optional LLM enrichment → event update.
Context assembly: (a) reply-chain inheritance of type/count from the parent; (b) *burst*: consecutive messages from the same channel ≤ 45 s apart are one context; (c) per-channel current-type memory ≤ 3 min; (d) the "bump" (identical text re-posted as a reply) is a no-op.
Rules produce a `Parse`: type ∈ {drone, ballistic, missile, kab, recon, clear, threat, unknown}, stage ∈ {threat, launch, trajectory, impact, clear}, places[], count, target_is_kyiv, confidence. Type vocabulary is global with per-profile extensions.

**Missile/ballistic three-stage model** (validated on 19, 21, 22 and 27 Aug events; from the prototype):
```
THREAT   "Загроза (застосування) балістики", "Балістична небезпека"
         → INFO once per 15-min window; opens ballistic context
LAUNCH   "ЦІЛЬ"/"Ціль!"/"ЩЕ ЦІЛЬ", "🚀 Пуск"/"🚀 Ще", "Балістика на Київ",
         "спуск балістики", "вихід/виходи ... на Київ", "N балістик на Київ"
         · message ≤ 140 chars, not past-tense/summary, no non-Kyiv place
         · target named & Kyiv          → URGENT (any channel w ≥ 0.6)
         · target absent                → WATCH "pending", expires after 90 s;
                                          promoted to URGENT by the next Kyiv
                                          place from ANY channel
TRAJECT. bare place names while event active (≤ 5 min since last launch)
         → body update (replace-in-place), never a sound
IMPACT/  "вибухи", "чисто", "зникли", "втрачена", "мінус", "відбій"
CLEAR    → body update; event closes after 5 min without launches
RESOUND  new launch form while event active and ≥ 2 min since last sound;
         a pending (target-less) event never resounds — it stays WATCH until promoted
COUNT    max over channels of that channel's own ordinal/number, shown "≥N"
```
The launch path is synchronous: Telethon update → rules → ntfy; no LLM, no corroboration, no DB write before the push (persist after).

**Drone events.** Event key = (type, place-tier). Confidence = noisy-OR over distinct channels' weights within an 8-min window; a channel that posts the same fact within 15 s of another (aggregator echo, e.g. kyiv_nebo after UI/AR) counts as a partial, not a full, second source. URGENT immediately from one channel with w ≥ 0.8; lower-weight single source → WATCH, promoted on a second channel or reply-chain progression. Cooldowns per tier (URGENT 5 min, WATCH 10, INFO 20) gate *sounds*; body updates are unlimited but coalesced (replace-in-place via a stable ntfy tag per event). All-clear: INFO once after ≥ 10 min without HOME/NEARBY reports AND (a clear message OR Kyiv siren ended).

**Silence and contradictions.** No weight penalty for quiet channels; `last_post_age` per channel is tracked and shown as `N/5 каналів активні`; the `system` topic warns when all channels are silent while the Kyiv siren is on. `збили/чисто/зникли` never cancel an active URGENT by themselves.

**LLM.** Provider behind one interface: OpenAI-compatible chat client (OpenRouter free tier: 20 rpm / 50 per day, 1000 per day after $10; Ollama; OpenAI). Live path: only for `unknown`/low-confidence parses, 3 s timeout, result may raise tier or add places, never lower a rules verdict; failure → rules verdict stands; a provider that cannot be called at all fails at startup instead (#24). Offline: `add-channel` profile drafting and `review` diff proposals. Unofficial Copilot proxies are out.

**Profiles as data.** `profiles/<channel>.yaml`: `channel, weight, language, threads_by_reply, default_type (type assumed for bare place-name posts; kyiv_nebo: drone), quiet_hours (window exempt from silent-channel warnings; kyiv_nebo: 03:00–07:00 UTC), noise_patterns[], type_vocab{}, place_aliases{}, examples[]` where each example is `{text, type, stage, places, count}` and doubles as a test. `add-channel` writes a draft and a coverage report; a human edits and commits. `review` writes proposed diffs to a review file, never to the profile.

**Notifications.** Self-hosted ntfy with authentication, reachable via Tailscale or a tunnel. Topics `urgent`, `all`, `system`. Priority mapping URGENT=5, WATCH=4, INFO=2. Every push carries: tier emoji, event title, places/trajectory, sources, age, channels-active, siren state, a "view source" action; stable tag per event for replace-in-place. iOS requires ntfy's upstream (APNS relay) configured; Android instant delivery recommended.

**Storage.** SQLite: `messages` (raw + parse), `events`, `notifications`, `channel_state`. Retention unbounded for v1. `replay <from> <to>` re-runs the rules over stored messages and prints the would-be notification sequence.

**Packaging.** `docker compose` with `agent` and `ntfy`; volumes for session file and DB; first start interactive for Telegram login; secrets via env; session volume permissions locked down.

## Testing Decisions

A good test feeds messages in at the reader boundary and asserts what leaves at the ntfy boundary; it never inspects event objects, scoring internals or DB rows. Time is injected (fake clock driven by message timestamps), the LLM is stubbed (returns `unknown` unless a test provides a canned answer), the siren feed is a message stream like any channel, and ntfy is replaced by a recorder.

**Seam 1 — replay → notifications (primary, end-to-end).** Fixtures are slices of the real corpus (JSONL: channel, id, date, reply_to, text). Assertions are ordered lists of `(time, kind, tier, title)`; bodies are matched loosely. Required scenarios, all taken from `research/BEHAVIOR.md`:
- 19 Aug 20:50–21:16: URGENT at 20:52:25; Antonov/Святошин appear in the body; ≤ 8 sounds; non-Kyiv `Ціль на Ромни!` produces nothing above a log entry; Zircons produce missile WATCH/URGENT.
- 21 Aug 21:54–22:06: `ЦІЛЬ` → WATCH at 21:58:35, URGENT by 21:58:40; declared threats produce exactly one INFO.
- 22 Aug 08:36–08:50: URGENT by 08:39:52, before the kpszsu post; past-tense `Цілі були…` does not re-sound.
- 27 Aug 00:00–00:30: URGENT at ~00:01:34, 25 minutes before kpszsu.
- 28 Aug 00:30–08:00 with HOME = {Нивки, Антонов}: the nine reported passes each yield a sound under a 5-min cooldown; body updates are replace-in-place; changing the cooldown in config changes the count.
- 30 Aug 09:40–10:20: WATCH for the ring before URGENT for HOME; `Ні на Оболонь.`-style typos resolve; INFO never sounds.
- Noise: `@Kyiv` promo, evening essays, `ЗБИТО/ПОДАВЛЕНО` summaries produce nothing.
- Bump: identical reply re-post produces no new event.
- Degradation: LLM stub raising/timing out changes nothing on the launch path; a channel going silent changes the `N/5` label only.
- Failover of understanding: an unparsed message naming a HOME place → WATCH.

**Seam 2 — profile examples → classifier.** Every `examples[]` entry in every profile is a parametrized test: text (with the profile's context flags) → expected type/stage/places/count. Global vocabulary has its own example table. This is the fast feedback loop for vocabulary and alias edits.

Prior art: the research prototype (`sim.py`, `timeline.py`) already replays JSONL slices and prints the push sequence; the harness generalizes that shape. There is no existing test suite in the repo.

## Out of Scope

- VPS standby / failover, multi-instance coordination.
- Coordinates, distance rings, bearing computation, maps.
- Reading restricted channels that need account membership beyond joining (e.g. `@Nikolaevskiy_Vanek`).
- Automatic weight adjustment or auto-applied profile changes.
- Web UI / dashboard; timelines are CLI/SQL for v1.
- Per-person routing logic inside the agent (handled by ntfy topic subscriptions).
- KAB, reconnaissance UAV and aviation (МіГ-31К) tiers — logged, not notified.
- Siren gating of alerts.
- Any NEPTUN or alerts.in.ua integration.
- Historical backfill beyond what the Telethon account can fetch at `add-channel` time.

## Further Notes

- The corpus (18–30 Aug 2026, ~8.6k messages, five channels) includes four real ballistic events on Kyiv and a nightly jet-drone loop `Оболонь → Нивки → Вишневе`; it is the regression suite and should be committed as fixtures.
- GitHub Models (free gpt-4o API) was retired 30 Jul 2026; the Copilot SDK turned out to be an agentic-session driver, not a completion API, and bills one premium request per prompt — adapter removed (#24, ADR 8). Design assumes the LLM may be absent.
- Open decisions left to the owner, with defaults: drone URGENT cadence during a multi-hour raid (default: 5-min cooldown), personal vs dedicated Telegram account (default: dedicated). Channel weights, HOME/NEARBY sets and aliases are decided (see Data source and Geometry).
- Ballistic and missile events on other cities are stored and visible in `replay`, useful later for widening HOME to other family locations.

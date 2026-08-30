# Attack behaviour model — from replaying the 18–30 Aug corpus

Tooling: `samples-2026-08-30/timeline.py <from> <to>` (merged multi-channel timeline),
`sim.py "<from> <to>" ...` (prototype 3-stage state machine, placeholder HOME=Оболонь).
Corpus: 8.6k messages, 5 channels, 18–30 Aug 2026 (`*.jsonl`).

## Ballistic attacks observed on Kyiv
| date (UTC) | first launch msg | kpszsu launch msg | explosions | descents reported |
|---|---|---|---|---|
| 19 Aug 20:52 | UI 20:52:25 `Балістика на Київ!`; AR 20:52:28 `ЦІЛЬ` | 20:53:35 (+70 s) | 20:55:22 (+3 min) | 9 (WM counts «Перша…Сьома, 8 та 9») + 7 Zircons |
| 21 Aug 21:58 | AR 21:58:35 `ЦІЛЬ`; UI 21:58:36 `Балістика на Київ!` | 22:00:33 (+2 min) | 22:00:27 (+2 min) | 5 |
| 22 Aug 08:39 | AR 08:39:49 `ЦІЛЬ`; UI 08:39:50 `КИЇВ ЦІЛЬ` | 08:40:04 (+15 s) | ~08:44 (Бориспіль) | 6 (NR: «застосовано 6 ракет») |

Warning budget from first launch message to explosions: **2–3 min**. Monitors lead kpszsu by 15–120 s.

## The 3 stages, with real vocabulary
1. **THREAT** (minutes–hours before; often none at all on 19 Aug — WM's threat came 13 s *after* AR's `ЦІЛЬ`):
   `Загроза балістики з Брянська/Курська`, `☄️ Загроза застосування балістичного озброєння з півночі`, `🚨 Тривога. Балістична небезпека`, NR evening essays. → **INFO once per threat window**, sets `ballistic_context = 15 min`.
2. **LAUNCH** (t=0): `ЦІЛЬ` / `ЦІЛЬ!` / `ЦІЛЬʼ` / `ЩЕ ЦІЛЬ!` / `ДРУГА ЦІЛЬ!` / `2 ЦІЛІ` (AR), `🚀 Ціль!` / `🚀 Пуск` / `🚀 Ще` / `Дві цілі` (NR), `Балістика на Київ!` / `КИЇВ ЦІЛЬ` / `Ще 2 балістики на Бровари!` (UI), `☄ Вихід у напрямку Києва` / `‼️Київ — спуск балістики! Друга…` / `☄ Виходи балістики на Бориспіль` (WM), `🚀Балістичні ракети на Київ з півночі` / `Повторно…` (PS).
   Target is frequently **not in the launch message** — it arrives 1–10 s later in the same channel's burst: `ЦІЛЬ` → `КИЇВ` → `Балістика` → `На Бровари!!`.
3. **TRAJECTORY** (t+5 s … t+90 s): bare place names, often typo'd, one per message, 2–10 s apart, second-person: `Третя на Оболонь!`, `2 над Дарницею!`, `АНТОНОВ/Коцюба!!`, `Курс Оболонь!`, `ВАСИЛЬКІВ НАД ВАМИ!`, `ГОЛОС!` (=Голосіїв), `Троя` (=Троєщина), `Вищневе`, `Відрадниц`. NR/UI echo the same places 1–5 s after AR.
4. **IMPACT / CLEAR**: `💥 Вибухи у Києві` (WM), `Чисто по ракетам` / `Чисто` (UI), `Зникли.` / `Втрачена.` / `Поки без цілей.` (AR), `По попередній балістиці мінус` (NR), `📢 Відбій загрози` (PS). Then, often, **another wave 2–5 min later** (19 Aug: 6 waves in 20 min; 22 Aug: 2 waves).

## What the prototype did (and what to fix)
- **Latency**: URGENT at the *first* launch message every time (UI 20:52:25; AR `ЦІЛЬ` → WATCH at 21:58:35 → URGENT +1 s when UI named Kyiv → PROMOTE +5 s when AR said `Київ!!`). Burst assembly (same channel ≤45 s) is what makes `ЦІЛЬ`+`КИЇВ` work.
- **Sounds**: 19 Aug → 8 sounds in 24 min with a 2-min resound gap; 21 Aug → 6; 22 Aug → 9 (some spurious, below). Everything else was replace-in-place body updates (79 trajectory updates on 19 Aug — right for the body, never for sound).
- **Fix 1 — non-Kyiv targets leaked in**: `Ціль над Курщиною!`, `Ціль на Ромни!`, `ЛУБНИ ЦІЛЬ!`, `Балістика Миргород` counted as Kyiv launches because the event was active. Rule: a launch naming a non-Kyiv place opens a separate, log-only event.
- **Fix 2 — count inflation**: summing every channel's launch message gave "#48" for 6 missiles. Rule: count = max over channels of that channel's own ordinal/number (`Четверта`, `8 та 9`, `5 балістик`, `застосовано 6 ракет`), display `≥N`.
- **Fix 3 — past tense**: `Очікуємо поки. Цілі були або Іскандери…` re-sounded. Rule: resound only on strong launch forms (`ЦІЛЬ`, `спуск`, `вихід`, `балістика на`, `🚀 Ще`), not on any `ціл*`.
- **Fix 4 — threat INFO dedup**: one INFO per threat window, not one per channel (4 pushes on 22 Aug).
- **Fix 5 — Zircon/cruise**: on 19 Aug Zircons (`Циркон`, `КР`) hit Kyiv in the same 20 minutes with identical phrasing (`5 Цирконів на Київ`, `Київ увага, 4 Циркони на місто`, `БРОВАРИ ПІДЛІТ КР!` on 20 Aug). "Cruise deferred" is not viable: treat `missile` (Циркон/Онікс/КР/Бандероль/Х-101) toward Kyiv as WATCH on `у напрямку Києва` and URGENT on `на Київ` / `підліт` / `над містом` / `захід`.
- **Fuzzy places**: stems caught `ГОЛОС`, `Троя`, `ЦІЛЬʼ`; missed `Вищневе`, `уіль`, `Відрадниц`. Stems + a per-channel alias list handle most; LLM enrichment is for the rest and never on the launch path.

## Drone raid 30 Aug 09:40–10:20 (placeholder HOME=Оболонь, NEARBY=Троєщина/Поділ/Нивки/Вишгород/Хотянівка)
- URGENT fired 09:50:39 (`AR: Ні на Оболонь.` — typo for Нивки→Оболонь, and correct), 09:56:31 (`Цей вже Оболонь`), 10:01:16 (`WM: знову Оболонь`), 10:12:13 (`Від Оболоні Хотянівка`) → 3 sounds in 22 min under a 5-min cooldown. One circling drone = repeated URGENT; acceptable, or raise the drone cooldown to 10 min.
- WATCH: Троєщина 09:42, Поділ 09:44, Нивки 09:50, Вишгород 09:57 — the "it's coming your way" signal worked.
- INFO: 35 silent updates in 40 min — must be replace-in-place, never stacked.
- Reply-chain / burst context resolved type for bare posts (`Лук'янівка - Шулявка.`, `Троя.`) because the channel had said `реактив` ≤45 s earlier; a longer per-channel "current type" memory (~3 min) is needed for slower posters (WM `1х Лук'янівка`).

## Rules to carry into the design
- Per-channel **burst context** (≤45 s) + per-channel **current-type memory** (≤3 min) + reply-chain inheritance.
- Ballistic/missile path: Telethon push → regex → ntfy, no LLM, no corroboration wait; `ЦІЛЬ`-without-target = WATCH, promoted to URGENT by the next place message from any channel.
- Kyiv-gating on target for all missile tiers; non-Kyiv launches are separate log-only events.
- Sound policy: NEW, PROMOTE, and RESOUND at most every 2 min per event while new launches keep coming; body updates otherwise.
- Count from best single source, not sum across sources.

## Replay for HOME = {Нивки, Антонов} (NEARBY = Святошин, Борщагівка, Шулявка, Сирець, Берковець, Виноградар, Біличі, Академмістечко, Коцюбинське, Гостомель, Відрадний, Рембаза, Пуща-Водиця)
`sim.py` after fixes (Kyiv-gating, ≤140-char launch/drone messages, strong launch forms, `ЦІЛЬ`-pending expires after 90 s). Sounds per day, 18–30 Aug:

| day | URGENT drone@home | URGENT ballistic | WATCH drone | WATCH ballistic | INFO drone | INFO ballistic |
|---|---|---|---|---|---|---|
| 18 | 0 | 1 | 0 | 1 | 4 | 6 |
| 19 | 1 | 7 | 0 | 2 | 5 | 0 |
| 20 | 0 | 0 | 4 | 0 | 24 | 7 |
| 21 | 2 | 0* | 0 | 2 | 2 | 4 |
| 22 | 1 | 2 | 0 | 1 | 7 | 4 |
| 23 | 0 | 0 | 0 | 0 | 1 | 5 |
| 24 | 1 | 0 | 1 | 0 | 4 | 8 |
| 25 | 0 | 2† | 0 | 1 | 5 | 10 |
| 26 | 0 | 2† | 0 | 4 | 10 | 4 |
| 27 | 4 | 3 | 10 | 4 | 41 | 0 |
| 28 | 9 | 1 | 14 | 1 | 41 | 13 |
| 29 | 5 | 1 | 15 | 1 | 31 | 0 |
| 30 | 3 | 0 | 6 | 0 | 21 | 3 |
| **Σ** | **26** | **19** | **50** | **17** | **196** | **64** |

\* 21 Aug: the 21:58 URGENT counts as PROMOTE (from AR `ЦІЛЬ` WATCH), tallied under 08-21 sounds. † 25–26 Aug: RESOUNDs off `🚀Ціль`/`ЦІЛЬ` with no PS/WM Kyiv launch that day — should stay WATCH; fix = resound only after a confirmed (non-pending) event.

Real Kyiv ballistic events in the corpus: **19 Aug 20:52, 21 Aug 21:58, 22 Aug 08:39, 27 Aug 00:01** — all four produced URGENT at the first launch message (0–5 s after the first channel post; kpszsu was 15 s … 25 min later). Zero missed.

Drone URGENT at Нивки/Антонов: 26 sounds in 13 days, 21 of them in the last four days (27–30 Aug) — Нивки sits on the jet-drone loop `Оболонь → Нивки → Вишневе/Борщагівка`. Worst night 28 Aug: 9 alarms between 00:35 and 07:55 (`Сирець Нивки` 00:35, `Оболонь → Нивки` 02:17/02:45/02:54, `Оболонь - Нивки` 05:09, `Нивки → Вишневе` 05:41, `Коцюбинське, Нивки, Біличі` 07:08, `Антонов.` 07:55, `Нивки реактив!` 15:28). Each is a real report of a drone over/at the home set; a 5-min cooldown collapses same-drone chatter but not a 7-hour raid. Lever if too much: per-event cooldown 10–15 min, or "URGENT once, then silent updates until a 20-min gap".

WATCH (NEARBY ring) fires 10–15×/day on raid days — correct as a DND-respecting heads-up, but it is the tier to prune first if it fatigues.

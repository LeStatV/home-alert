# Channel evaluation — `@kyiv_nebo` («Київське небо 🌌»)

Evaluated 2026-08-30 against the 18–30 Aug corpus. Corpus fetched with
`page.py kyiv_nebo 2026-08-18T18:00` → `samples-2026-08-30/kyiv_nebo.jsonl`
(45 pages, **898 messages**, 2026-08-18 15:30 → 2026-08-30 13:50 UTC).
Public `t.me/s/` preview works — **no Telethon session needed to evaluate**.

Replay tooling (copies, originals untouched): `sim_kn.py`, `timeline_kn.py`.

---

## 1. Verdict

**INCLUDE — supplementary channel, trust weight `0.6`.**

`@kyiv_nebo` is the cleanest source in the corpus and the best at *microdistrict*
granularity for HOME={Нивки, Антонов}, but it is a **part-time** channel: it goes
dark 03:00–07:00 UTC every day and covered only **60 %** of active raid windows
against 89–90 % for the other four. It can never be an anchor; it is a high-precision
supplement that earns its place by naming Нивки/Борщагівки/Виноградар when nobody
else does.

### Why exactly 0.6

| threshold (ARCHITECTURE §9) | effect at that weight | evidence |
|---|---|---|
| `w ≥ 0.6` → ballistic launch on Kyiv fires URGENT solo | **Yes, grant it.** In 13 days it posted **zero** uncorroborated Kyiv ballistic launches, **zero** missed Kyiv ballistic events (4/4), and on 27 Aug it was the **first channel of six to name Kyiv as the target, by 25 s**. It also correctly *withheld* Kyiv on the 26 Aug Dnipro/Poltava and 29 Aug Odesa ballistic waves — the exact discrimination `sim.py` needed a `NONKYIV` hack for. | §3 |
| `w ≥ 0.8` → drone in HOME fires URGENT solo | **No, withhold.** 60 % raid coverage and a daily 4-hour blackout mean it cannot carry sole responsibility for a HOME drone alarm; and its bare-place style makes type inference (drone vs cruise) unreliable — on 23 Aug its `На Нивки` was a *Бандероль*, not a drone. | §4, §6 |

Net: 0.6 buys the ballistic lead without granting solo drone-URGENT authority.

**Independence caveat for the noisy-OR score (ARCHITECTURE §9).** The channel
self-describes as an aggregator (*«з відкритих джерел»*), and several of its ballistic
launch posts land 4–15 s after UI/AR — i.e. they may be echoes, not independent
observations. Confidence `1−Π(1−wᵢ)` assumes independence, so KN *confirming* UI or AR
slightly overstates confidence. Its own data rebuts a pure-mirror reading (first to name
Kyiv on 27 Aug, first threat on 19 Aug, first on 12 of 20 HOME mentions, 38 unique ring
reports), which is why 0.6 stands — but if corroboration counting is ever tightened,
KN-after-UI/AR within 15 s should count as a partial, not a full, second source.
**Conservative alternative: 0.5** if the operator wants zero added false-URGENT risk —
it costs the 25 s lead on 27 Aug and nothing else, because every other KN ballistic
launch was matched by ≥3 channels within 10 s.

**The weight is not the bottleneck — the profile is.** With the current rules engine
`@kyiv_nebo` contributes almost nothing (+1 URGENT, +1 WATCH over 13 days) because
**88 % of its messages contain no threat-type word at all**. With a per-channel
`default_type: drone` it contributes **+14 URGENT / +15 WATCH** (§5). Adding this
channel without that profile setting is close to pointless.

---

## 2. Style profile

353K subscribers. Description: *«Канал створено для інформування киян про загрози під
час війни. Вся інформація на каналі з відкритих джерел та не є офіційною.»*
(self-declared aggregator, explicitly unofficial).

### 2.1 RESEARCH.md §1 table row

| channel | preview (`t.me/s`) | style | threads same target via reply? |
|---|---|---|---|
| @kyiv_nebo (353K, aggregator) | yes | Ultra-terse bare microdistrict names, no emoji, no prefixes: `Нивки`, `Борщагівки, Вишневе`, `На Жуляни`. Kyiv-city-and-oblast scope only. Type word appears in only 7 % of posts. Ballistic: `Загроза балістики з Брянська` → `Ціль на Київ` → `До 4 ракет`. Clear: `Більше не летить`, `Очікуємо на відбої`, `Чисто`. | **no** — 0 % replies, flat feed, no bumps |

### 2.2 Quantitative comparison

| metric | **KN** | AR | UI | PS | NR | WM |
|---|---|---|---|---|---|---|
| messages 18–30 Aug | **898** | 2299 | 2254 | 2099 | 1294 | 654 |
| per day | **74.8** | 191.6 | 187.8 | 174.9 | 107.8 | 54.5 |
| night share (19:00–03:00 UTC) | **26 %** | 45 % | 44 % | 32 % | 32 % | 55 % |
| median msg length (chars) | **16** | 30 | 34 | 53 | 21 | 44 |
| p90 / max length | **36 / 210** | 69 / 2232 | 127 / 1201 | 102 / 1431 | 69 / 979 | 117 / 2303 |
| `reply_to` non-null | **0 %** | 34 % | 33 % | 5 % | 50 % | 14 % |
| media-only posts | **0 %** | 0 % | 0 % | 0 % | 0 % | 0 % |
| **active-raid bin coverage** | **60 %** | 90 % | 90 % | 90 % | 89 % | 70 % |
| HOME+NEARBY ring mentions | **86** | 214 | 126 | 89 | 126 | 41 |

### 2.3 Noise: effectively zero

Across all 898 messages: **0 @mentions, 0 URLs, 0 `t.me` links, 0 donation/fundraiser
posts, 0 cross-promotions, 0 media-only posts, 1 emoji total** (a 💔 in a condolence
post). `sim.py`'s `NOISE` regex matches **0** messages. Max message length 210 chars —
there are no essays. Compare: NR runs ads for `@Kyiv` / `@kiev_radar_truvoga` and
fundraisers mid-raid; UI appends `✅Розвідка України | Чатик | Підтримати` to launch
messages; AR posts 2 232-char `🎩Зведення` briefings.

The only non-threat content is a handful of one-line asides
(`Кіт Келлог у Києві, нарешті нормальне ППО`, `Немає слів… вічна пам'ять загиблим 💔`)
and short analytic remarks (`Схоже, що запаси реактивних Шахедів у них трохи зменшилися…`).

### 2.4 Vocabulary — the defining problem

| feature | share of 898 msgs |
|---|---|
| contains **any** threat-type word | **7 %** (71) |
| contains **no** type word (bare place / bare count / bare status) | **88 %** (793) |
| resolvable to a place by `sim.py` `PLACES` stems | 53 % |
| drone words (`реактив/БпЛА/шахед/мопед`) | 5 % (47) |
| ballistic words (`баліст/☄/іскандер`) | 3 % (26) |
| missile words (`Циркон/КР/Бандероль/Калібр/ракет`) | 3 % (29) |
| clear words (`відбій/чисто/не летить/не фіксується`) | 14 % (131) |
| threat words (`загроза`) | 2 % (20) |
| KAB (`КАБ`) | **0 %** |

The channel writes `Нивки`, not `🅿️ 1х реактив Нивки`. Type is carried by the
*preceding* message in its own stream, often 2–5 minutes back — well beyond the
45 s burst window and at the edge of the 3-min current-type memory.

### 2.5 Representative messages (verbatim, UTC)

```
2026-08-18T16:31:36  Більше не летить
2026-08-18T17:02:34  2 на Рембазу
2026-08-18T19:04:00  ТУшки неактивні, у наш бік наразі нічого не летить\n\nЗагроза по балістиці актуальна
2026-08-19T20:52:17  Загроза балістики з Брянська
2026-08-19T20:52:29  Цілі на Київ
2026-08-19T20:53:15  До 4 ракет
2026-08-19T20:56:40  4 Циркони
2026-08-19T23:54:15  Реактивний Шахед підлітає до Броварів
2026-08-20T14:20:47  Солома
2026-08-21T21:58:41  Ціль на Київ
2026-08-21T22:00:19  8 цілей
2026-08-21T22:04:45  2-3 Бандеролі в бік Києва
2026-08-22T08:40:44  Бориспіль, Лівий берег
2026-08-23T18:02:00  Правий берег - уважно
2026-08-25T20:55:30  Київ, зреагуйте
2026-08-26T23:25:51  10+ реактивних Шахедів з Чернігівщини/Полтавщини у наш бік
2026-08-26T23:29:10  Цілі на Дніпропетровщину/Полтавщину
2026-08-27T00:00:39  Цілі на Київ з Брянська
2026-08-27T15:43:13  Маневрує в районі ТЕЦ-5
2026-08-28T17:40:52  Нивки, Святошин
2026-08-29T07:30:03  Оболонь, Нивки
2026-08-29T21:19:15  Розвернувся на Нивки
2026-08-30T08:19:09  Знижується, скоро впаде
2026-08-30T13:36:14  Нивки
```

---

## 3. Ballistic timing

`first-of-five` = earliest launch message from kpszsu / war_monitor / nebo_raketa /
AerisRimor / Ukrainian_Intelligence. Negative KN delta = KN was earlier.

| event (UTC) | KN THREAT | first-of-five THREAT | KN LAUNCH | first-of-five LAUNCH | **Δ launch** | KN TRAJECTORY |
|---|---|---|---|---|---|---|
| **19 Aug 20:52** | `20:52:17 Загроза балістики з Брянська` — **first of all six**, 21 s before WM, 115 s before PS | WM 20:52:38 | `20:52:29 Цілі на Київ` | UI 20:52:25 `Балістика на Київ!` | **+4 s** | `20:53:15 До 4 ракет`, `20:59:55 Вишневе`, `21:10:27 Лівий берег` |
| **21 Aug 21:58** | `21:58:29 + Загроза балістики з Курська та Брянська` | UI 21:56:24 (+125 s) | `21:58:41 Ціль на Київ` | AR 21:58:35 `ЦІЛЬ` (no target); UI 21:58:36 | **+6 s** / +5 s | `21:59:15 До 4 цілей`, `21:59:37 До 6`, `22:00:19 8 цілей`, `22:10:54 Лівий берег`, `22:15:21 Бровари` |
| **22 Aug 08:39** | `08:37:52 Загроза балістики з Брянська` | NR/AR 08:37:48 (+4 s) | `08:40:04 Ціль на Київ` | AR 08:39:49 `ЦІЛЬ`; UI 08:39:50 `КИЇВ ЦІЛЬ` | **+15 s** (tied with kpszsu 08:40:04) | `08:40:13 2`, `08:40:44 Бориспіль, Лівий берег`, `08:40:56 На Трипілля`, `08:41:56 Бориспіль` |
| **27 Aug 00:01** | none (went straight to launch) | UI 23:53:23 (Crimea, not Kyiv) | `00:00:39 Цілі на Київ з Брянська` | UI 00:01:04 `Балістика на Київ!` | **−25 s — KN FIRST** | `00:02:21 Ще ціль`, `00:03:20 4 цілі`, `00:03:47 Вишневе` |

Notes:
- UI 00:00:18 / 00:00:36 on 27 Aug said `‼️ Вихід балістики з Брянська` — a launch with
  **no target**. KN's 00:00:39 was the **first message from any of the six naming Kyiv as
  the target**, 25 s before UI and 55 s before AR (`00:01:34 Київ увага!`), 105 s before
  kpszsu. Against a 2–3 min warning budget that is a material lead.
- KN never posts trajectory spam. Where AR emits 20–40 bare place names per wave, KN
  emits 3–6, plus a running **count** (`До 4 ракет` → `До 4 цілей` → `До 6` → `8 цілей`),
  which is exactly the single-source count BEHAVIOR "Fix 2" asks for.

### 3.1 False positives — none

Every KN message containing `ціл*` or `баліст*` was cross-checked for corroboration
(any other channel with a launch form within ±3 min):

- **0 uncorroborated Kyiv ballistic launches** in 13 days.
- All uncorroborated KN ballistic messages are **THREAT-tier only** (`Загроза балістики
  з Курська` ×5, `з Брянська` ×2, `з Воронежа`, `з Таганрогу`) or nightly-status essays
  (`ТУшки неактивні…` ×5) → INFO, no sound.
- **Correct non-Kyiv discrimination**, twice: 26 Aug 23:29:10 `Цілі на
  Дніпропетровщину/Полтавщину` while WM ran `Павлоград — спуск балістики!` /
  `Кременчук` / `Кривий Ріг`; 29 Aug 02:39 Odesa wave — KN stayed silent. It never
  claimed Kyiv for a non-Kyiv launch.

**One borderline case, 25 Aug 20:55:30 `Київ, зреагуйте`** — during a Kursk launch that
resolved to Poltava 80 s later (KN itself corrected: `20:56:50 На Полтавщину пішли`).
AerisRimor said the same thing 12 s later (`20:55:42 Прилуки по Київ - БЦ увага!`), so
this is a shared misread, not a KN defect; it is also not launch phrasing — it fired in
the replay only by promoting an already-pending `ЦІЛЬ` event. BEHAVIOR.md already flags
25 Aug URGENTs († spurious) for the baseline engine.

### 3.2 Misses — none

Scanning every cluster where the five posted a strong Kyiv-ballistic launch form,
KN was present in all Kyiv clusters. The two clusters with no KN message
(26 Aug 23:28 Pavlohrad, 29 Aug 02:39 Odesa) were **not Kyiv events** — correct silence.

### 3.3 19 Aug Zircon wave (20:55–21:04)

| time | KN | vs others |
|---|---|---|
| 20:55:42 | `І Циркони з Курська летять` | UI 20:55:29 `Циркон` (+13 s), WM 20:55:57 |
| 20:56:40 | `4 Циркони` | AR 20:56:38 `Другий циркон`; UI 20:56:29 `Ще 1 циркон` |
| 20:57:49 | `І ще Циркони з Ростова` | **unique — no other channel reported the Rostov batch** |
| 20:59:07 | `Підлітають` | WM 20:59:16 `Київ увага, 4 Циркони на місто` (+9 s) |
| 21:00:46 | `Ще балістика на Київ` | corroborated AR/PS/UI/WM |
| 21:01:23 | `Просто не висовуйтеся, багато всього з різних напрямків летить, і все в бік Києва` | plain-language summary, no equivalent elsewhere |
| 21:02:22 | `Північнокорейськими ракетами також б'ють` | KN-only attribution (KN-23) |

KN tracked the Zircon wave correctly and in time, but with **`Підлітають` (bare, no
place)** rather than WM's `4 Циркони на місто`. Under ARCHITECTURE §5 (missile URGENT
on `підліт`), `Підлітають` must be recognised — see `type_vocab` below.

---

## 4. Drone coverage — HOME {Нивки, Антонов} + NEARBY ring

KN ring mentions 18–30 Aug: **86** (4th of six — behind AR 214, NR 126 and UI 89, ahead of
WM 41 and PS 5). Volume is not the point: see §4.2 for how much of it is *first* or *unique*.

Per place: Борщагівка 28 · **Нивки 20** · Виноградар 16 · Святошин 8 · Гостомель 6 ·
Коцюбинське 6 · Шулявка 6 · Сирець 3 · Рембаза 1 · **Антонов 0**.

> KN never writes «Антонов». It covers that airspace as `Коцюбинське` / `Борщагівки`.
> AerisRimor is the only channel that names it, and misspells it (`Підвернув на анонов!`,
> 30 Aug 09:46:05) — an alias `анонов` is required in the *global* stem list, not just here.

### 4.1 Every KN message naming HOME (Нивки / Антонов)

`Δ` = KN time minus the earliest other-channel HOME mention within ±4 min. Negative = KN first.

| # | UTC | KN text | other channels | first | Δ |
|---|---|---|---|---|---|
| 1 | 08-19 22:35:30 | `Нивки` | AR | **KN** | −16 s |
| 2 | 08-23 18:01:56 | `На Нивки` | AR, NR, UI | UI | +11 s |
| 3 | 08-24 21:32:09 | `Нивки` | AR, NR | AR | +97 s |
| 4 | 08-27 09:04:02 | `Далі на Нивки` | AR, WM | WM | +22 s |
| 5 | 08-28 13:52:21 | `Нивки` | NR, UI, WM | UI | +7 s |
| 6 | 08-28 14:35:11 | `Нивки` | **none** | **KN** | unique |
| 7 | 08-28 15:29:05 | `Нивки, Борщагівки` | AR | AR | +21 s |
| 8 | 08-28 17:40:52 | `Нивки, Святошин` | **none** | **KN** | unique |
| 9 | 08-28 19:50:37 | `Нивки` | AR | AR | +18 s |
| 10 | 08-29 07:30:03 | `Оболонь, Нивки` | **none** | **KN** | unique |
| 11 | 08-29 08:33:52 | `На Нивки, Святошин` | **none** | **KN** | unique |
| 12 | 08-29 09:57:05 | `Нивки, Святошин` | AR | **KN** | −10 s |
| 13 | 08-29 14:32:59 | `На Нивки` | **none** | **KN** | unique |
| 14 | 08-29 19:13:34 | `Наступний на Борщагівки, Нивки` | UI | UI | +11 s |
| 15 | 08-29 19:30:55 | `Нивки` | **none** | **KN** | unique |
| 16 | 08-29 21:19:15 | `Розвернувся на Нивки` | UI | **KN** | −79 s |
| 17 | 08-30 08:16:31 | `Нивки` | AR, UI | **KN** | −13 s |
| 18 | 08-30 09:46:01 | `Нивки, Святошин` | **none** | **KN** | unique |
| 19 | 08-30 12:05:34 | `Нивки` | AR, NR, WM | AR | +27 s |
| 20 | 08-30 13:36:14 | `Нивки` | **none** † | **KN** | unique |

† #20 is past the other five corpora's cutoff (13:02) — discount it.

**20 HOME mentions, KN first in 12, 8 of them with no HOME mention from any other
channel within ±4 min.** All 8 were verified against the surrounding timeline and are
**real passes**, not fabrication — the other channels were tracking the same drone
through adjacent districts at that moment. Example, 30 Aug 09:46:

```
09:45:05 AR | Лук'янівка - Шулявка.
09:45:57 AR | Відрадний - Галагани.
09:46:01 KN | Нивки, Святошин        <-- only channel naming HOME
09:46:05 AR | Підвернув на анонов!    <-- = Антонов, misspelled
09:46:14 AR | Тепер на Борщагівки.
```

### 4.2 Every KN message naming HOME or the NEARBY ring (all 86, 18–30 Aug)

`Δ` = KN time minus the earliest other-channel mention of the *same place* within ±3 min.
`unique` = no other channel named that place in that window.

| UTC | KN text | ring place(s) | other ch. | first | Δ |
|---|---|---|---|---|---|
| 08-18 17:02:34 | `2 на Рембазу` | Рембаза | none | **KN** | **unique** |
| 08-19 12:42:32 | `Одна ракета в бік Гостомеля` | Гостомель | AR | **KN** | **KN −72 s** |
| 08-19 22:35:30 | `Нивки` | Нивки | AR | **KN** | **KN −16 s** |
| 08-23 18:01:56 | `На Нивки` | Нивки | AR,NR,UI | UI | +11 s |
| 08-24 21:29:53 | `Гостомель` | Гостомель | NR | **KN** | **KN −91 s** |
| 08-24 21:32:02 | `Виноградар` | Виноградар | AR,NR,UI | AR | +97 s |
| 08-24 21:32:09 | `Нивки` | Нивки | AR,NR | AR | +20 s |
| 08-27 09:02:49 | `Гостомель, Ірпінь, Буча` | Гостомель | none | **KN** | **unique** |
| 08-27 09:03:32 | `Коцюбинське` | Коцюбинське | AR | **KN** | **KN −133 s** |
| 08-27 09:04:02 | `Далі на Нивки` | Нивки | WM | WM | +22 s |
| 08-27 09:04:42 | `На Борщагівки` | Борщагівка | AR | AR | +9 s |
| 08-27 09:26:04 | `1 Бровари, 1 біля Борщагівок` | Борщагівка | none | **KN** | **unique** |
| 08-27 15:50:09 | `Шулявка` | Шулявка | AR | **KN** | **KN −56 s** |
| 08-27 15:51:58 | `Коцюбинське` | Коцюбинське | AR,NR | **KN** | **KN −3 s** |
| 08-27 16:26:22 | `Шулявка` | Шулявка | none | **KN** | **unique** |
| 08-27 16:56:44 | `Шулявка` | Шулявка | NR | **KN** | **KN −33 s** |
| 08-27 16:57:37 | `На Борщагівки` | Борщагівка | none | **KN** | **unique** |
| 08-27 17:43:16 | `Борщагівки` | Борщагівка | AR | **KN** | **KN −43 s** |
| 08-27 17:43:19 | `Святошин` | Святошин | AR | **KN** | **KN −48 s** |
| 08-27 17:44:49 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-27 17:49:21 | `Сирець` | Сирець | AR | AR | +59 s |
| 08-27 18:31:24 | `Борщагівки` | Борщагівка | AR | AR | +9 s |
| 08-27 18:42:06 | `Виноградар` | Виноградар | AR | AR | +8 s |
| 08-27 18:44:20 | `На Борщагівки` | Борщагівка | none | **KN** | **unique** |
| 08-27 21:04:29 | `Борщагівки` | Борщагівка | AR,UI | AR | +2 s |
| 08-28 07:51:52 | `2 реактивних у бік Гостомеля` | Гостомель | PS | PS | +28 s |
| 08-28 07:55:16 | `Борщагівки, Вишневе` | Борщагівка | AR | **KN** | **KN −123 s** |
| 08-28 13:51:40 | `Борщагівки` | Борщагівка | AR,WM | AR | +19 s |
| 08-28 13:52:21 | `Нивки` | Нивки | NR,UI,WM | UI | +7 s |
| 08-28 13:57:26 | `Борщагівки` | Борщагівка | UI | UI | +5 s |
| 08-28 14:35:11 | `Нивки` | Нивки | none | **KN** | **unique** |
| 08-28 14:42:08 | `На Шулявку новий` | Шулявка | none | **KN** | **unique** |
| 08-28 14:50:50 | `Борщагівки` | Борщагівка | none | **KN** | **unique** |
| 08-28 15:27:27 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-28 15:29:05 | `Нивки, Борщагівки` | Борщагівка/Нивки | AR,UI | AR | +21 s |
| 08-28 15:37:02 | `Борщагівки` | Борщагівка | AR,NR | AR | +37 s |
| 08-28 17:13:01 | `Борщагівки` | Борщагівка | none | **KN** | **unique** |
| 08-28 17:14:18 | `Коцюбинське` | Коцюбинське | UI | **KN** | **KN −8 s** |
| 08-28 17:14:30 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-28 17:15:40 | `На Гостомель` | Гостомель | NR | NR | +3 s |
| 08-28 17:40:52 | `Нивки, Святошин` | Нивки/Святошин | none | **KN** | **unique** |
| 08-28 19:32:55 | `На Шулявку` | Шулявка | AR | **KN** | **KN −19 s** |
| 08-28 19:49:28 | `Новий на Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-28 19:50:37 | `Нивки` | Нивки | none | **KN** | **unique** |
| 08-28 19:51:25 | `Борщагівки, Вишневе` | Борщагівка | AR | AR | +21 s |
| 08-28 20:12:55 | `Виноградар` | Виноградар | AR | AR | +7 s |
| 08-28 21:54:11 | `Реактивний на Виноградар` | Виноградар | NR,UI,WM | NR | +36 s |
| 08-28 21:56:13 | `Святошин` | Святошин | WM | **KN** | **KN −25 s** |
| 08-28 21:56:24 | `Борщагівки, Вишневе` | Борщагівка | NR,WM | **KN** | **KN −10 s** |
| 08-29 07:30:03 | `Оболонь, Нивки` | Нивки | none | **KN** | **unique** |
| 08-29 07:30:55 | `Святошин, Борщагівки` | Борщагівка/Святошин | none | **KN** | **unique** |
| 08-29 07:37:13 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-29 07:38:35 | `Сирець, Солома` | Сирець | none | **KN** | **unique** |
| 08-29 08:14:25 | `Вилетів у бік Гостомеля` | Гостомель | UI | **KN** | **KN −64 s** |
| 08-29 08:33:52 | `На Нивки, Святошин` | Нивки/Святошин | none | **KN** | **unique** |
| 08-29 09:57:05 | `Нивки, Святошин` | Нивки/Святошин | AR | **KN** | **KN −10 s** |
| 08-29 09:57:58 | `Борщагівки, Вишневе` | Борщагівка | none | **KN** | **unique** |
| 08-29 14:32:59 | `На Нивки` | Нивки | none | **KN** | **unique** |
| 08-29 15:31:52 | `Коцюбинське, на північ` | Коцюбинське | none | **KN** | **unique** |
| 08-29 18:48:09 | `Солома, Шулявка` | Шулявка | none | **KN** | **unique** |
| 08-29 18:48:48 | `Борщагівки, Вишневе` | Борщагівка | UI | **KN** | **KN −58 s** |
| 08-29 19:09:04 | `Борщагівки` | Борщагівка | none | **KN** | **unique** |
| 08-29 19:13:34 | `Наступний на Борщагівки, Нивки` | Борщагівка/Нивки | UI | UI | +11 s |
| 08-29 19:30:53 | `Коцюбинське` | Коцюбинське | none | **KN** | **unique** |
| 08-29 19:30:55 | `Нивки` | Нивки | none | **KN** | **unique** |
| 08-29 19:31:31 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-29 19:36:46 | `Сирець, Лукʼянівка` | Сирець | NR | **KN** | **KN −5 s** |
| 08-29 21:19:15 | `Розвернувся на Нивки` | Нивки | UI | **KN** | **KN −79 s** |
| 08-30 08:10:56 | `Ірпінь, Буча, Коцюбинське - уважно` | Коцюбинське | none | **KN** | **unique** |
| 08-30 08:14:40 | `Виноградар` | Виноградар | UI | **KN** | **KN −23 s** |
| 08-30 08:16:31 | `Нивки` | Нивки | AR,UI | **KN** | **KN −13 s** |
| 08-30 08:17:02 | `Борщагівки` | Борщагівка | AR,NR,UI | AR | +5 s |
| 08-30 09:46:01 | `Нивки, Святошин` | Нивки/Святошин | none | **KN** | **unique** |
| 08-30 09:46:28 | `Борщагівки` | Борщагівка | AR,NR | AR | +14 s |
| 08-30 09:49:38 | `Виноградар, Мінський масив` | Виноградар | none | **KN** | **unique** |
| 08-30 10:00:46 | `Борщагівки, Вишневе, Васильків` | Борщагівка | AR | AR | +68 s |
| 08-30 10:03:28 | `Виноградар` | Виноградар | none | **KN** | **unique** |
| 08-30 10:08:06 | `Борщагівки, Виноградар` | Борщагівка/Виноградар | none | **KN** | **unique** |
| 08-30 12:04:20 | `Виноградар` | Виноградар | UI | **KN** | **KN −105 s** |
| 08-30 12:05:34 | `Нивки` | Нивки | NR,WM | **KN** | **KN −102 s** |
| 08-30 12:07:17 | `Центр, Печерськ, Святошин` | Святошин | NR | **KN** | **KN −31 s** |
| 08-30 12:08:01 | `Борщагівки` | Борщагівка | AR,WM | AR | +50 s |
| 08-30 12:15:39 | `Борщагівки` | Борщагівка | NR | **KN** | **KN −54 s** |
| 08-30 12:54:02 | `Мінський масив, Виноградар, Оболонь` | Виноградар | none | **KN** | **unique** |
| 08-30 13:36:14 | `Нивки` | Нивки | none | **KN** | **unique** |
| 08-30 13:36:29 | `Борщагівки` | Борщагівка | none | **KN** | **unique** |

**Totals: 86 ring messages — KN first or tied in 47, of which 38 are unique.**
Highest-value places: Борщагівка 28 (8 unique), Нивки 20 (8 unique),
Виноградар 16 (8 unique), Святошин 8, Гостомель 6, Коцюбинське 6, Шулявка 6,
Сирець 3, Рембаза 1, Антонов 0.
The last two rows (08-30 13:36) fall past the other corpora's 13:02 cutoff — discount them.

### 4.3 27–30 Aug nights specifically

The four heaviest HOME nights are where KN both shines and fails:

- **27 Aug**: KN present 08:38–09:42 and from 11:45 onward, but **absent 00:31–08:38**
  (two consecutive gaps of 3 h 43 m and 4 h 24 m) — it slept through 23 active-raid bins.
- **28 Aug**: BEHAVIOR's worst HOME night (9 URGENTs 00:35–07:55). KN was
  **silent 02:10–07:51** — it missed 6 of the 9. It did contribute the afternoon/evening
  passes (13:52, 14:35, 15:29, 17:40, 19:50).
- **29 Aug**: KN's best day — 5 HOME mentions, 4 of them unique (07:30, 08:33, 14:32, 19:30)
  plus first-by-79 s at 21:19. Still silent 21:23 → 30 Aug 07:41.
- **30 Aug**: first at 08:16:31 (−13 s vs AR), unique at 09:46:01.

---

## 5. Replay delta (`sim_kn.py`)

`sim_kn.py` = `sim.py` + `"kyiv_nebo": ("KN", 0.7)` + 15 place stems for KN wording
(`солом`→Солом'янка, `почайн`, `видубич`, `тец-?5/6`, `козин`, `вишеньк`, `макарів`,
`ворзел`, `конча`, `трипілл`, `\bцентр\b`, `лівий берег`, `правий берег`, `анонов`→Антонов).
Two env toggles keep the comparison honest: `KN=0` excludes the channel; `KNTYPE=1`
applies a per-channel `default_type: drone`. (`sim_kn.py` carries `0.7` as the task
specified; `sim.py` only ever tests `w >= 0.6`, so the replay is identical at 0.6 or 0.7.) **All three runs share identical stems**, so
the delta is attributable to `@kyiv_nebo` alone. 30 Aug truncated at 13:02 to match the
other corpora.

Per day, sounds (NEW + RESOUND + PROMOTE) as `URGENT/WATCH/INFO`:

| day | base (5 ch) | +KN, engine as-is | +KN, `default_type: drone` |
|---|---|---|---|
| 18 | 1/1/10 | 1/1/11 | 1/2/11 |
| 19 | 8/2/5 | 8/2/6 | 9/3/7 |
| 20 | 0/4/31 | 0/4/32 | 0/4/32 |
| 21 | 2/2/6 | 2/2/7 | 2/2/7 |
| 22 | 3/1/11 | 3/1/12 | 3/1/12 |
| 23 | 0/0/7 | 0/0/7 | **1**/0/7 |
| 24 | 1/1/13 | 1/1/14 | 1/1/14 |
| 25 | 2/1/15 | **3**/1/15 | 3/1/15 |
| 26 | 2/4/14 | 2/4/15 | 2/4/15 |
| 27 | 7/14/43 | 7/14/43 | 7/**19**/45 |
| 28 | 10/15/54 | 10/15/56 | **14**/16/57 |
| 29 | 6/16/31 | 6/16/31 | **12**/**20**/33 |
| 30 | 3/6/24 | 3/7/24 | **4**/**9**/25 |
| **Σ sounds** | **45 / 67 / 264** = 376 | **46 / 68 / 273** = 387 | **59 / 82 / 280** = 421 |
| total pushes | 1372 | 1433 | 1737 |

### 5.1 What KN adds

- **Engine as-is: +1 URGENT, +1 WATCH, +9 INFO over 13 days — negligible.** 10 of its
  15 sound contributions are `Загроза балістики` INFO dedup fodder. This is the direct
  consequence of the 88 % bare-place style: `sim.py`'s drone branch requires a type word
  in the message or its 45 s burst context, and KN rarely supplies one.
- **With `default_type: drone`: +14 URGENT, +15 WATCH, +16 INFO.** Now it delivers 13
  HOME URGENTs, 8 of which no other channel produced.

### 5.2 Did it move first-URGENT earlier?

| day | base first URGENT | with KN (typed) | change |
|---|---|---|---|
| 23 Aug | *none all day* | **18:01:56 KN `На Нивки`** | new alarm on a day the base engine was silent (corroborated: UI 18:01:45 `Далі на Нивки перша`, AR 18:01:56 `Нивки від Мінського!`) |
| 25 Aug | 20:58:15 AR | **20:55:30 KN `Київ, зреагуйте`** | 2 m 45 s earlier — the borderline Poltava case (§3.1) |
| 30 Aug | 09:46:05 AR `Підвернув на анонов!` | **08:16:31 KN `Нивки`** | **1 h 29 m earlier** — real 08:14–08:19 pass (AR 08:16:44 `Нивки - Шулявка.`, UI 08:16:55 `Нивки`) that the base engine had no typed message for |
| all other days | unchanged | unchanged | KN never delayed or displaced an existing first-URGENT |

On the four ballistic events KN never moved first-URGENT, because AR/UI already fire
0–6 s ahead of it — **except 27 Aug**, where KN is the first Kyiv-targeted launch by 25 s
but the base engine already fired at 00:01:34 off AR's `Київ увага!`; at `w = 0.6` KN's
00:00:39 `Цілі на Київ з Брянська` fires URGENT immediately, **55 s earlier**.

### 5.3 Parsing failures specific to KN wording

Blocking (must be in the profile):

1. **No type word in 88 % of messages.** Needs `default_type: drone` (or a per-channel
   current-type memory ≥5 min). Without it the channel is inert. Risk: it mislabels
   cruise-missile passes as drones (23 Aug `На Нивки` was a Бандероль) — tier is still
   correct, only the push title is wrong.
2. **`Солома` = Солом'янка** — 7 occurrences, no stem in `sim.py`. Also `Почайна`,
   `Видубичі`, `ТЕЦ-5`, `ТЕЦ-6`.
3. **Coarse Kyiv-halves**: `Лівий берег` (5), `Правий берег` (2+), `Центр` (9 + `На Центр` 6
   + `Знову на Центр` 3). These are place-tier INFO for a Нивки home, but must not be
   dropped as unparsed.
4. **Bare counts as continuation messages**: `2`, `До 4 ракет`, `До 4 цілей`, `До 6`,
   `8 цілей`, `4 Циркони`, `Зараз 4 біля Києва`. These carry the ordinal for BEHAVIOR
   Fix 2 (`count = max over channels`) but have no place and no type — they must attach
   to the open event, never open a new one.
5. **`Підлітає` / `Підлітають` with no place** — ARCHITECTURE §5 treats `підліт` as an
   URGENT trigger for missiles; KN's bare form must inherit the event's target rather
   than fire on its own.
6. **Clear vocabulary not in `sim.py`'s `CLEAR`**: `Більше не летить` (30), `Очікуємо на
   відбої` / `Очікуємо на відбій` (21+), `Не фіксується` / `Більше не фіксується` (8),
   `Поки все`, `Дорозвідка` / `Дорозвідка в області` (8), `Знижується, скоро впаде`,
   `Біля Києва наразі чисто`, `Балістика не до нас`.
7. **`уважно` as a soft-warning suffix**: `Троєщина - уважно`, `Бровари - уважно`,
   `Правий берег - не висовуйтеся`. Advisory, not a sighting — should be one tier below
   a bare place name.
8. Global (not KN-specific, found while checking): AerisRimor writes **`анонов`** for
   Антонов — a HOME place the current `r"антонов"` stem misses.

---

## 6. Silence

- **Daily blackout 03:00–07:00 UTC (06:00–10:00 Kyiv).** Hourly post counts across
  13 days: 03:00 → **0**, 04:00 → 1, 05:00 → 2, 06:00 → 2, then 07:00 → 39, 08:00 → 74.
  This is a single-operator channel that sleeps in the early morning.
- **Active-raid coverage 60 %** (114 of 187 ten-minute bins in which ≥3 of the other five
  named a Kyiv-area place) — vs AR/UI/PS 90 %, NR 89 %, WM 70 %.
- **37 silences longer than 25 min that span an active raid.** Worst:

  | gap | window (UTC) | active bins missed |
  |---|---|---|
  | 7 h 18 m | 28 Aug 21:58 → 29 Aug 05:16 | 20 |
  | 5 h 42 m | 28 Aug 02:10 → 07:51 | 9 (incl. BEHAVIOR's worst HOME night) |
  | 4 h 24 m | 27 Aug 04:14 → 08:38 | 11 |
  | 4 h 18 m | 20 Aug 02:51 → 07:08 | 7 |
  | 3 h 43 m | 27 Aug 00:31 → 04:14 | 12 |
  | 3 h 45 m | 26 Aug 19:00 → 22:45 | 2 |
  | 8 h 40 m | 21 Aug 23:57 → 22 Aug 08:37 | 3 |

- It does **not** stop posting at night in the ordinary sense — 00:00–02:00 UTC
  (03:00–05:00 Kyiv) is active (20/8/15 posts) and it woke for all four ballistic events
  including 27 Aug 00:00. The hole is the pre-dawn/early-morning band.
- **Implication for ARCHITECTURE §11**: KN will frequently be the stale channel in the
  `N/6 каналів активні` line. Do not let a silent KN suppress or delay anything, and do
  not count it toward the "all channels silent while siren on" warning during 03:00–07:00 UTC.

---

## 7. Draft `profiles/kyiv_nebo.yaml`

```yaml
channel: kyiv_nebo
title: "Київське небо 🌌"
weight: 0.6                 # ballistic launch on Kyiv may fire URGENT solo (>=0.6);
                            # drone at HOME stays WATCH until a 2nd source (<0.8)
subscribers: 353000
threads_by_reply: false     # 0/898 replies — flat feed, no bump pattern
scope: kyiv                 # Kyiv city + oblast only; never reports other oblasts as ours

# --- the critical setting: 88% of messages carry no threat-type word ---
default_type: drone         # bare place names during a raid are jet-drone/Shahed passes
default_type_ttl: 300       # s; a preceding typed message overrides for this long
type_memory_window: 300     # KN's own type words are 2-5 min back, beyond the 45 s burst

type_vocab:
  drone:      ['реактивн\w* шахед', 'реактивн\w*', 'шахед', 'бпла', 'дрон', 'мопед']
  ballistic:  ['баліст\w*', 'ціл[ьіє]', 'кн-23', 'північнокорейськ\w* ракет']
  missile:    ['циркон', 'бандерол', 'калібр', 'онікс', 'кр\b', 'ракет[аиі]']
  aviation:   ['тушк', 'ту-95', 'ту-160', 'злет']
  recon:      ['дорозвідк', 'розвід']

stage_vocab:
  threat:
    - 'загроза балістики з (брянськ\w*|курськ\w*|воронеж\w*|таганрог\w*|крим\w*)'
    - 'загроза по балістиці актуальна'
    - 'вночі буде масована ракетна атака'
  launch:                   # Kyiv target present -> URGENT at weight 0.6
    - '^ціл[ьі] на київ'
    - '^цілі на київ з \w+'
    - '^ще баліст\w*( на київ)?'
    - '^київ,? зреагуйте'
    - 'тримають курс в бік києва'
  launch_pending:           # launch/continuation, target inherited from open event
    - '^ще ціл[ьі]$'
    - '^ще одна ціль$'
    - '^є цілі$'
    - '^підліта[єю]т?ь?$'
    - '^\d+$'               # bare count: "2"
    - '^(до )?\d+ (ракет|цілей|циркон\w*|балістик)'
    - '^до \d+$'
  trajectory:               # bare place lines; tier from place set
    - '^(на |далі на |знову на |курс |курс на |наступний на |розвернувся на )?<PLACE>'
  clear:
    - 'більше не летить'
    - 'більше не фіксується'
    - 'не фіксується'
    - 'очікуємо на відбо[ії]'
    - '^відбій$'
    - '^чисто( поки)?$'
    - '^поки чисто$'
    - 'біля києва (наразі |поки )?чисто'
    - 'в області наразі чисто'
    - 'по балістиці все спокійно'
    - 'балістика не до нас'
    - '^зникли$'
    - '^поки все$'
    - 'знижується, скоро впаде'
    - '^все, дорозвідка$'
    - 'дорозвідка( в області)?'
    - 'у наш бік наразі нічого не летить'
  advisory:                 # soft warning, one tier below a bare sighting
    - '- ?уважно$'
    - '- ?не висовуйтеся'
    - 'не висовуйтеся'

place_aliases:
  Солом'янка:   ['Солома', 'Солом''янка']
  Почайна:      ['Почайна']
  Видубичі:     ['Видубичі']
  Лівий берег:  ['Лівий берег', 'Весь Лівий берег', 'Лівобережний']
  Правий берег: ['Правий берег']
  Центр:        ['Центр']
  ТЕЦ-5:        ['ТЕЦ-5', 'ТЕЦ5']
  ТЕЦ-6:        ['ТЕЦ-6', 'ТЕЦ6']
  Борщагівка:   ['Борщагівки', 'Борщагівок', 'Борщаги']
  Конча-Заспа:  ['Конча-Заспа', 'Конча']
  Трипілля:     ['Трипілля']
  Козин:        ['Козин']
  Вишеньки:     ['Вишеньки']
  Макарів:      ['Макарів']
  Ворзель:      ['Ворзель']
  # NOTE: KN never writes "Антонов" — it says Коцюбинське/Борщагівки for that airspace.
  # Global alias needed elsewhere: AerisRimor writes "анонов" for Антонов.

noise_patterns:             # near-empty by design: 0 ads, 0 @mentions, 0 links in 898 msgs
  - '^(кіт келлог|немає слів)'          # occasional one-line asides
  - 'вічна пам.ять'
  - 'схоже, що запаси'                  # analytic commentary, not a sighting
  - '^працює вороже ппо$'               # situational note

silence:
  expected_blackout_utc: ['03:00-07:00']  # 06:00-10:00 Kyiv; do not flag as failure
  raid_coverage: 0.60                     # vs 0.89-0.90 for AR/UI/NR/PS
  never_anchor: true                      # must not gate all-clear or silence warnings
```

### 7.1 Labelled `examples` (regression fixtures)

```yaml
examples:
  - {text: "Цілі на Київ",                    type: ballistic, stage: launch,     places: [Київ],                 count: null}   # 2026-08-19T20:52:29
  - {text: "Загроза балістики з Брянська",    type: ballistic, stage: threat,     places: [],                     count: null}   # 2026-08-19T20:52:17
  - {text: "До 4 ракет",                      type: ballistic, stage: launch,     places: [],                     count: 4}      # 2026-08-19T20:53:15  (count only, inherits target)
  - {text: "8 цілей",                         type: ballistic, stage: launch,     places: [],                     count: 8}      # 2026-08-21T22:00:19
  - {text: "Цілі на Дніпропетровщину/Полтавщину", type: ballistic, stage: launch, places: [Дніпропетровщина, Полтавщина], count: null} # 2026-08-26T23:29:10  (NON-KYIV -> log only)
  - {text: "4 Циркони",                       type: missile,   stage: launch,     places: [],                     count: 4}      # 2026-08-19T20:56:40
  - {text: "2-3 Бандеролі в бік Києва",       type: missile,   stage: launch,     places: [Київ],                 count: 3}      # 2026-08-21T22:04:45
  - {text: "Нивки, Святошин",                 type: drone,     stage: trajectory, places: [Нивки, Святошин],      count: null}   # 2026-08-28T17:40:52  (HOME + NEARBY, no type word)
  - {text: "Борщагівки, Вишневе",             type: drone,     stage: trajectory, places: [Борщагівка, Вишневе],  count: null}   # 2026-08-28T07:55:16
  - {text: "Реактивний Шахед підлітає до Броварів", type: drone, stage: trajectory, places: [Бровари],            count: 1}      # 2026-08-19T23:54:15
  - {text: "Більше не летить",                type: null,      stage: clear,      places: [],                     count: null}   # 2026-08-18T16:31:36
  - {text: "Троєщина - уважно",               type: drone,     stage: advisory,   places: [Троєщина],             count: null}   # 2026-08-18T15:30:09
```

---

## 8. Integration checklist

1. Set `weight: 0.6` and **`default_type: drone`** — without the latter the channel is inert (§5.1).
2. Add the 15 place stems from §5.3 to the global stem list; they are not KN-specific
   (`Солома`, `Центр`, `Лівий берег` appear in AR/NR/WM too).
3. Add `анонов` → Антонов to the global aliases — a HOME place currently missed in AR.
4. Extend the global `CLEAR` vocabulary with `більше не летить` / `не фіксується` /
   `очікуємо на відбій` / `дорозвідка`.
5. Exempt KN from the "channel silent while siren on" warning between 03:00–07:00 UTC.
6. Do not let KN alone open a drone URGENT (weight < 0.8 handles this) and do not let
   its bare counts (`2`, `До 6`) open a new event.

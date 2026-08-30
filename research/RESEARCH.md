# home-alert — source research (2026-08-30)

Goal: notify (ntfy) about threats that matter for a home location in Kyiv:
drones on/near the location, ballistics toward Kyiv. Filter out noise.

Samples captured during a live jet-drone (реактивні БпЛА) raid on Kyiv, 08:00–10:15 UTC:
`samples-2026-08-30/*.html` (t.me/s previews), `parse.py` (extract text/time/reply).

## 1. Telegram channels — observed styles

| channel | preview (`t.me/s`) | style | threads same target via reply? |
|---|---|---|---|
| @kpszsu (Air Force, official) | yes | `🏍 Реактивний БпЛА повз X курсом на Y`, `☄️ Загроза балістики`, `⚠ Київ ... Перебувайте в укриттях!` | no — flat |
| @war_monitor | yes | `Київ: 🅿️ 1х реактив Лівобережний масив`, `🔄` = circling, `💥 ... чисто` | **yes** — chain of replies per drone |
| @monitor_ukr (mirror of war_monitor + footer) | yes | same as war_monitor, multiline "Станом на зараз" summaries | partly |
| @monitorwarr | yes | `1х Чабани.` / `Далі Глеваха/Васильків.` — terse, context-dependent | yes |
| @deraketaua | yes | `⚠️4 реактивні шахеди на Київщині: 2 біля Броварів ...` counts+regions | yes, and *edits summary per reply* |
| @eRadarrua | yes | `🛵 Оболонь`, `🛵 1 Вишгород`, one-word district posts, jokes | no |
| @povitryanatrivogaaa | yes | `✈️Київщина:→Васильків/Боярка/Київ (2х)` route lists per oblast; map images | rarely |
| @vanek_nikolaev | yes | Russian, slang (`мопед`), Mykolaiv-centric, Kyiv mentioned in passing | yes |
| @Nikolaevskiy_Vanek, @shahedy_raketaa | **no preview** (restricted) | — | — |
| @kyivoda (Kyiv oblast admin) | yes | `🔴 Бучанський район - повітряна тривога!` — raion alerts only, no type | no |
| @air_alert_ua (official siren feed) | yes | `Повітряна тривога в м. Київ`, `Загроза ударних БпЛА в ...` | no |

Observations:
- Same event, five wordings. Locality names are the common denominator (Оболонь, Бровари, Васильків, Вишгород, Ірпінь, лівий/правий берег).
- Threat-type vocabulary: `реактив/реактивний БпЛА/реактБпЛА/реактивний шахед/мопед` (jet drone), `шахед/БпЛА/мопед` (Shahed), `мгКР/мКР "Бандероль"` (small cruise missile), `балістика/☄️/Загроза балістики`, `КАБ`, `МіГ-31К`, `розвідувальний`.
- "Толкает" style: replies carry no context (`1х далі Білогородка`) — need parent message to know it's a drone.
- kpszsu is slow but authoritative; monitor channels lead by 1–5 min.
- texty.org.ua: 40+ "monitor" channels are reposts/ad funnels; only a handful have original content.

Access options:
- `https://t.me/s/<ch>` — no account, HTML, last 20 msgs, `?before=<id>` pagination, includes `data-post`, `datetime`, reply link. Works for most channels. Poll every ~20–30s.
- MTProto user session (Telethon) — needed for restricted channels (Ванёк), gives push updates, edits, no 20-msg limit. Needs phone-number login + api_id/hash.
- Bot API — useless (bots cannot read channels they don't admin).

## 2. NEPTUN — https://neptun.in.ua/developers  (THE key finding)

Free, keyless, GET-only, CORS *. Attribution link required.
- `GET /api/v1/threats` — snapshot of active tracks. Fields: `id, type (uav|recon|missile|ballistic|kab|mig31k|fpv|unknown), title, region, district, locality, lat, lon, heading, velocity{bearingDeg,speedKmh}, confidenceLevel (low|medium|high), sourceCount, count, status (active|stale|resolved), lifecycle (uncertain|confirmed), positionQuality (approx|confirmed), uncertaintyKm, trail[{lat,lon,t}], destination, presumptiveCourse, advisory, areaOnly, explanationShort`.
- `GET /api/v1/alerts` — official sirens per raion/oblast with `since`.
- `GET /api/v1/messages` — raw feed of ~45 Telegram channels they ingest (last ~10 min, ~120 msgs), `{channel,text,date}`. Includes kpszsu, war_monitor, monitor_ukr, eradarrua, povitryanatrivogaaa, ukrainealarmsignal, radar_top_ua, ...
- `wss://neptun.in.ua/api/v1/stream` — frames `{type: snapshot|upsert|remove|heartbeat|alerts, ts, data}`. Verified 101 upgrade via curl.
- REST: poll ≤ 1/5s (CDN cached). JS SDK has `predict()` dead-reckoning.
- Live check 10:15 UTC: 42 tracks, 11 within 80 km of Kyiv centre, incl. `Печерськ d=2.2km conf=high src=3`, matching what channels reported. No ballistic present to verify that type.
- Caveats: `areaOnly` tracks sit at oblast centroid; `presumptiveCourse` = extrapolated; third-party, free, could vanish/degrade under load exactly during mass attacks.

## 3. Other structured sources
- alerts.in.ua API — official sirens only, `alert_type` ∈ {air_raid, artillery_shelling, urban_fights, chemical, nuclear}; no drone/ballistic distinction. Token, 10 req/min.
- api.ukrainealarm.com — same, token via form.

## 4. Prior art
- ALERTua/air_raid_threat_reporter (archived): Telethon user session → every message to Ollama "is this a threat to <city>?" → forward. No scoring, no geo.
- mourner gist: MTProto scrape of @air_alert_ua, regex for start/end.
- IRONSIGHT: OSINT dashboard, ingests Shahed/missile tracks (source unclear).

## 5. Implications for architecture — SUPERSEDED by ARCHITECTURE.md
**Decision 2026-08-30: NEPTUN rejected by the user (observed false ballistic reports). Telegram-only.** Kept for history:
- NEPTUN already does the hard part (multi-channel fusion, geocoding, typing, confidence). Rung 1/2 of the ladder: consume it first.
- Own Telegram ingestion becomes (a) fallback if NEPTUN is down, (b) second opinion / latency race, (c) coverage of channels NEPTUN lacks (Ванёк).
- Per-channel "style learning" only matters for path (b)/(c); NEPTUN `/messages` feed already gives labelled multi-channel text to bootstrap/evaluate a parser without any Telegram credentials.

## 6. Ballistic events — timeline from the 20–30 Aug corpus (`samples-2026-08-30/*.jsonl`)

**21 Aug (UTC)** — THREAT: 21:56 UI `‼️ Загроза балістики з Курська` · 21:57 kpszsu `☄️ Загроза застосування балістичного озброєння з північного сходу` · 21:58 nebo_raketa `🚨 Тривога. Балістична небезпека з Курська`.
LAUNCH: 21:58 UI `Балістика на Київ!` · 21:59 war_monitor `☄ Балістика на Київ з Курська` + `‼️ Київ — спуск балістики!` ×5 · 21:59 AerisRimor `5 балістик на Київ!` · 21:59 UI `Бровари - Київ 4 балістики` · **22:00 kpszsu `🚀Декілька балістичних ракет на Київ!`** (2 min behind monitors) · 22:00–22:01 `Вибухи в Києві`.

**22 Aug** — THREAT 08:37–08:39 from all five. LAUNCH: **08:40 kpszsu `🚀Балістичні ракети на Київ.`** (first) · 08:40 war_monitor `☄ Балістика Бровари Бориспіль` · 08:42 kpszsu `Повторно … Київ/Бориспіль`, war_monitor `Виходи балістики на Бориспіль` · 08:44 war_monitor `💥 Вибухи Бориспіль, до 4 балістичних ракет`. nebo_raketa, AerisRimor, UI posted **no launch message** this time (AerisRimor 08:47: speculation only). 10:03 `Відбій загрози балістики`.

Takeaways: threat and launch have disjoint vocabularies (see ARCHITECTURE row 5); launch→impact ≈ 1–2 min; no single channel is reliably first; kpszsu is required as anchor. Noise seen in the same window: nebo_raketa ads for `@Kyiv`, `@kiev_radar_truvoga`, evening "no threat tonight" essays.

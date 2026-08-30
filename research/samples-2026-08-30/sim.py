"""Prototype replay: 3-stage ballistic/drone state machine over the merged corpus.
ponytail: research-only; hand-rolled regex + placeholder HOME/NEARBY. Not the product."""
import json, re, sys
from datetime import datetime, timedelta

CH = {"kpszsu": ("PS", 1.0), "war_monitor": ("WM", 0.9), "nebo_raketa": ("NR", 0.8),
      "AerisRimor": ("AR", 0.7), "Ukrainian_Intelligence": ("UI", 0.6)}
# ---- placeholder geometry (user will fill real sets) ----
HOME = {"Нивки", "Антонов"}
NEARBY = {"Святошин", "Борщагівка", "Шулявка", "Сирець", "Берковець", "Виноградар", "Біличі", "Академмістечко", "Коцюбинське", "Гостомель", "Відрадний", "Рембаза", "Пуща-Водиця"}
PLACES = {  # stem regex -> canonical
    r"оболон": "Оболонь", r"мінськ": "Мінський масив", r"пущ": "Пуща-Водиця", r"виноград": "Виноградар",
    r"куренів": "Куренівка", r"вишгород": "Вишгород", r"поділ": "Поділ", r"хотянів": "Хотянівка",
    r"тро[єея]щ|тро[юя]\b|троє\b": "Троєщина", r"нивк": "Нивки", r"бровар": "Бровари", r"дарниц": "Дарниця",
    r"двр": "ДВРЗ", r"вишнев": "Вишневе", r"васильк": "Васильків", r"антонов": "Антонов", r"коцюб": "Коцюбинське",
    r"жулян": "Жуляни", r"святош": "Святошин", r"борщаг": "Борщагівка", r"голос": "Голосіїв", r"обух": "Обухів",
    r"чабан": "Чабани", r"гатн": "Гатне", r"українк": "Українка", r"відрадн": "Відрадний", r"лівобереж": "Лівобережна",
    r"печерськ": "Печерськ", r"позняк": "Позняки", r"осокор": "Осокорки", r"лук.?янів": "Лук'янівка",
    r"шулявк": "Шулявка", r"русанів": "Русанівка", r"звіринц": "Звіринець", r"деміїв": "Деміївка", r"теремк": "Теремки",
    r"ірпін": "Ірпінь", r"буч[аі]\b": "Буча", r"бориспіл": "Бориспіль", r"біла церкв|\bбц\b": "Біла Церква",
    r"боярк": "Боярка", r"глевах": "Глеваха", r"лісов": "Лісовий", r"семиполк": "Семиполки", r"круглик": "Круглик",
    r"білогородк": "Білогородка", r"сирец|сирц": "Сирець", r"берков": "Берковець", r"білич": "Біличі", r"академ": "Академмістечко", r"гостомел": "Гостомель", r"рембаз": "Рембаза", r"галаган": "Галагани", r"київ|киев|столиц|над містом": "Київ",
}
KYIV_CITY = {"Оболонь", "Мінський масив", "Пуща-Водиця", "Виноградар", "Куренівка", "Поділ", "Троєщина", "Нивки",
             "Дарниця", "ДВРЗ", "Жуляни", "Святошин", "Борщагівка", "Голосіїв", "Відрадний", "Лівобережна", "Печерськ",
             "Позняки", "Осокорки", "Сирець", "Берковець", "Біличі", "Академмістечко", "Рембаза", "Галагани", "Лук'янівка", "Шулявка", "Русанівка", "Звіринець", "Деміївка", "Теремки", "Київ", "Лісовий"}

THREAT = re.compile(r"загроза (застосування )?баліст|балістичн\w* небезпек|ракетна небезпека", re.I)
LAUNCH = re.compile(r"(?<!загроза )баліст\w*\s*(на|летить|летять|-)|^\W*(ще |друга |третя |\d+ )?ціл[ьі]\b|\bціл[ьі]\W*$|ціль на|спуск баліст|\bвих[іо]д|пуск баліст|балістичн\w* ракет\w* на|\d+ балістик|🚀 ?ще\b|🚀 ?пуск", re.I)
NONKYIV = re.compile(r"ромни|лубни|полтав|чернігів|курщин|конотоп|миргород|шостк|суми|харків|дніпро|одес|запоріж|кременчук|ніжин|прилук|баштанк|кам.янськ|кривий", re.I)
BALLISTIC_WORD = re.compile(r"баліст|балист|☄|іскандер|кинжал", re.I)
DRONE = re.compile(r"реактив|бпла|шахед|мопед|🛵|🏍|🅿️|дрон", re.I)
CLEAR = re.compile(r"чисто|зникл|втрачен|мінус|відбій|без цілей", re.I)
NOISE = re.compile(r"підпис|@\w+|http|підтримати|чатик|реклам", re.I)


def places(text):
    found = []
    for pat, name in PLACES.items():
        if re.search(pat, text, re.I):
            found.append(name)
    return found


def tier_for(pl):
    if pl & HOME: return "URGENT"
    if pl & NEARBY: return "WATCH"
    if pl & KYIV_CITY: return "INFO"
    return None


def load(d0, d1):
    ms = []
    for ch in CH:
        for l in open(ch + ".jsonl"):
            m = json.loads(l)
            if not m["date"]: continue
            m["t"] = datetime.fromisoformat(m["date"].replace("+00:00", ""))
            if d0 <= m["t"] <= d1:
                m["ch"] = ch; ms.append(m)
    return sorted(ms, key=lambda m: m["t"])


def run(d0, d1):
    ms = load(d0, d1)
    last_burst = {}      # ch -> (t, text accumulated)
    threat_until = None  # ballistic threat context (any channel)
    ev = None            # active ballistic event
    drone_ev = {}        # tier -> last notify time
    pushes = []
    first_launch_t = None

    def push(t, kind, tier, title, body):
        pushes.append((t, kind, tier, title, body)); print(f"  >> {t:%H:%M:%S} {kind:8} {tier:6} {title} | {body}")

    for m in ms:
        ch, (tag, w) = m["ch"], CH[m["ch"]]
        text = re.sub(r"\s+", " ", m["text"]).strip()
        if not text: continue
        if NOISE.search(text) and not BALLISTIC_WORD.search(text): continue
        # burst: same channel, <=45 s apart -> context = concatenation
        t0, ctx = last_burst.get(ch, (None, ""))
        ctx = (ctx + " ‖ " + text) if t0 and (m["t"] - t0) <= timedelta(seconds=45) else text
        last_burst[ch] = (m["t"], ctx)
        pl = set(places(text))
        print(f"{m['t']:%H:%M:%S} {tag} | {text[:90]}")

        # --- stage 1: threat
        if THREAT.search(text):
            threat_until = m["t"] + timedelta(minutes=15)
            if not ev: push(m["t"], "NEW", "INFO", "Загроза балістики", f"{tag}: {text[:60]}")
            continue
        # --- stage 2: launch
        in_threat = threat_until and m["t"] <= threat_until
        is_launch = LAUNCH.search(text) and not THREAT.search(text) and len(text) <= 140 and not NONKYIV.search(text) and not re.search(r"збито|подавлено|були|зведення", text, re.I)
        bal_ctx = BALLISTIC_WORD.search(ctx) or (ev and (m["t"] - ev["last"]) < timedelta(minutes=5))
        if is_launch and (BALLISTIC_WORD.search(text) or in_threat or bal_ctx):
            target = pl & (KYIV_CITY | NEARBY | HOME | {"Бровари", "Бориспіль", "Вишгород"})
            if ev and (m["t"] - ev["last"]) < timedelta(minutes=5):
                ev["n"] += 1; ev["last"] = m["t"]; ev["src"].add(tag)
                if (m["t"] - ev["sound"]) >= timedelta(minutes=2):
                    ev["sound"] = m["t"]; push(m["t"], "RESOUND", "URGENT", f"Балістика: ще пуск (#{ev['n']})", f"{tag}: {text[:60]}")
                else:
                    push(m["t"], "UPDATE", "URGENT", f"Балістика #{ev['n']}", f"{tag}: {text[:60]}")
            elif target or (w >= 0.6 and re.search(r"на київ|київ —|у напрямку києва", text, re.I)):
                ev = {"start": m["t"], "last": m["t"], "sound": m["t"], "n": 1, "src": {tag}, "places": set(pl)}
                first_launch_t = first_launch_t or m["t"]
                push(m["t"], "NEW", "URGENT", "🔴 БАЛІСТИКА на Київ", f"{tag}: {text[:60]}")
            else:
                # launch, target unknown -> WATCH, promote when place arrives
                ev = {"start": m["t"], "last": m["t"], "sound": m["t"], "n": 1, "src": {tag}, "places": set(pl), "pending": True}
                push(m["t"], "NEW", "WATCH", "Пуск балістики, ціль уточнюється", f"{tag}: {text[:60]}")
            continue
        # --- stage 3: trajectory (place-only messages while event active)
        if ev and (m["t"] - ev["last"]) < timedelta(minutes=5) and pl and not DRONE.search(text) and len(text) <= 140 and not NONKYIV.search(text):
            ev["last"] = m["t"]; ev["places"] |= pl; ev["src"].add(tag)
            if ev.get("pending") and (m["t"] - ev["start"]) <= timedelta(seconds=90) and pl & (KYIV_CITY | NEARBY | HOME | {"Бровари", "Бориспіль"}):
                ev["pending"] = False; push(m["t"], "PROMOTE", "URGENT", "🔴 БАЛІСТИКА на Київ", f"{tag}: {text[:60]}")
            else:
                push(m["t"], "UPDATE", "URGENT", "Балістика: траєкторія", f"{tag}: {' / '.join(sorted(pl))}")
            continue
        # --- impact / clear
        if ev and CLEAR.search(text) and (m["t"] - ev["last"]) < timedelta(minutes=5):
            push(m["t"], "UPDATE", "URGENT", "Балістика: чисто/вибухи", f"{tag}: {text[:60]}"); continue
        # --- drones (no ballistic event context)
        if len(text) <= 140 and (DRONE.search(text) or (pl and DRONE.search(ctx))):
            tier = tier_for(pl)
            if tier:
                cool = {"URGENT": 5, "WATCH": 10, "INFO": 20}[tier]
                lt = drone_ev.get(tier)
                if not lt or (m["t"] - lt) >= timedelta(minutes=cool):
                    drone_ev[tier] = m["t"]
                    push(m["t"], "NEW", tier, f"Дрон: {' / '.join(sorted(pl))}", f"{tag}: {text[:60]}")
                else:
                    push(m["t"], "UPDATE", tier, f"Дрон: {' / '.join(sorted(pl))}", f"{tag}: {text[:60]}")
    print(f"\n  pushes: {len(pushes)}  (NEW/RESOUND/PROMOTE = sound: {sum(1 for p in pushes if p[1] in ('NEW','RESOUND','PROMOTE'))})")
    if first_launch_t: print(f"  first URGENT at {first_launch_t:%H:%M:%S}")


if __name__ == "__main__":
    for a, b in [l.split() for l in sys.argv[1:]]:
        print(f"\n################ {a} .. {b}")
        run(datetime.fromisoformat(a), datetime.fromisoformat(b))

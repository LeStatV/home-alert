"""Deterministic classification of one message. Regex only -- the launch path
never waits on anything. Vocabulary is global in v1; per-channel profiles come later.
"""
import re
from dataclasses import dataclass

TERSE = 140            # launches and trajectory calls are short; digests are not

# -- vocabulary (validated against research/samples-2026-08-30, see BEHAVIOR.md) --
# AerisRimor types ЦІЛЬʼ with U+02BC, which is a word character -- \b and \W both miss it
APOSTROPHE = r"[\u02bc\u2019'`\u02b9\u2032]?"

THREAT = re.compile(r"загроза (застосування )?баліст|балістичн\w* (небезпек|загроз)|ракетна небезпека", re.I)
LAUNCH = re.compile(
    # `\s+` matters: without it `\w*` backtracks and "балістична загроза" reads as "на"
    r"(?<!загроза )баліст\w*\s+(на\b|летить|летять)|баліст\w*\s*[-—]"
    r"|^\W*(ще |друга |третя |\d+ )?ціл[ьі]" + APOSTROPHE + r"(?![а-яіїєґ'])"
    r"|\bціл[ьі]" + APOSTROPHE + r"\W*$|ціль на"
    r"|спуск баліст|\bвих[іо]д|пуск баліст|балістичн\w* ракет\w* на|\d+ балістик"
    r"|🚀 ?ще\b|🚀 ?пуск", re.I)
BALLISTIC = re.compile(r"баліст|балист|☄|іскандер|кинжал", re.I)
CLEAR = re.compile(r"чисто|зникл|втрачен|мінус|відбій|без цілей|вибух", re.I)
DRONE = re.compile(r"реактив|бпла|шахед|мопед|дрон|🛵|🏍|🅿️", re.I)
# past tense and daily digests report what already happened -- never a launch
PAST = re.compile(r"\bбули\b|збито|подавлено|зведення|застосован|атакував|протягом дня", re.I)
RECON = re.compile(r"дорозвідк", re.I)
NOISE = re.compile(r"підпис|@\w+|http|підтримати|чатик|реклам|картка фоп", re.I)
# a launch naming one of these is a separate, log-only event (BEHAVIOR.md fix 1)
NON_KYIV = re.compile(
    r"ромни|лубни|полтав|чернігів|курщин|конотоп|миргород|шостк|сум[ищ]|харків|дніпро"
    r"|одес|запоріж|кременчук|ніжин|прилук|баштанк|кам.янськ|кривий|микола[їє]в"
    r"|вознесенськ|чорноморськ|херсон|черкас|житомир|вінниц|луцьк|рівн"
    r"|\bачм\b|аркадія|каменское|доброслав|совіньйон|усатове", re.I)

# stem -> canonical place. Kyiv city/oblast only; everything else is out of scope.
PLACES = {
    r"київ(?!ськ)|киев(?!ск)|столиц|над містом": "Київ",
    r"оболон": "Оболонь", r"мінськ": "Мінський масив", r"пущ": "Пуща-Водиця",
    r"виноград": "Виноградар", r"куренів": "Куренівка", r"поділ": "Поділ",
    r"тро[єея]щ|тро[юя]\b": "Троєщина", r"нивк": "Нивки", r"дарниц": "Дарниця",
    r"двр": "ДВРЗ", r"вишнев": "Вишневе", r"антонов|анонов": "Антонов",
    r"коцюб": "Коцюбинське", r"жулян": "Жуляни", r"святош": "Святошин",
    r"борщаг": "Борщагівка", r"голос": "Голосіїв", r"відрадн": "Відрадний",
    r"лівобереж": "Лівобережна", r"печерськ": "Печерськ", r"позняк": "Позняки",
    r"осокор": "Осокорки", r"лук.?янів": "Лук'янівка", r"шулявк": "Шулявка",
    r"русанів": "Русанівка", r"звіринц": "Звіринець", r"деміїв": "Деміївка",
    r"теремк": "Теремки", r"сирец|сирц": "Сирець", r"берков": "Берковець",
    r"білич": "Біличі", r"академ": "Академмістечко", r"рембаз": "Рембаза",
    # ЖК Файна Таун stands in the Антонов airspace; AerisRimor types Антонов as `анонов`
    r"файна": "Антонов", r"лісов": "Лісовий", r"биківн": "Биківня",
    r"хотів": "Хотів", r"теличк": "Теличка",
    # Kyiv oblast: a launch on these is still a launch on us
    r"бровар": "Бровари", r"бориспіл": "Бориспіль", r"вишгород": "Вишгород",
    r"васильк": "Васильків", r"ірпін": "Ірпінь", r"буч[аі]\b": "Буча",
    r"гостомел": "Гостомель", r"білогородк": "Білогородка", r"боярк": "Боярка",
    r"глевах": "Глеваха", r"чабан": "Чабани", r"гатн": "Гатне", r"обух": "Обухів",
    r"українк": "Українка", r"біла церкв|\bбц\b": "Біла Церква",
    r"семиполк": "Семиполки", r"круглик": "Круглик", r"перемог": "Перемога",
}


@dataclass(frozen=True, slots=True)
class Parse:
    places: tuple            # canonical Kyiv-area places named
    is_threat: bool          # a declared ballistic threat
    is_launch: bool          # strong launch wording, present tense, short
    names_ballistic: bool    # carries a ballistic word itself
    names_non_kyiv: bool     # names a city we do not cover
    is_clear: bool
    is_drone: bool
    is_recon: bool
    is_noise: bool
    terse: bool


def places(text):
    return tuple(sorted({name for stem, name in PLACES.items() if re.search(stem, text, re.I)}))


def zone(named, home, nearby):
    """How close to the household a report is: HOME, NEARBY, KYIV, or None.

    The whole geometry -- no coordinates, no distances, just which named set a
    canonical place falls into (ADR 6). A report naming both takes the nearer one.
    """
    if not named:
        return None
    if any(place in home for place in named):
        return "HOME"
    if any(place in nearby for place in named):
        return "NEARBY"
    return "KYIV"


def classify(text):
    is_threat = bool(THREAT.search(text))
    terse = len(text) <= TERSE
    return Parse(
        places=places(text),
        is_threat=is_threat,
        is_launch=bool(LAUNCH.search(text)) and not is_threat and terse
                  and not PAST.search(text) and not CLEAR.search(text),
        names_ballistic=bool(BALLISTIC.search(text)),
        names_non_kyiv=bool(NON_KYIV.search(text)),
        is_clear=bool(CLEAR.search(text)),
        is_drone=bool(DRONE.search(text)),
        is_recon=bool(RECON.search(text)),
        is_noise=bool(NOISE.search(text)) and not BALLISTIC.search(text),
        terse=terse,
    )

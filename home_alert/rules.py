"""Deterministic classification of one message. Regex only -- the launch path
never waits on anything.

The vocabulary here is global: every channel says `баліст` and `Нивки` the same way.
A `profiles.Profile` extends it with what one channel alone does -- its own ads and
digests, its own wording, its own spellings of a place (SPEC "Profiles as data").
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
# Cruise and hypersonic missiles (BEHAVIOR.md fix 5). `кр` is war_monitor's and
# AerisRimor's own shorthand for «крилата ракета»; bare `ракета` is deliberately absent
# -- kpszsu says it of ballistics too, and it would swallow every ballistic wave.
MISSILE = re.compile(r"циркон|онікс|оникс|бандерол|х-101|калібр|\bкр\b|крилат", re.I)
# A Kyiv place plus one of these is "it is coming at us now" -> URGENT (SPEC story 11).
# `захід` is the entry («Київ захід Цирконів», war_monitor); `курсом на захід` and
# `західним курсом` are the compass, which is all the other 30 uses in the corpus.
APPROACH = re.compile(r"підліт|над містом|(?<!на )(?<!курс )\bзахід\b|заліт"
                      r"|на київ(?!щ|ськ)|на місто", re.I)
# Only a bearing -> WATCH, never an immediate URGENT. The genitive `Києва` lives here and
# not in the gazetteer, so `у напрямку Києва` can never promote a pending event by itself.
DIRECTION = re.compile(r"(напрямк\w*|бік|сторону)\s+(києв|київ)", re.I)
# Kyiv-gating is on the target, not on every name in the message: a wave `на Київ повз
# Прилуки, Ніжин` is ours; `Ціль на Ромни!` is somebody else's (SPEC story 12).
# `на місто` is deliberately absent: war_monitor writes it of Dnipro too.
KYIV_TARGET = re.compile(r"на київ(?!щ|ськ)|курс(ом)? на київ", re.I)
CLEAR = re.compile(r"чисто|зникл|втрачен|мінус|відбій|без цілей|вибух", re.I)
# 🔄 is war_monitor's loitering marker (33 corpus posts, all its own, all drones), the
# same house style as 🅿️. Its bare `Nх` count prefix is NOT a drone word: 54 terse posts
# use it for cruise, KAB and ПРР too.
DRONE = re.compile(r"реактив|бпла|шахед|мопед|дрон|🛵|🏍|🅿️|🔄", re.I)
# past tense and daily digests report what already happened -- never a launch
PAST = re.compile(r"\bбули\b|збито|подавлено|зведення|застосован|атакував|протягом дня", re.I)
RECON = re.compile(r"дорозвідк", re.I)
# Ads and cross-promotions, which every channel runs. A launch message that carries a
# donation footer (`✅Розвідка України | Чатик | Підтримати`, Ukrainian_Intelligence) is
# still a launch, hence the ballistic exemption below -- which is exactly why the
# essay/digest patterns are per-profile instead: an essay *is* about ballistics.
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
    r"оболон": "Оболонь", r"мінськ": "Мінський масив",
    r"(?<![а-яіїєґ])пущ": "Пуща-Водиця",     # not `запущено`
    r"виноград": "Виноградар", r"куренів": "Куренівка", r"поділ": "Поділ",
    r"тро[єея]щ|тро[юя]\b": "Троєщина", r"нивк": "Нивки", r"дарниц": "Дарниця",
    r"двр": "ДВРЗ", r"вишнев": "Вишневе", r"антонов|анонов": "Антонов",
    r"(?<!михайло-)коцюб": "Коцюбинське",     # not Михайло-Коцюбинське, Чернігівщина
    r"жулян": "Жуляни", r"святош": "Святошин",
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


# the global patterns a profile's `type_vocab` may extend, by name
VOCAB = {"threat": THREAT, "launch": LAUNCH, "ballistic": BALLISTIC, "missile": MISSILE,
         "drone": DRONE, "clear": CLEAR, "recon": RECON}


def says(name, text, profile):
    """Does `text` use this vocabulary -- the global words, or this channel's own?

    kyiv_nebo writes `Більше не летить` where everyone else writes `чисто`; the global
    words stay global (SPEC: "Type vocabulary is global with per-profile extensions").
    """
    extra = profile.vocab.get(name) if profile else None
    return bool(VOCAB[name].search(text)) or bool(extra and extra.search(text))


@dataclass(frozen=True, slots=True)
class Parse:
    places: tuple            # canonical Kyiv-area places named
    is_threat: bool          # a declared ballistic threat
    is_launch: bool          # strong launch wording, present tense, short
    names_ballistic: bool    # carries a ballistic word itself
    names_non_kyiv: bool     # names a city we do not cover
    is_approach: bool        # missile wording for "on its way in": підліт/захід/на Київ
    is_direction: bool       # missile wording for a bearing only: `у напрямку Києва`
    names_missile: bool      # a cruise or hypersonic missile, not a ballistic one
    targets_kyiv: bool       # says Kyiv is the target, whatever else it names
    count: int               # the largest figure this message states about itself
    is_clear: bool
    is_drone: bool
    is_recon: bool
    is_noise: bool
    terse: bool


def places(text, profile=None):
    """Canonical Kyiv-area names this text mentions: the global gazetteer above, plus
    whatever spellings one channel alone uses (`profiles/<channel>.yaml: place_aliases`).
    """
    stems = PLACES | (profile.aliases if profile else {})
    return tuple(sorted({name for stem, name in stems.items()
                         if re.search(stem, text, re.I)}))


# Ordinals a channel counts its own launches with: «Четверта», «П'ятий, шостий та сьомий»
ORDINALS = [("перш", 1), ("друг", 2), ("трет", 3), ("четверт", 4), (r"п.?ят", 5),
            ("шост", 6), ("сьом", 7), ("восьм", 8), (r"дев.?ят", 9)]
# A digit is a count only where it counts something («5 Цирконів», «4-6 одиниць»,
# «2х КР») or enumerates («8 та 9»). `02:20`, `20 км` and `13 загиблих` are not.
COUNTED = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?\s*(?:х\b|шт|ракет|ціл|баліст|груп"
                     r"|одиниц|цирк|калібр|бандерол|онікс|шахед|бпла|дрон|реактив)"
                     r"|(\d+)\s*(?:та|і|й)\s*(\d+)\b", re.I)


def count(text):
    """The largest figure a message states about itself -- an ordinal or a number.

    Never summed across channels (BEHAVIOR.md fix 2: summing gave «#48» for six
    missiles). Anything above 20 is a model number, not a count: Х-101, С-400, Ту-95.
    """
    numbers = [int(digits) for match in COUNTED.finditer(text)
               for digits in match.groups() if digits and int(digits) <= 20]
    numbers += [value for stem, value in ORDINALS
                if re.search(rf"\b{stem}[аяиіоеу]", text, re.I)]
    return max(numbers, default=0)


# every threat type `type_of` can name, and so every value a profile's `default_type`
# may take: anything else routes nowhere and the channel goes quiet
TYPES = ("drone", "missile", "recon", "ballistic")


def type_of(parse, default=None):
    """The threat type a message names in its own words, or `default` when it names
    none -- the channel's `default_type`, since 88% of kyiv_nebo's posts are a bare
    place name (SPEC "Profiles as data").

    A message carrying both (`🅿️ Одеса 4х мгКР Бандероль над містом.`) is a drone: that
    is the precedence `events.py` routes launches on. `context.kind` is deliberately
    *not* this function -- it feeds the 3-min type memory, where a cruise word must not
    overwrite what the channel has been tracking.
    """
    if parse.is_drone:
        return "drone"
    if parse.names_missile:
        return "missile"
    if parse.is_recon:
        return "recon"
    if parse.names_ballistic or parse.is_launch or parse.is_threat:
        return "ballistic"
    return default


def stage(parse):
    """Where in the three-stage model a message sits: a declared `threat`, a `launch`
    call, an impact or all-clear report, or a bare `trajectory` call -- None if it is
    none of those. A cruise wave launches three ways (SPEC story 11): its own launch
    wording, a bearing that says Kyiv, or an approach word over a Kyiv place.
    """
    if parse.is_threat:
        return "threat"
    if parse.is_launch or (type_of(parse) == "missile"
                           and (parse.is_direction
                                or (parse.is_approach and parse.places))):
        return "launch"
    if parse.is_clear:
        return "clear"
    if parse.places:
        return "trajectory"
    return None


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


def classify(text, profile=None):
    is_threat = says("threat", text, profile)
    terse = len(text) <= TERSE
    # a launch call is short, present tense and not an all-clear; the missile approach
    # forms answer to exactly the same three guards
    is_clear = says("clear", text, profile)
    present = (not is_threat and terse
               and not PAST.search(text) and not is_clear)
    return Parse(
        places=places(text, profile),
        is_threat=is_threat,
        is_launch=says("launch", text, profile) and present,
        is_approach=bool(APPROACH.search(text)) and present,
        is_direction=bool(DIRECTION.search(text)) and present,
        names_missile=says("missile", text, profile),
        targets_kyiv=bool(KYIV_TARGET.search(text)),
        count=count(text),
        names_ballistic=says("ballistic", text, profile),
        names_non_kyiv=bool(NON_KYIV.search(text)),
        is_clear=is_clear,
        is_drone=says("drone", text, profile),
        is_recon=says("recon", text, profile),
        is_noise=(bool(NOISE.search(text)) and not BALLISTIC.search(text)
                  or bool(profile and profile.noise and profile.noise.search(text))),
        terse=terse,
    )

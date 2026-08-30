"""`review`: what the rules could not type last night, and what a model proposes about
it -- written as a diff nobody has applied.

The store is seeded row by row instead of replayed: every test here turns on *which*
messages the rules could not type, and picking those out of a corpus night is a hunt.
The profile under review is a real one, comments and all -- the diff has to land in a
file a human wrote, not in a file this project generated.
"""
import shutil
from datetime import datetime, timedelta

from harness import ROOT
from home_alert import notify, profiles, review, rules, store
from home_alert.reader import Message

CHANNEL = "war_monitor"          # a real profile with no `default_type`, so a message
                                 # with no threat word in it stays unparsed
NOW = datetime(2026, 8, 30, 22, 0, 0)

# Three ways this channel writes that the rules cannot read -- its own slang for a
# drone, twice, and a digest nobody has taught it to ignore -- plus one message the
# rules do read, which must not be in the report.
UNPARSED = ["пепелаци над Святошином", "Мигаль над Нивками",
            "два пепелаци курсом на Борщагівку", "Ранковий дайджест по країні"]
TYPED = ["Групи БпЛА курсом на Бучу"]
OLD = "пепелаци над Троєщиною"   # 30 h ago: outside a 24 h window


def seed(tmp_path, texts=None, channel=CHANNEL):
    """A store holding one night of this channel, the way the live agent left it."""
    profile = profiles.load(ROOT / "profiles").get(channel)
    db = store.Store(str(tmp_path / "home-alert.db"))
    rows = [(NOW - timedelta(hours=30), OLD)] + [
        # 10 minutes apart: the channel's 3-minute type memory must not label one
        # message with the message before it, which is the report's whole subject
        (NOW - timedelta(minutes=10 * (i + 1)), text)
        for i, text in enumerate(reversed(texts if texts is not None
                                          else UNPARSED + TYPED))]
    for msg_id, (when, text) in enumerate(rows):
        message = Message(channel, msg_id, when, None, text)
        db.record(message, rules.classify(text, profile), None, [])
    return str(tmp_path / "home-alert.db")


def config(tmp_path, provider="none"):
    """The household config as `review` reads it: profiles, geometry, provider."""
    directory = tmp_path / "profiles"
    directory.mkdir(exist_ok=True)
    shutil.copy(ROOT / "profiles" / f"{CHANNEL}.yaml", directory / f"{CHANNEL}.yaml")
    return {"profiles": directory, "llm": {"provider": provider},
            "home": ["Нивки", "Антонов"], "nearby": ["Святошин", "Борщагівка"]}


def test_the_run_reports_what_the_rules_could_not_type_and_says_it_once(tmp_path, capsys):
    """The report is the half of this command that works with no LLM at all, and the
    `system` line is what the owner sees on the phone after a nightly run (AC4)."""
    sink = notify.Recorder()
    review.review(config(tmp_path), seed(tmp_path), sink=sink)
    out = capsys.readouterr().out

    for text in UNPARSED:
        assert text in out
    assert TYPED[0] not in out
    assert OLD not in out                      # 30 h ago, outside the default window

    assert len(sink.pushes) == 1
    push = sink.pushes[0]
    assert push.topic == notify.SYSTEM_TOPIC and push.tier == "INFO"
    assert push.body == "4 unparsed across 1 channel, 0 proposals written"

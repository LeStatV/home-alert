"""`review`: what the rules could not type last night, and what a model proposes about
it -- written as a diff nobody has applied.

The store is seeded row by row instead of replayed: every test here turns on *which*
messages the rules could not type, and picking those out of a corpus night is a hunt.
The profile under review is a real one, comments and all -- the diff has to land in a
file a human wrote, not in a file this project generated.
"""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml

from harness import ROOT
from home_alert import cli, llm, notify, profiles, review, rules, store
from home_alert.reader import Message
from test_profiles import seam_2

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


def config(tmp_path, provider="none", channels=(CHANNEL,)):
    """The household config as `review` reads it: profiles, geometry, provider."""
    directory = tmp_path / "profiles"
    directory.mkdir(exist_ok=True)
    for channel in channels:
        shutil.copy(ROOT / "profiles" / f"{channel}.yaml", directory / f"{channel}.yaml")
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
    assert "no LLM provider configured" in out

    assert len(sink.pushes) == 1
    push = sink.pushes[0]
    assert push.topic == notify.SYSTEM_TOPIC and push.tier == "INFO"
    assert push.body == "4 unparsed across 1 channel, 0 proposals written"


# What a model answers, canned. Its own slang for a drone, the digest it wants
# silenced, one alias -- and four things that may not reach the file: a noise pattern
# the profile already carries, an example nobody in this window ever posted, an
# example the rules disagree with, and a vocabulary name that does not exist.
CANNED = json.dumps({
    "noise_patterns": ["^ранковий дайджест", "^загальна оцінка загроз"],
    "type_vocab": {"drone": ["пепелац", "мигал"], "aviation": ["тушк"]},
    "place_aliases": {"Борщагівка": ["борщага"]},
    "examples": [
        {"text": "пепелаци над Святошином", "type": "drone", "stage": "trajectory",
         "places": ["Святошин"]},
        {"text": "Мигаль над Нивками", "type": "drone", "places": ["Нивки"]},
        {"text": "Ранковий дайджест по країні", "noise": True},
        {"text": "Шахеди над Києвом", "type": "drone"},
        {"text": "два пепелаци курсом на Борщагівку", "type": "missile"},
    ]}, ensure_ascii=False)


class FakeLLM(llm.Client):
    """A provider that answers `CANNED`, through the real client's own contract."""

    def __init__(self, answer=CANNED):
        self.answer, self.asked = answer, None

    def complete(self, prompt, timeout, system=None):
        self.asked = prompt
        return self.answer


def run(tmp_path, monkeypatch, answer=CANNED, texts=None, db=None, channel=CHANNEL):
    """A review run against a canned provider; returns the review file it wrote."""
    fake = FakeLLM(answer)
    monkeypatch.setattr(llm, "client", lambda config: fake)
    review.review(config(tmp_path, "openai"), db or seed(tmp_path, texts, channel),
                  sink=notify.Recorder())
    return tmp_path / "profiles" / "reviews" / f"{NOW:%Y-%m-%d}.diff"


def digest(directory):
    """Every profile on disk, byte for byte."""
    return {file.name: hashlib.sha256(file.read_bytes()).hexdigest()
            for file in sorted(Path(directory).glob("*.yaml"))}


def test_the_diff_applies_to_the_real_profile_and_its_examples_pass_seam_2(
        tmp_path, monkeypatch):
    """AC1 and AC2, mechanically. The diff is applied with `patch`, the patched file
    is loaded through the real loader, and every example in it -- the ones that were
    already there and the ones the review proposed -- is run through seam 2. Nothing
    is edited by hand in between: that is what "without further edits" means."""
    file = run(tmp_path, monkeypatch)
    assert file.exists()

    applied = subprocess.run(["patch", "-p0", "-d", str(tmp_path), "--dry-run"],
                             stdin=file.open(), capture_output=True, text=True)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    subprocess.run(["patch", "-p0", "-d", str(tmp_path)], stdin=file.open(),
                   check=True, capture_output=True)

    profile = profiles.load(tmp_path / "profiles")[CHANNEL]
    texts = [example["text"] for example in profile.examples]
    assert "пепелаци над Святошином" in texts
    assert "☄ Вихід у напрямку Києва" in texts        # the profile's own, still there
    for example in profile.examples:
        got = seam_2(profile, example)
        listed = set(example) - {"text"}
        assert listed and {field: got[field] for field in listed} == {
            field: example[field] for field in listed}, example


def test_the_profiles_on_disk_are_the_same_bytes_after_a_run(tmp_path, monkeypatch):
    """AC3, and the whole point of the story: a review proposes, it never applies."""
    directory = config(tmp_path)["profiles"]     # copies the real profile into place
    before = digest(directory)
    run(tmp_path, monkeypatch)
    assert digest(directory) == before


def test_the_command_line_runs_with_no_ntfy_and_refuses_a_window_it_cannot_read(
        tmp_path, capsys):
    """The nightly run is `docker compose run --rm agent ... review`, and it must not
    need an ntfy server to be worth running -- the report is the half that always
    works. A `--since` nobody can parse is an error at the command line, not a
    week-long window discovered in the output."""
    settings = config(tmp_path) | {"profiles": str(tmp_path / "profiles"),
                                   "db": seed(tmp_path)}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")

    cli.main(["review", "--config", str(path)])
    out = capsys.readouterr().out
    assert "пепелаци над Святошином" in out
    assert "no ntfy server" in out

    with pytest.raises(SystemExit):
        cli.main(["review", "--config", str(path), "--since", "24 hours"])
    assert "24h or 7d" in capsys.readouterr().err


def test_what_the_rules_or_the_night_disagree_with_never_reaches_the_diff(
        tmp_path, monkeypatch, capsys):
    """Four things a model proposes happily and none of which may land: a vocabulary
    the rules do not have, an example of a message nobody posted, an example the
    classifier reads differently, and a pattern the profile already carries. Each is
    dropped and written into the review file's header -- a silently shortened
    proposal reads as a model that agreed with us."""
    text = run(tmp_path, monkeypatch).read_text(encoding="utf-8")
    assert "Шахеди над Києвом" not in text.partition("--- ")[2]
    assert "не летить" not in text
    for said in ("aviation", "not one of the messages under review",
                 "the rules say type 'drone', not 'missile'",
                 "the profile already has it"):
        assert said in text, said
    # and the header is comments: `patch` reads past them, which is what makes the
    # explanation and the diff one file instead of two
    assert text.startswith("# home-alert review")


def test_a_channel_with_no_profile_is_named_and_left_alone(tmp_path, monkeypatch,
                                                           capsys):
    """`review` proposes changes to profiles that exist; a channel with none is what
    `add-channel` is for, and saying so is more use than an empty diff."""
    file = run(tmp_path, monkeypatch, channel="newcomer")
    out = capsys.readouterr().out
    assert not file.exists()
    assert "add-channel @newcomer" in out


@pytest.mark.parametrize("answer", ["Sorry, I cannot help with that.",
                                    '{"examples": [{"text": "Нивки"',
                                    '{"type_vocab": "drone", "examples": "some"}'])
def test_a_provider_that_says_nothing_useful_costs_the_proposal_only(
        tmp_path, monkeypatch, capsys, answer):
    """The same fail-open as the live path and as `add-channel`: the report has been
    printed by the time the provider is asked, and it is the half worth having."""
    file = run(tmp_path, monkeypatch, answer=answer)
    out = capsys.readouterr().out
    assert not file.exists()
    assert "пепелаци над Святошином" in out
    assert "4 unparsed across 1 channel, 0 proposals written" in out


def test_a_second_night_extends_the_line_the_first_review_added(tmp_path, monkeypatch):
    """Tonight's proposal has to merge into the `drone:` line last night's review put
    there. Appending a second `drone:` under `type_vocab:` is a duplicate key, and
    PyYAML keeps the last one -- which would silently drop last night's words."""
    first = run(tmp_path, monkeypatch)
    subprocess.run(["patch", "-p0", "-d", str(tmp_path)], stdin=first.open(),
                   check=True, capture_output=True)

    tonight = ["три бавовники над Виноградарем"]
    answer = json.dumps({"type_vocab": {"drone": ["пепелац", "бавовник"]},
                         "examples": [{"text": tonight[0], "type": "drone",
                                       "places": ["Виноградар"], "count": 3}]},
                        ensure_ascii=False)
    second = run(tmp_path, monkeypatch, answer=answer, texts=tonight,
                 db=seed(tmp_path, tonight))
    subprocess.run(["patch", "-p0", "-d", str(tmp_path)], stdin=second.open(),
                   check=True, capture_output=True)

    profile = tmp_path / "profiles" / f"{CHANNEL}.yaml"
    assert profile.read_text(encoding="utf-8").count("  drone:") == 1
    loaded = profiles.load(tmp_path / "profiles")[CHANNEL]
    assert seam_2(loaded, {"text": "пепелаци над Святошином"})["type"] == "drone"
    assert seam_2(loaded, {"text": tonight[0]})["type"] == "drone"


def test_a_store_nobody_has_written_to_still_says_so_once(tmp_path, capsys):
    """AC4 is per run, not per finding: a night with nothing in it is exactly the
    night the owner wants a line about."""
    sink = notify.Recorder()
    review.review(config(tmp_path), str(tmp_path / "empty.db"), sink=sink)
    assert "which is empty" in capsys.readouterr().out
    assert [push.body for push in sink.pushes] == [
        "0 unparsed across 0 channels, 0 proposals written"]


SECOND = "nebo_raketa"           # a second profile with no `default_type` either
GEESE = ["гуси над Оболонню", "дві гуски курсом на Позняки"]


def test_a_night_across_two_channels_is_one_file_patch_still_takes(tmp_path,
                                                                   monkeypatch):
    """The nightly run is several channels, and their hunks are concatenated into one
    review file. `patch` has to take the whole of it in one go, and each channel's
    examples have to stay that channel's: the verbatim gate is per channel, so
    war_monitor's messages may not be proposed as examples of @nebo_raketa."""
    settings = config(tmp_path, "openai", (CHANNEL, SECOND))
    db = seed(tmp_path)
    seed(tmp_path, GEESE, SECOND)
    monkeypatch.setattr(llm, "client", lambda config: FakeLLM())
    sink = notify.Recorder()
    file = review.review(settings, db, sink=sink)

    text = file.read_text(encoding="utf-8")
    assert text.count("--- profiles/") == 2
    assert f"profiles/{SECOND}.yaml" in text
    subprocess.run(["patch", "-p0", "-d", str(tmp_path)], stdin=file.open(),
                   check=True, capture_output=True)

    loaded = profiles.load(settings["profiles"])
    assert [e["text"] for e in loaded[SECOND].examples if e["text"] in UNPARSED] == []
    for channel, profile in loaded.items():
        for example in profile.examples:
            got = seam_2(profile, example)
            listed = set(example) - {"text"}
            assert {f: got[f] for f in listed} == {f: example[f] for f in listed}, (
                channel, example)
    assert sink.pushes[0].body == "6 unparsed across 2 channels, 2 proposals written"


def test_a_week_is_a_window_too():
    """`--since 7d` after a quiet week, and `7d` is the other half of the parser."""
    assert review.window("7d") == timedelta(days=7)
    assert review.window("24h") == review.window("1d")

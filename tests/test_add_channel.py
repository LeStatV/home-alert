"""`add-channel`: fetched history in, coverage report out, a draft nobody has approved.

The Telethon half is the owner's to verify -- there are no credentials here -- so
every test feeds the same thing a fetch produces: a JSONL history file. The research
corpus *is* fetched history, which is what makes AC1 machine-verifiable.
"""
import json

import pytest
import yaml

from harness import ROOT
from home_alert import add_channel, llm, profiles
from test_profiles import seam_2

HISTORY = ROOT / "research" / "samples-2026-08-30" / "kyiv_nebo.jsonl"


def config(tmp_path, provider="none"):
    """The household config as `add-channel` reads it: profiles, geometry, provider.
    No ntfy, no db -- the command must not need either, and this proves it."""
    (tmp_path / "profiles").mkdir(exist_ok=True)
    return {"profiles": tmp_path / "profiles",
            "llm": {"provider": provider},
            "home": ["Нивки", "Антонов"],
            "nearby": ["Святошин", "Борщагівка"]}


def test_coverage_lists_every_message_the_rules_could_not_type(tmp_path, capsys):
    """AC2. On a channel with no profile yet, 88% of kyiv_nebo's posts are a bare
    place name that types as nothing -- and the owner has to read them verbatim to
    see that, which is how `default_type: drone` gets discovered in the first place."""
    add_channel.add("@kyiv_nebo", config(tmp_path), history_path=HISTORY, limit=500)
    out = capsys.readouterr().out
    assert "500 messages" in out
    assert "unparsed" in out
    # verbatim, with its timestamp -- and these two are the report doing its job:
    # a bare microdistrict name types as nothing without `default_type`, and the
    # channel's own all-clear wording is invisible to the global CLEAR words
    assert "2026-08-27T17:43:16  Борщагівки" in out
    assert "Очікуємо на відбої" in out


def test_without_a_provider_the_report_still_runs_and_drafting_says_so(tmp_path, capsys):
    """AC4. The LLM is optional everywhere in this project, and this command is no
    exception: no provider costs the owner the draft, never the coverage report."""
    add_channel.add("@kyiv_nebo", config(tmp_path), history_path=HISTORY, limit=500)
    out = capsys.readouterr().out
    assert "unparsed" in out
    assert "drafting skipped" in out
    assert not list((tmp_path / "profiles").rglob("*.yaml"))


# What a model answers, canned. Three of these fields are deliberately wrong -- a
# vocabulary name the rules do not have, a regex that does not compile, a canonical
# place that is not in the gazetteer -- and three examples are labelled wrongly. None
# of it may reach the draft file, and all of it has to be said out loud.
CANNED = """Here is the profile:
{"noise_patterns": ["^кіт келлог", "вічна пам.ять", "^(працює"],
 "type_vocab": {"clear": ["більше не летить", "очікуємо на відбо"],
                "aviation": ["тушк", "ту-95"]},
 "place_aliases": {"Борщагівка": ["борщаги"], "Солом'янка": ["солома"]},
 "examples": [
   {"text": "Цілі на Київ", "type": "ballistic", "stage": "launch", "places": ["Київ"]},
   {"text": "Загроза балістики з Брянська", "type": "ballistic", "stage": "threat"},
   {"text": "Більше не летить", "stage": "clear", "count": null},
   {"text": "Реактивний Шахед підлітає до Броварів", "type": "drone",
    "places": ["Бровари"]},
   {"text": "4 Циркони", "type": "missile", "count": 4},
   {"text": "Борщаги, Вишневе", "type": null, "places": ["Борщагівка", "Вишневе"]},
   {"text": "Нивки", "type": "drone", "places": ["Нивки"]},
   {"text": "Троєщина - уважно", "type": "missile", "places": ["Троєщина"]}]}
"""


class FakeLLM(llm.Client):
    """A provider that answers `CANNED`, through the real client's own contract."""

    def complete(self, prompt, timeout, system=None):
        self.asked = prompt
        return CANNED


def draft(tmp_path, monkeypatch, answer=CANNED, capsys=None):
    """Run the command with a canned provider; return the draft path and the output."""
    fake = FakeLLM()
    monkeypatch.setattr(fake, "complete", lambda *a, **kw: answer)
    monkeypatch.setattr(llm, "client", lambda config: fake)
    add_channel.add("@kyiv_nebo", config(tmp_path, "openai"),
                    history_path=HISTORY, limit=500)
    return tmp_path / "profiles" / "drafts" / "kyiv_nebo.yaml"


def test_every_example_in_the_draft_passes_seam_2(tmp_path, monkeypatch, capsys):
    """AC1, and the reason the drafter is not just a JSON writer: whatever the model
    proposes, each example is run through the real classifier with the draft's own
    vocabulary, and only the ones that reproduce their own labels are written. This
    test re-runs that check independently -- the classifier, the loaded profile, the
    example's own fields -- so a broken gate cannot certify itself."""
    file = draft(tmp_path, monkeypatch)
    raw = yaml.safe_load(file.read_text(encoding="utf-8"))

    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "kyiv_nebo.yaml").write_text(
        yaml.safe_dump(raw | {"weight": 0.6}, allow_unicode=True), encoding="utf-8")
    profile = profiles.load(approved)["kyiv_nebo"]

    assert profile.examples
    for example in profile.examples:
        got = seam_2(profile, example)     # the profiles' own check, not the drafter's
        listed = set(example) - {"text"}
        assert listed and listed <= set(got)
        assert {field: got[field] for field in listed} == {field: example[field]
                                                           for field in listed}


def test_what_the_rules_disagree_with_is_dropped_and_said_out_loud(tmp_path, monkeypatch,
                                                                   capsys):
    """The three examples the model got wrong go, and the owner is told how many and
    why -- a silently shortened list would read as a model that agreed with us."""
    file = draft(tmp_path, monkeypatch)
    out = capsys.readouterr().out
    texts = [e["text"] for e in yaml.safe_load(file.read_text(encoding="utf-8"))["examples"]]
    assert "Цілі на Київ" in texts
    assert "Більше не летить" in texts        # kept by the draft's own `clear` vocabulary
    assert "Нивки" not in texts               # no `default_type`: types as nothing
    assert "Троєщина - уважно" not in texts   # not a missile
    assert "6 of 8" in out and "dropped" in out


def test_a_field_the_profile_schema_does_not_have_never_reaches_the_file(tmp_path,
                                                                         monkeypatch,
                                                                         capsys):
    """A vocabulary name the rules do not have, a regex that does not compile and a
    place outside the gazetteer are all things a model invents happily. Each is
    dropped with a note; the file that lands is one `profiles.load` accepts."""
    raw = yaml.safe_load(draft(tmp_path, monkeypatch).read_text(encoding="utf-8"))
    out = capsys.readouterr().out
    assert set(raw["type_vocab"]) == {"clear"}
    assert "aviation" in out
    assert raw["noise_patterns"] == ["^кіт келлог", "вічна пам.ять"]
    assert set(raw["place_aliases"]) == {"Борщагівка"}
    assert "Солом'янка" in out


def test_the_draft_is_not_live_and_says_what_is_missing(tmp_path, monkeypatch, capsys):
    """AC3's other half. The draft carries no weight, and it is written where
    `profiles.load` does not look -- so approving a channel is two deliberate acts:
    setting the weight and moving the file."""
    file = draft(tmp_path, monkeypatch)
    assert file.parent.name == "drafts"
    raw = yaml.safe_load(file.read_text(encoding="utf-8"))
    assert raw["weight"] is None and raw["default_type"] is None
    assert "set the weight" in file.read_text(encoding="utf-8")
    assert set(raw) <= profiles.KEYS
    # the drafts directory lives under `profiles/`, and the loader still sees nothing
    with pytest.raises(AssertionError, match="no profiles"):
        profiles.load(tmp_path / "profiles")


# An apology, prose that happens to contain braces, JSON cut off mid-answer, and JSON
# of the wrong shape entirely -- four answers a 60-second call really does come back
# with, and none of them may cost the owner the report they already waited for.
USELESS = ["Sorry, I cannot help with that.",
           "Here {is} my thinking about the channel...",
           '{"noise_patterns": ["a"], "examples": [{"text": "Нивки"',
           '{"type_vocab": "clear", "examples": "about thirty of them"}']


@pytest.mark.parametrize("answer", USELESS)
def test_a_provider_that_says_nothing_useful_costs_the_draft_only(tmp_path, monkeypatch,
                                                                  capsys, answer):
    """Same fail-open as the live path: the coverage report has already been printed,
    and it is the half of this command that is worth having on its own."""
    file = draft(tmp_path, monkeypatch, answer=answer)
    out = capsys.readouterr().out
    assert not file.exists()
    assert "unparsed" in out and "drafting skipped" in out


def test_a_corpus_directory_is_not_one_channels_history(tmp_path):
    """`config.yaml: corpus` names a directory of six channels, and it is the obvious
    thing to paste after `--history`. Six channels under one channel's name make a
    report that reads as right and is not: the other five decide this one's
    `threads_by_reply`, and their typed messages bury its unparsed ones."""
    with pytest.raises(AssertionError, match="one channel's history file"):
        add_channel.add("@kyiv_nebo", config(tmp_path), history_path=HISTORY.parent)


def test_a_noise_pattern_is_run_over_the_history_before_it_is_written(tmp_path,
                                                                      monkeypatch,
                                                                      capsys):
    """A noise pattern silences the channel for good, and one nobody has run is a
    guess: each is printed with what it would swallow out of this very history, so
    `.*` reads as `500/500` instead of as a plausible line of YAML."""
    answer = json.dumps({"noise_patterns": [".*", "^Нивки$"], "examples": []})
    file = draft(tmp_path, monkeypatch, answer=answer)
    out = capsys.readouterr().out
    assert yaml.safe_load(file.read_text(encoding="utf-8"))["noise_patterns"] == [
        ".*", "^Нивки$"]
    assert "silences 500/500" in out


def test_a_noise_pattern_too_slow_to_run_is_dropped(tmp_path, monkeypatch, capsys):
    r"""`^(\w+\s?)+$` compiles fine and takes 40 s on one of this channel's messages;
    the live path would run it on every post. The budget is what catches it -- the
    test moves the budget rather than spending the 40 s."""
    monkeypatch.setattr(add_channel, "NOISE_BUDGET", 0)
    answer = json.dumps({"noise_patterns": ["^Нивки$"], "examples": []})
    file = draft(tmp_path, monkeypatch, answer=answer)
    out = capsys.readouterr().out
    assert yaml.safe_load(file.read_text(encoding="utf-8"))["noise_patterns"] == []
    assert "too slow" in out


def test_an_example_that_is_not_an_object_does_not_cost_the_draft(tmp_path, monkeypatch,
                                                                  capsys):
    """Models answer with a list of strings where a list of objects was asked for."""
    answer = json.dumps({"examples": ["Нивки",
                                      {"text": "4 Циркони", "type": "missile"}]})
    file = draft(tmp_path, monkeypatch, answer=answer)
    assert [e["text"] for e in yaml.safe_load(file.read_text(encoding="utf-8"))
            ["examples"]] == ["4 Циркони"]
    assert "not an object" in capsys.readouterr().out

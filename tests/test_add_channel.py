"""`add-channel`: fetched history in, coverage report out, a draft nobody has approved.

The Telethon half is the owner's to verify -- there are no credentials here -- so
every test feeds the same thing a fetch produces: a JSONL history file. The research
corpus *is* fetched history, which is what makes AC1 machine-verifiable.
"""
import pytest
import yaml

from harness import ROOT
from home_alert import add_channel, llm, profiles

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

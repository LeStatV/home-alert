"""Seam 2: every labelled example in every `profiles/<channel>.yaml` is a test.

Text (plus the profile's context flags) goes into the classifier and the four
documented Parse fields come out -- `type`, `stage`, `places`, `count`. This is the
only test that calls the classifier directly, and it asserts only the fields an
example actually lists, so a count-only example says nothing about the rest.
"""
from datetime import datetime

import pytest

from harness import ROOT
from home_alert import profiles, rules

PROFILES = profiles.load(ROOT / "profiles")


def test_the_six_configured_channels_load_from_yaml():
    assert set(PROFILES) == {"war_monitor", "nebo_raketa", "AerisRimor",
                             "Ukrainian_Intelligence", "kpszsu", "kyiv_nebo"}
    assert PROFILES["kpszsu"].weight == 1.0
    assert PROFILES["kyiv_nebo"].default_type == "drone"


def test_kyiv_nebo_is_expected_to_be_silent_in_its_pre_dawn_blackout():
    """The 03:00-07:00 UTC hole is the channel's habit, not an outage: hourly counts
    across 13 days are 0/1/2/2 against 39 at 07:00 (channel-eval-kyiv_nebo.md §6).
    #8 reads this when it decides which channels count as active."""
    silent = PROFILES["kyiv_nebo"].expected_silent
    assert silent(datetime(2026, 8, 28, 3, 0))
    assert silent(datetime(2026, 8, 28, 5, 42))
    assert not silent(datetime(2026, 8, 28, 2, 59))
    assert not silent(datetime(2026, 8, 28, 7, 0))
    assert not PROFILES["war_monitor"].expected_silent(datetime(2026, 8, 28, 5, 42))


# The global vocabulary lives in `rules.py`, so no profile carries its examples. This is
# the table for it. `файна таун` is spec-mandated (SPEC Geometry: ЖК Файна Таун stands in
# the Антонов airspace) and appears nowhere in the corpus -- the one example here that is
# not a verbatim corpus message.
GLOBAL = [
    {"text": "Файна таун", "places": ["Антонов"], "type": None, "stage": "trajectory"},
]


def examples():
    for example in GLOBAL:
        yield pytest.param(None, example, id=f"global:{example['text'][:40]}")
    for channel, profile in sorted(PROFILES.items()):
        for example in profile.examples:
            yield pytest.param(profile, example, id=f"{channel}:{example['text'][:40]}")


@pytest.mark.parametrize("profile,example", list(examples()))
def test_profile_example(profile, example):
    """One labelled message from a profile, through the classifier and out.

    Only the fields the example lists are asserted -- a count-only example says
    nothing about places, and a noise example says nothing at all about type.
    `profile` is None for the global vocabulary table."""
    parse = rules.classify(example["text"], profile)
    got = {"type": rules.type_of(parse, profile.default_type if profile else None),
           "stage": rules.stage(parse),
           "places": list(parse.places),
           "count": parse.count,
           "noise": parse.is_noise}
    listed = set(example) - {"text"}
    assert listed and listed <= set(got), f"unknown field(s) in example: {listed - set(got)}"
    assert {field: got[field] for field in listed} == {field: example[field]
                                                       for field in listed}


BAD = {
    "no profiles at all": {},                                   # wrong cwd, empty dir
    "war_monitor.yaml": "channel: war_monitor\nweight: 8\n",    # the missed decimal point
    "kyiv_nebo.yaml": "weight: 0.6\ndefault_type: drones\n",    # a type nothing routes on
}


@pytest.mark.parametrize("name,text", list(BAD.items()))
def test_a_profile_that_would_break_the_alert_path_never_loads(tmp_path, name, text):
    """A weight of `8` passes every trust threshold there is, a `default_type` nothing
    matches makes the channel inert, and an empty directory is a notifier with no
    channels that still exits 0. All three are quiet in production and loud here."""
    if text:
        (tmp_path / name).write_text(text, encoding="utf-8")
    with pytest.raises(AssertionError):
        profiles.load(tmp_path)

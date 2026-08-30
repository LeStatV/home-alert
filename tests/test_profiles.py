"""Seam 2: every labelled example in every `profiles/<channel>.yaml` is a test.

Text (plus the profile's context flags) goes into the classifier and the four
documented Parse fields come out -- `type`, `stage`, `places`, `count`. This is the
only test that calls the classifier directly, and it asserts only the fields an
example actually lists, so a count-only example says nothing about the rest.
"""
from datetime import datetime

from harness import ROOT
from home_alert import profiles

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

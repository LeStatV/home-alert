"""What the agent knows about one channel, as data: `profiles/<channel>.yaml`.

A channel with no profile file is not read at all -- there is no second list of
active channels to keep in step with these. Everything channel-specific lives here:
the trust weight, the type a bare place-name post means, the hours the channel is
expected to be quiet, the wording it uses that the global vocabulary in `rules.py`
does not, and labelled examples that run as tests (`tests/test_profiles.py`).
"""
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path

import yaml

from .rules import TYPES, VOCAB

# every key a profile may carry; anything else is a typo, and a typo'd weight or
# noise pattern would fail silently on the alert path
KEYS = {"channel", "title", "weight", "language", "threads_by_reply", "default_type",
        "quiet_hours", "noise_patterns", "type_vocab", "place_aliases", "examples"}


def _compile(patterns):
    return re.compile("|".join(patterns), re.I) if patterns else None


@dataclass(frozen=True, slots=True)
class Profile:
    channel: str
    weight: float                # trust: >=0.8 wakes the house alone, >=0.6 may launch
    default_type: str | None     # what a bare place-name post from here means
    quiet_hours: tuple           # (start, end) UTC times this channel sleeps through
    noise: re.Pattern | None     # this channel's ads, essays and digests
    vocab: dict                  # rules vocabulary name -> this channel's extra wording
    aliases: dict                # extra place stem -> canonical name, this channel only
    examples: tuple              # labelled messages; every one of them is a test
    language: str = "uk"
    threads_by_reply: bool = False   # documentation until something reads it (#8/#18)
    title: str = ""

    def expected_silent(self, when):
        """Is this channel meant to be quiet at this time? A gap inside the window is
        the channel sleeping, not the agent losing it (#8 shows `N/6 каналів активні`).

        ponytail: a window that crosses midnight has to be written as two, e.g.
        `["22:00-23:59", "00:00-02:00"]`. No channel needs one; the day it does, this
        is one `if` wide.
        """
        return any(start <= when.time() < end for start, end in self.quiet_hours)


def _window(text):
    start, end = (time.fromisoformat(part) for part in text.split("-"))
    return start, end


def load(directory):
    """Every profile in `directory`, keyed by channel. The filename is the channel."""
    loaded = {}
    for file in sorted(Path(directory).glob("*.yaml")):
        raw = yaml.safe_load(file.read_text(encoding="utf-8"))
        assert isinstance(raw, dict) and "weight" in raw, f"{file.name}: no weight"
        weight = float(raw["weight"])
        assert 0.0 <= weight <= 1.0, f"{file.name}: weight {weight} outside 0..1"
        assert raw.get("default_type") in (None, *TYPES), (
            f"{file.name}: default_type {raw['default_type']!r} is not one of {TYPES}")
        unknown = set(raw) - KEYS
        assert not unknown, f"{file.name}: unknown key(s) {sorted(unknown)}"
        assert raw.get("channel", file.stem) == file.stem, f"{file.name}: channel mismatch"
        vocab = raw.get("type_vocab") or {}
        assert set(vocab) <= set(VOCAB), (
            f"{file.name}: type_vocab extends nothing in rules.VOCAB: "
            f"{sorted(set(vocab) - set(VOCAB))}")
        loaded[file.stem] = Profile(
            channel=file.stem,
            weight=weight,
            default_type=raw.get("default_type"),
            quiet_hours=tuple(_window(w) for w in raw.get("quiet_hours") or ()),
            noise=_compile(raw.get("noise_patterns")),
            vocab={name: _compile(patterns) for name, patterns in vocab.items()},
            aliases={stem: canonical
                     for canonical, stems in (raw.get("place_aliases") or {}).items()
                     for stem in stems},
            examples=tuple(raw.get("examples") or ()),
            language=raw.get("language", "uk"),
            threads_by_reply=bool(raw.get("threads_by_reply")),
            title=raw.get("title", ""),
        )
    assert loaded, f"no profiles in {directory}: the notifier would read no channels"
    return loaded

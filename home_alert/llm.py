"""The optional second opinion: what the rules could not type, an LLM may.

Everything here is allowed to fail. The provider is one config line (SPEC story 28),
the call is given a 3-second budget, and any answer that is late, malformed or absent
leaves the rules verdict exactly as it was (story 29). The launch path never comes
here at all (story 32) -- `events.py` calls `enrich` only for messages nothing else
could type, and never for a launch.

ponytail: `TIMEOUT` is what the transport is *asked* for, not a deadline anything
enforces. `urlopen` applies it per socket operation, so a provider dribbling a long
answer a byte at a time blocks longer than 3 s; the Copilot SDK's `timeout=` is a
guessed keyword and may be ignored outright, in which case a hung call hangs the
handler with nothing but a WARNING to show for it. A real ceiling needs the call on
its own thread (`asyncio.to_thread` + `wait_for`), which is the upgrade the day a
provider is actually configured.
"""
import dataclasses
import importlib
import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass

from . import rules

log = logging.getLogger(__name__)

TIMEOUT = 3.0            # seconds; the spec's number, not the household's to tune
                         # -- and asked of the transport, not enforced (see above)
DRAFT_TIMEOUT = 60.0     # `add-channel` is the offline path: no household is waiting
                         # on it, and 500 messages do not summarize in three seconds

# Types the answer may carry. `recon` is deliberately absent: the drone branch drops
# recon flights, so letting the model say `recon` would let it *silence* a report --
# and the one thing enrichment may never do is lower a verdict.
TYPES = ("drone", "missile", "ballistic")
COPILOT_SDK = "github_copilot_sdk"


@dataclass(frozen=True, slots=True)
class Enrichment:
    """What the model added: a threat type, canonical Kyiv places, or neither."""
    type: str | None
    places: tuple


def read(answer):
    """One model answer as an `Enrichment`, or None if it is not usable.

    Robust by construction: the JSON object is cut out of whatever prose the model
    wrapped it in, an unknown type is dropped, and place names go through the same
    gazetteer every other place in this project does -- so the model can name a place
    but never invent one, and never one outside Kyiv.
    """
    found = re.search(r"\{.*\}", answer or "", re.S)
    if not found:
        return None
    data = json.loads(found.group())
    if not isinstance(data, dict):
        return None
    kind = data.get("type")
    named = data.get("places") or []
    if isinstance(named, str):
        named = [named]
    return Enrichment(kind if kind in TYPES else None,
                      rules.places(" ".join(str(name) for name in named)))


# what a type in the answer sets on the parse -- one flag each, all of them raising
FLAGS = {"drone": "is_drone", "missile": "names_missile", "ballistic": "names_ballistic"}


def unresolved(parse, kind):
    """Is this a message nothing deterministic could type -- the only kind the model
    is ever shown (SPEC story 29)?

    `kind` is what context resolved: the message's own words, its reply parent, the
    channel's 3-minute memory or its `default_type`. A launch call, a declared threat
    and a ballistic word all type themselves through `rules.type_of`, so none of them
    can reach the provider -- the launch path stays rules-only (story 32). An
    all-clear is excluded too: there is no tier to raise and the free tiers this runs
    on are rate-limited in requests per minute.
    """
    return kind is None and rules.type_of(parse) is None and not parse.is_clear


def merge(parse, enrichment):
    """The rules verdict with the model's answer folded in -- upwards only.

    Two things may change: places gain what the model named and the rules missed, and
    a message the rules could not type gets one. Nothing is ever removed, no flag is
    ever cleared, and a message the rules already typed keeps its own type -- so an
    answer can raise a tier or lengthen a chain, never quiet either (SPEC story 29).
    """
    if enrichment is None:
        return parse
    added = {"places": parse.places + tuple(place for place in enrichment.places
                                            if place not in parse.places)}
    if enrichment.type and rules.type_of(parse) is None:
        added[FLAGS[enrichment.type]] = True
    return dataclasses.replace(parse, **added)


SYSTEM = (
    "You classify short Ukrainian air-threat monitoring messages about Kyiv. "
    "Answer with one JSON object and nothing else: "
    '{"type": "drone" | "missile" | "ballistic" | null, "places": [Ukrainian place '
    'names the message reports a threat over]}. '
    "`drone` covers Shahed/reactive UAVs, `missile` cruise and hypersonic ones, "
    "`ballistic` ballistic ones. Use null when the message names no threat type. "
    "List only places the message itself names. Answer with JSON, never prose.")


DRAFT_SYSTEM = (
    "You write channel profiles for a Ukrainian air-threat monitoring agent. "
    "You are shown one Telegram channel's recent messages and must describe how that "
    "channel writes, as one JSON object and nothing else. Answer with JSON, never "
    "prose. Every regex is Python `re`, case-insensitive, matched against the whole "
    "message.")


class Client:
    """One interface for both providers: `enrich` is the whole of it.

    Adapters implement `complete(prompt, timeout, system) -> str` and nothing else,
    so the fail-open, the prompts and the answer parsing are written once and are
    identical whichever provider the household configured. Both callers -- the live
    `enrich` and `add-channel`'s offline `draft` -- go through that one method; the
    only thing that differs is the system prompt and the budget.
    """

    def prompt(self, message):
        text = " ".join(message.text.split())
        return (f"Channel: @{message.channel}\nMessage: {text}\n"
                "What threat type and which places does it report?")

    def draft(self, prompt):
        """The model's profile draft for one channel, raw -- or None if it never came.

        `add-channel` only: the same client and the same transport as `enrich`, with
        the offline budget and the drafting system prompt. Fail-open like everything
        else here -- the coverage report has already been printed by the time this
        runs, and it is worth having on its own (SPEC story 26, #10 AC4).
        """
        try:
            return self.complete(prompt, DRAFT_TIMEOUT, DRAFT_SYSTEM)
        except Exception as error:      # noqa: BLE001 -- see `enrich`
            log.warning("llm profile draft skipped (%s)", type(error).__name__)
            return None

    def enrich(self, message):
        """The model's reading of one message, or None -- late, broken, or unusable.

        Nothing here may raise: the caller is the live alert path, and an LLM outage
        must cost the household nothing but the enrichment itself (SPEC story 37).
        """
        try:
            return read(self.complete(self.prompt(message), TIMEOUT))
        except Exception as error:      # noqa: BLE001 -- fail-open is the whole point
            # the type only: an API error's text can carry the request, and the request
            # carries the key. Nothing in this module ever logs `self.key`.
            log.warning("llm enrichment skipped (%s)", type(error).__name__)
            return None


class OpenAI(Client):
    """Any OpenAI-compatible `/chat/completions` endpoint: OpenRouter, Ollama, OpenAI.

    ponytail: stdlib urllib, like `notify.Ntfy` -- one POST does not need an SDK, and
    the household's only two HTTP calls now look the same.
    """

    def __init__(self, config):
        self.url = config["base_url"].rstrip("/") + "/chat/completions"
        self.model = config["model"]
        self.key = os.environ.get(config.get("api_key_env") or "OPENAI_API_KEY", "")

    def complete(self, prompt, timeout, system=SYSTEM):
        payload = {"model": self.model, "temperature": 0,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": prompt}]}
        request = urllib.request.Request(
            self.url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"} |
                    ({"Authorization": f"Bearer {self.key}"} if self.key else {}))
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)["choices"][0]["message"]["content"]


class Copilot(Client):
    """`github-copilot-sdk` behind the same contract (ADR 8).

    ponytail: the SDK is not installed here and its billing under AI Credits is
    unverified (ARCHITECTURE.md open question), so this is the thinnest adapter that
    can honestly exist -- one call, the same contract, and a loud failure at
    construction if the package is missing. The day someone runs it for real, the
    only thing that can be wrong is this one method's argument names -- `timeout=`
    included, which is why nothing here treats it as a real deadline.
    """

    def __init__(self, config):
        try:
            self.sdk = importlib.import_module(COPILOT_SDK)
        except ImportError as error:
            raise RuntimeError(
                f"llm provider `copilot` needs the `{COPILOT_SDK.replace('_', '-')}` "
                "package; install it or set llm.provider to `openai` or `none`"
            ) from error
        self.model = config["model"]
        self.client = self.sdk.Client()

    def complete(self, prompt, timeout, system=SYSTEM):
        return self.client.complete(model=self.model, system=system, prompt=prompt,
                                    timeout=timeout)


PROVIDERS = {"openai": OpenAI, "copilot": Copilot}


def client(config):
    """The provider named by the one config line, or None when there is no LLM.

    `none` is the default and the state this project is designed to run in: GitHub
    Models is retired and Copilot billing unverified, so the agent must be complete
    without any of this (ARCHITECTURE.md).
    """
    provider = (config or {}).get("provider") or "none"
    if provider == "none":
        return None
    if provider not in PROVIDERS:
        raise ValueError(f"llm.provider {provider!r} is not one of "
                         f"{('none', *PROVIDERS)}")
    return PROVIDERS[provider](config)

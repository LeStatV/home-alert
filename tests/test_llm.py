"""The LLM boundary: one interface, two adapters, and a merge that never lowers.

No network and no credentials here -- the transport is faked for both adapters, which
is the whole point of the contract: switching provider is a config line (SPEC 28).
"""
import contextlib
import json
import sys
import time
from datetime import datetime
from unittest import mock

import pytest
import yaml

from home_alert import events, llm, reader, rules, store
from home_alert.reader import Message
from harness import FIXTURES, ROOT, replay

MESSAGE = Message("AerisRimor", 1, datetime(2026, 8, 28, 0, 54, 16), None,
                  "Йде Виноградар на Антонов!")
ANSWER = '{"type": "drone", "places": ["Антонов", "Виноградар"]}'


def test_a_canned_answer_is_read_as_a_type_and_canonical_places():
    """The model answers in the channels' own Ukrainian; the gazetteer canonicalizes
    it, so an alias (`файна таун`) lands on the home set and a place outside Kyiv is
    dropped rather than invented into the geometry."""
    enriched = llm.read('{"type": "drone", "places": ["файна таун", "Ромни"]}')
    assert enriched == llm.Enrichment("drone", ("Антонов",))


def test_a_place_the_rules_missed_is_added_and_the_message_gets_its_type():
    """The whole point of enrichment: `Йде Виноградар на Антонов!` names no type the
    rules know, so it types nothing. The model says drone and names the two places."""
    parse = rules.classify("Йде Виноградар на Антонов!")
    assert rules.type_of(parse) is None
    merged = llm.merge(parse, llm.read(ANSWER))
    assert rules.type_of(merged) == "drone"
    assert merged.places == ("Виноградар", "Антонов")


def test_an_answer_never_lowers_what_the_rules_already_said():
    """A model that calls a ballistic launch a drone, drops the places and declares it
    over changes nothing: the rules verdict is the floor (SPEC story 29)."""
    parse = rules.classify("Балістика на Київ! Ціль")
    merged = llm.merge(parse, llm.Enrichment("drone", ()))
    assert merged == parse


def test_places_are_added_and_never_taken_away():
    """An answer that names fewer places than the message did leaves the message's own
    reading order intact and appends its own."""
    parse = rules.classify("Нивки")
    merged = llm.merge(parse, llm.Enrichment(None, ("Антонов",)))
    assert merged.places == ("Нивки", "Антонов")


def test_no_answer_at_all_is_the_rules_verdict_untouched():
    parse = rules.classify("Нивки")
    assert llm.merge(parse, None) is parse


# -- the contract both adapters answer to. The transport is faked for both: there are
# no credentials on this machine and a test must never reach a network.

CONFIG = {"provider": "openai", "base_url": "https://openrouter.ai/api/v1",
          "model": "meta-llama/llama-3.3-70b-instruct:free",
          "api_key_env": "OPENROUTER_API_KEY"}


class FakeUrlopen:
    """The OpenAI-compatible transport: one chat completion, or an error."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, request, timeout=None):
        self.calls.append({"prompt": json.loads(request.data)["messages"][-1]["content"],
                           "system": json.loads(request.data)["messages"][0]["content"],
                           "timeout": timeout, "request": request})
        if isinstance(self.answer, Exception):
            raise self.answer
        import io
        body = {"choices": [{"message": {"content": self.answer}}]}
        return contextlib.closing(io.BytesIO(json.dumps(body).encode()))


class FakeSDK:
    """The thinnest stand-in for `github-copilot-sdk`, which is not on this machine."""

    def __init__(self, answer):
        self.answer, self.calls = answer, []
        sdk = self

        class Client:
            def complete(self, model=None, system=None, prompt=None, timeout=None):
                sdk.calls.append({"prompt": prompt, "timeout": timeout,
                                  "system": system, "model": model})
                if isinstance(sdk.answer, Exception):
                    raise sdk.answer
                return sdk.answer

        self.Client = Client


@pytest.fixture(params=["openai", "copilot"])
def adapter(request, monkeypatch):
    """A client of one provider, with its transport faked: `make(answer)` returns the
    client and the list of calls its transport recorded."""
    provider = request.param

    def make(answer):
        config = CONFIG | {"provider": provider}
        if provider == "openai":
            fake = FakeUrlopen(answer)
            monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
        else:
            fake = FakeSDK(answer)
            monkeypatch.setitem(sys.modules, llm.COPILOT_SDK, fake)
        return llm.client(config), fake.calls

    return make


def test_both_adapters_read_the_same_answer_the_same_way(adapter):
    """Switching provider is a config line and nothing else (SPEC story 28): the same
    canned answer becomes the same enrichment through either transport."""
    client, calls = adapter(ANSWER)
    # the answer's own order, which for a chain of places is the order it was flown
    assert client.enrich(MESSAGE) == llm.Enrichment("drone", ("Антонов", "Виноградар"))
    assert len(calls) == 1
    assert MESSAGE.text in calls[0]["prompt"] and MESSAGE.channel in calls[0]["prompt"]
    assert calls[0]["timeout"] == 3.0


def test_the_offline_draft_call_is_the_same_client_with_its_own_budget(adapter):
    """`add-channel` drafting is not the alert path: 3 s is the live budget (SPEC
    story 29), and drafting a profile out of 500 messages is allowed to take a
    minute. One client, one transport, one different system prompt -- adding a
    channel must never mean configuring a second provider."""
    client, calls = adapter('{"noise_patterns": []}')
    assert client.draft("Draft a profile for @kyiv_nebo") == '{"noise_patterns": []}'
    assert calls[0]["timeout"] == llm.DRAFT_TIMEOUT == 60.0
    assert calls[0]["system"] != llm.SYSTEM and "profile" in calls[0]["system"].lower()


def test_a_draft_call_that_fails_costs_the_draft_and_nothing_else(adapter):
    """Same fail-open as `enrich`, for the same reason: the coverage report has
    already been printed and it is worth having on its own (#10 AC4)."""
    client, _ = adapter(TimeoutError("timed out"))
    assert client.draft("Draft a profile") is None


def test_both_adapters_fail_open_when_the_provider_is_unreachable(adapter):
    """The provider is down, rate-limited or past its 3 s: `enrich` says nothing and
    the rules verdict stands (SPEC story 29, story 37)."""
    client, _ = adapter(TimeoutError("timed out"))
    assert client.enrich(MESSAGE) is None


def test_both_adapters_fail_open_on_garbage(adapter):
    """Models answer with prose, half a JSON object, or an apology."""
    client, _ = adapter("Sorry, I cannot help with that.")
    assert client.enrich(MESSAGE) is None
    client, _ = adapter('{"type": "drone", "places": [')
    assert client.enrich(MESSAGE) is None


def test_no_llm_is_the_default_and_constructs_nothing():
    """The shipped config says `none` and the design assumes the LLM may be absent
    (ARCHITECTURE.md): no stanza, no provider, no client, no import."""
    assert llm.client(None) is None
    assert llm.client({}) is None
    assert llm.client({"provider": "none"}) is None
    with pytest.raises(ValueError):
        llm.client({"provider": "gpt5-please"})


def test_the_copilot_adapter_says_what_is_missing_instead_of_failing_at_call_time():
    """`github-copilot-sdk` is not on this machine. Construction is where the owner
    finds that out -- not the first message of a raid."""
    with mock.patch.dict(sys.modules, {llm.COPILOT_SDK: None}):
        with pytest.raises(RuntimeError, match="github-copilot-sdk"):
            llm.client(CONFIG | {"provider": "copilot"})


def test_the_api_key_comes_from_the_named_env_var_and_never_from_the_config(monkeypatch):
    """Secrets stay in the environment (SPEC "secrets via environment"), the config
    only names the variable -- and the key never reaches the prompt or a log line."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    fake = FakeUrlopen(ANSWER)
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    client = llm.client(CONFIG)
    client.enrich(MESSAGE)
    request = fake.calls[0]["request"]
    assert request.headers["Authorization"] == "Bearer sk-secret"
    assert "sk-secret" not in fake.calls[0]["prompt"]
    assert "sk-secret" not in request.data.decode()


# -- the pipeline hook, at seam 1: fixture in at the reader boundary, pushes out at
# the sink. The provider is a fake transport under the real `llm.Client`, so the
# fail-open under test is the one that ships.


class FakeProvider(llm.Client):
    """A canned provider: one answer for every message, or an error, or a slow one.

    It is a `Client` and not a mock of one -- the prompt, the JSON reading and the
    fail-open are the shipped code, and only the transport is fake.
    """

    def __init__(self, answer, log=None, delay=0.0):
        self.answer, self.log, self.delay = answer, log if log is not None else [], delay

    def complete(self, prompt, timeout):
        self.log.append(("llm", prompt.splitlines()[1]))
        if self.delay:
            time.sleep(self.delay)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer(prompt) if callable(self.answer) else self.answer


def run(fixture, provider=None, log=None):
    """The fixture through the pipeline with this provider; the push tuples out."""
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["profiles"] = ROOT / "profiles"
    pushes = []

    def sink(push):
        pushes.append(push)
        if log is not None:
            log.append(("push", push.kind, push.tier, push.title))

    events.replay(reader.read_corpus(FIXTURES / f"{fixture}.jsonl"), config, sink,
                  store.Store(":memory:"), enricher=provider)
    return [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title) for p in pushes]


FIXTURE_NAMES = sorted(path.stem for path in FIXTURES.glob("*.jsonl"))


@pytest.mark.parametrize("fixture", FIXTURE_NAMES)
def test_a_provider_that_is_down_changes_no_scenario_at_all(fixture):
    """SPEC story 37 and the seam-1 degradation case, over every scenario there is:
    the provider raises on every call and the household is sent exactly what the
    rules alone would have sent, at exactly the same times."""
    assert run(fixture, FakeProvider(TimeoutError("timed out"))) == replay(fixture)


def test_a_slow_provider_delays_nothing_and_changes_nothing():
    """The 21 Aug ballistic slice against a provider that takes its time and then
    does not answer -- which is what a 3 s budget running out looks like from here.
    Same sequence, same timings: the launch path never asked it anything anyway."""
    assert run("2026-08-21T21-54_22-06",
               FakeProvider(TimeoutError("timed out"), delay=0.01)) \
        == replay("2026-08-21T21-54_22-06")


def test_a_launch_is_pushed_without_the_provider_ever_being_asked():
    """SPEC story 32: a launch is rules and ntfy, nothing else. The cold burst is four
    launch calls and three URGENT pushes -- and not one provider call before, between
    or after them."""
    log = []
    pushes = run("synthetic-cold-launch-burst", FakeProvider(ANSWER, log=log), log=log)
    assert pushes == replay("synthetic-cold-launch-burst")
    assert log == [("push", "NEW", "URGENT", "БАЛІСТИКА на Київ"),
                   ("push", "UPDATE", "URGENT", "БАЛІСТИКА на Київ"),
                   ("push", "NEW", "URGENT", "БАЛІСТИКА на Київ")]


def test_a_canned_answer_raises_an_unparsed_message_to_the_drone_tier():
    """SYNTHETIC fixture. `Знову над нами кружляє.` names no type and no place the
    gazetteer knows, so the rules push nothing at all. The model reads it as a drone
    over Антонов; war_monitor is w=0.9, so that is the tier the rules would have given
    the same report -- URGENT, over the home set.

    The second line is the check on the other side: a bare `Оболонь.` from the same
    channel 30 s later pushes nothing. The model's verdict enriched one message; it
    never entered the channel's 3-minute type memory, where it would have retyped
    every bare place name that followed.
    """
    assert run("synthetic-llm-types-an-unparsed-report") == []
    model = FakeProvider(lambda prompt: '{"type": "drone", "places": ["Антонов"]}'
                         if "кружляє" in prompt else '{"type": null, "places": ["Оболонь"]}')
    assert run("synthetic-llm-types-an-unparsed-report", model) == [
        ("00:54:16", "NEW", "URGENT", "БпЛА НАД ДОМОМ")]

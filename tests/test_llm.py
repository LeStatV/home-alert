"""The LLM boundary: one interface, two adapters, and a merge that never lowers.

No network and no credentials here -- the transport is faked for both adapters, which
is the whole point of the contract: switching provider is a config line (SPEC 28).
"""
import contextlib
import json
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

from home_alert import llm, rules
from home_alert.reader import Message

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
                sdk.calls.append({"prompt": prompt, "timeout": timeout, "model": model})
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
    parse = rules.classify(MESSAGE.text)
    # the answer's own order, which for a chain of places is the order it was flown
    assert client.enrich(MESSAGE, parse) == llm.Enrichment("drone",
                                                           ("Антонов", "Виноградар"))
    assert len(calls) == 1
    assert MESSAGE.text in calls[0]["prompt"] and MESSAGE.channel in calls[0]["prompt"]
    assert calls[0]["timeout"] == 3.0


def test_both_adapters_fail_open_when_the_provider_is_unreachable(adapter):
    """The provider is down, rate-limited or past its 3 s: `enrich` says nothing and
    the rules verdict stands (SPEC story 29, story 37)."""
    client, _ = adapter(TimeoutError("timed out"))
    assert client.enrich(MESSAGE, rules.classify(MESSAGE.text)) is None


def test_both_adapters_fail_open_on_garbage(adapter):
    """Models answer with prose, half a JSON object, or an apology."""
    client, _ = adapter("Sorry, I cannot help with that.")
    assert client.enrich(MESSAGE, rules.classify(MESSAGE.text)) is None
    client, _ = adapter('{"type": "drone", "places": [')
    assert client.enrich(MESSAGE, rules.classify(MESSAGE.text)) is None


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
    client.enrich(MESSAGE, rules.classify(MESSAGE.text))
    request = fake.calls[0]["request"]
    assert request.headers["Authorization"] == "Bearer sk-secret"
    assert "sk-secret" not in fake.calls[0]["prompt"]
    assert "sk-secret" not in request.data.decode()

"""The LLM boundary: one interface, one adapter, and a merge that never lowers.

No network and no credentials here -- the transport is faked, which is the whole point
of the contract: switching provider is a config line (SPEC 28).
"""
import contextlib
import json
import time
import urllib.error
from datetime import datetime

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


# -- the contract every adapter answers to. The transport is faked: there are no
# credentials on this machine and a test must never reach a network.

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


@pytest.fixture
def adapter(monkeypatch):
    """A client with its transport faked: `make(answer)` returns the client and the
    list of calls its transport recorded.

    The startup probe (`llm.probe`) has already run and its call is cleared, so every
    assertion below counts the calls the *household* caused, not the one construction
    costs (#24).
    """

    def make(answer):
        fake = FakeUrlopen(answer)
        monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
        client = llm.client(CONFIG)
        fake.calls.clear()
        return client, fake.calls

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


# -- a selected provider that cannot be called at all is loud at startup (#24). One
# that is merely slow, rate-limited or down still fail-opens per call, as it must.


class FakeProviderClass(llm.Client):
    """A provider whose one call raises whatever the test named. Registered in
    `PROVIDERS`, so it is `llm.client` and `llm.probe` under test, not a mock."""

    error = None

    def __init__(self, config):
        self.calls = []

    def complete(self, prompt, timeout, system=llm.SYSTEM):
        self.calls.append(prompt)
        if self.error:
            raise self.error
        return ANSWER


@pytest.fixture
def fake_provider(monkeypatch):
    def register(error):
        monkeypatch.setitem(llm.PROVIDERS, "fake",
                            type("Fake", (FakeProviderClass,), {"error": error}))
        return CONFIG | {"provider": "fake"}

    return register


def http(code):
    return urllib.error.HTTPError("https://x", code, "", {}, None)


@pytest.mark.parametrize("error", [
    TypeError("complete() got an unexpected keyword argument 'system'"),
    AttributeError("'module' object has no attribute 'Client'"),
    KeyError("choices"),
    IndexError("list index out of range"),
    http(401),
    http(403),
    http(404),
    http(400),
])
def test_a_provider_that_cannot_be_called_at_all_fails_at_startup(fake_provider, error):
    """The asymmetry #24 is about: a wrong signature or a bad key used to be caught by
    the per-call fail-open, so a household that had configured a provider ran exactly
    as `provider: none` runs, with one WARNING a night to say so. Construction is
    where the owner finds out now -- not the first message of a raid."""
    with pytest.raises(RuntimeError, match="llm provider 'fake'"):
        llm.client(fake_provider(error))


@pytest.mark.parametrize("error", [
    TimeoutError("timed out"),
    urllib.error.URLError("connection refused"),
    http(429),
    http(500),
    http(503),
])
def test_a_provider_that_is_merely_slow_or_down_still_constructs(fake_provider, error):
    """The other half of the same criterion: a provider past its budget, over its rate
    limit or having an outage is a runtime condition, and the household must not be
    left without a notifier because a free tier is busy. It constructs, and every call
    fail-opens exactly as before (SPEC story 37)."""
    client = llm.client(fake_provider(error))
    assert client.enrich(MESSAGE) is None


def test_the_probe_is_one_call_and_never_reaches_the_household(fake_provider):
    """Startup costs one request, and its answer is not a verdict about anything: the
    probe asks whether the provider answers, not what it thinks."""
    client = llm.client(fake_provider(None))
    assert client.calls == [llm.PROBE]


def test_the_copilot_provider_is_gone_and_says_so(monkeypatch):
    """`github-copilot-sdk` is real and is GitHub's, but it is an async agentic-session
    driver over a downloaded CLI runtime, not a completion API -- and it bills one
    premium request per prompt (300/month on Pro, tighter than the OpenRouter free
    tier this is gated for). Removed rather than left as a plausible dead option
    (#24). An old config naming it gets the same error as any other unknown provider,
    at startup."""
    with pytest.raises(ValueError, match="copilot"):
        llm.client(CONFIG | {"provider": "copilot"})


def test_the_api_key_comes_from_the_named_env_var_and_never_from_the_config(monkeypatch):
    """Secrets stay in the environment (SPEC "secrets via environment"), the config
    only names the variable -- and the key never reaches the prompt or a log line."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    fake = FakeUrlopen(ANSWER)
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake)
    client = llm.client(CONFIG)
    client.enrich(MESSAGE)
    # calls[0] is the startup probe; calls[1] is the message the household caused
    assert [call["prompt"] for call in fake.calls] == [llm.PROBE, client.prompt(MESSAGE)]
    request = fake.calls[1]["request"]
    assert request.headers["Authorization"] == "Bearer sk-secret"
    assert "sk-secret" not in fake.calls[1]["prompt"]
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
    config = yaml.safe_load((ROOT / "config.example.yaml").read_text())
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


# -- the other half of "loud at startup": who actually hears it. The agent runs under
# `restart: unless-stopped`, so a raise alone is a crash loop nobody is told about.


@pytest.mark.parametrize("error, clue", [
    # the probe's own verdict: a key that expired since the last deploy
    (RuntimeError("llm provider 'openai' answered HTTP 401 on its first call"), "401"),
    # a config still naming the provider #24 removed -- the one stale config this
    # change itself creates, and it does not raise `RuntimeError`
    (ValueError("llm.provider 'copilot' is not one of ('none', 'openai')"), "copilot"),
    # a stanza missing a key the adapter needs
    (KeyError("base_url"), "base_url"),
])
def test_a_provider_that_stops_the_agent_is_pushed_before_the_process_dies(
        monkeypatch, tmp_path, error, clue):
    """A provider that cannot be constructed fails the start at 3am. Without this, the
    household gets a restart loop and a docker log; with it, the owner's `system` topic
    says so -- and the process still dies, so the exit code stays honest."""
    from types import SimpleNamespace
    from home_alert import cli, notify

    recorder = notify.Recorder()
    settings = yaml.safe_load((ROOT / "config.example.yaml").read_text())
    settings["profiles"] = ROOT / "profiles"
    monkeypatch.setattr(cli, "sink_for", lambda config, ntfy: recorder)
    monkeypatch.setattr(llm, "client", lambda config: (_ for _ in ()).throw(error))

    with pytest.raises(type(error)):
        cli.run(SimpleNamespace(db=str(tmp_path / "x.db")), settings)

    assert [(push.topic, push.title, clue in push.body) for push in recorder.pushes] \
        == [(notify.SYSTEM_TOPIC, "Агент не стартував", True)]

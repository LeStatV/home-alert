"""Seam: a live Telethon update, normalized, is the replayer's `Message` and enters
the same pipeline. Fixture slice in through a fake client, ntfy pushes out."""
import asyncio
from datetime import datetime, timezone

import pytest
import yaml

from home_alert import events, notify, profiles, reader, store
from fake_telegram import FakeClient, feed
from harness import FIXTURES, ROOT, replay

BALLISTIC = "2026-08-21T21-54_22-06"


def config():
    loaded = yaml.safe_load((ROOT / "config.yaml").read_text())
    loaded["profiles"] = ROOT / "profiles"
    return loaded


def live(fixture, db=":memory:"):
    """The fixture fed live through a fake client; returns (pushes, store)."""
    messages = reader.read_corpus(FIXTURES / f"{fixture}.jsonl")
    channels = sorted(profiles.load(ROOT / "profiles"))
    recorder, saved = notify.Recorder(), store.Store(db)
    pipeline = events.Pipeline(config(), recorder, saved)
    client = FakeClient(channels)

    async def run():
        await reader.subscribe(client, channels, pipeline.feed)
        await feed(client, messages)

    asyncio.run(run())
    return recorder.pushes, saved


def test_live_slice_pushes_exactly_what_the_replay_pushes():
    """The 21 Aug ballistic slice, fed live one update at a time, produces the
    push sequence the replayer produces from the same rows."""
    pushes, _ = live(BALLISTIC)
    assert [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title) for p in pushes] \
        == replay(BALLISTIC)


def test_live_messages_land_in_the_store_with_reply_to():
    """Every message the reader hands over is stored, chain and all -- the audit
    trail `replay` re-runs is built from these rows."""
    _, saved = live(BALLISTIC)
    rows = saved.db.execute(
        "select channel, msg_id, reply_to, edited from messages "
        "where channel = 'Ukrainian_Intelligence' and msg_id in (144843, 144844)"
    ).fetchall()
    assert rows == [("Ukrainian_Intelligence", 144843, 144838, 0),
                    ("Ukrainian_Intelligence", 144844, None, 0)]


def test_an_edit_is_recorded_and_never_resounds_the_event():
    """SPEC alerts on posts, not on corrections: the edit updates text and raises the
    flag, the parse the rules actually ran on survives, and nothing is pushed."""
    messages = reader.read_corpus(FIXTURES / f"{BALLISTIC}.jsonl")
    launch = next(m for m in messages if m.id == 144844)
    channels = sorted(profiles.load(ROOT / "profiles"))
    recorder, saved = notify.Recorder(), store.Store(":memory:")
    pipeline = events.Pipeline(config(), recorder, saved)
    client = FakeClient(channels)

    async def run():
        await reader.subscribe(client, channels, pipeline.feed)
        await client.fire(launch.channel, launch)
        before = len(recorder.pushes)
        await client.fire(launch.channel, reader.Message(
            launch.channel, launch.id, launch.time, launch.reply_to, "‼️ Загроза балістики з Курська (уточнено)"),
            edit_date=datetime(2026, 8, 21, 21, 57, tzinfo=timezone.utc))
        return before

    before = asyncio.run(run())
    assert len(recorder.pushes) == before, "an edit must not push"
    text, edited, parse = saved.db.execute(
        "select text, edited, parse from messages where msg_id = ?", (launch.id,)).fetchone()
    assert edited == 1 and text.endswith("(уточнено)") and parse, parse


def test_a_channel_the_account_has_not_joined_is_logged_not_fatal(caplog):
    """Telegram pushes updates only for joined dialogs. Five channels must keep
    working while the sixth is logged for the owner to go and join."""
    channels = sorted(profiles.load(ROOT / "profiles"))
    recorder = notify.Recorder()
    pipeline = events.Pipeline(config(), recorder, None)
    client = FakeClient(channels, joined=[c for c in channels if c != "kpszsu"])
    messages = reader.read_corpus(FIXTURES / f"{BALLISTIC}.jsonl")

    async def run():
        with caplog.at_level("INFO"):
            await reader.subscribe(client, channels, pipeline.feed)
        await feed(client, messages)

    asyncio.run(run())
    assert "kpszsu: not joined" in caplog.text
    assert [(f"{p.time:%H:%M:%S}", p.kind, p.tier, p.title) for p in recorder.pushes] \
        == replay(BALLISTIC)


def test_a_disconnect_reconnects_and_says_so(caplog):
    """Telethon gives up eventually; the agent must not."""
    class Flaky(FakeClient):
        async def run_until_disconnected(self):
            await super().run_until_disconnected()
            if self.disconnects > 2:
                raise SystemExit

    client = Flaky(["war_monitor"])
    with caplog.at_level("WARNING"), pytest.raises(SystemExit):
        asyncio.run(reader.run(client, ["war_monitor"], lambda m: None, retry_sec=0))
    assert client.connects == 2, "reconnected once per disconnect"
    assert caplog.text.count("reconnecting") == 2

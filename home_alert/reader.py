"""Message input. v1 reads a JSONL corpus; Telethon will plug in here later."""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Message:
    channel: str
    id: int
    time: datetime          # naive UTC -- replay uses it as the clock
    reply_to: int | None
    text: str


def read_corpus(path, start=None, end=None):
    """Messages from a corpus in time order.

    `path` is either a directory of `<channel>.jsonl` (the research corpus, where
    the channel is the filename) or a single merged `.jsonl` whose rows carry a
    `channel` field (a test fixture). Rows without a date are skipped.
    """
    path = Path(path)
    files = sorted(path.glob("*.jsonl")) if path.is_dir() else [path]
    messages = []
    for file in files:
        for line in file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("date"):
                continue
            time = datetime.fromisoformat(row["date"]).astimezone(timezone.utc).replace(tzinfo=None)
            if (start and time < start) or (end and time > end):
                continue
            messages.append(Message(row.get("channel") or file.stem, row["id"], time,
                                    row.get("reply_to"), row.get("text") or ""))
    messages.sort(key=lambda m: (m.time, m.channel, m.id))
    return messages

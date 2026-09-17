"""Runtime settings you can change from Discord (persisted to settings.json).

Seeded from config/.env on first run; the slash commands (/fly watch, /fly vc)
write here so your choices survive a restart without editing files."""

from __future__ import annotations

import json
import threading
from pathlib import Path


class Settings:
    def __init__(self, path: Path, watch_channel_id: int = 0, voice_channel_id: int = 0):
        self.path = Path(path)
        self.watch_channel_id = watch_channel_id
        self.voice_channel_id = voice_channel_id
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.watch_channel_id = int(data.get("watch_channel_id", self.watch_channel_id))
            self.voice_channel_id = int(data.get("voice_channel_id", self.voice_channel_id))
        except Exception:
            pass  # no file yet, or unreadable -> keep the seeded defaults

    def save(self) -> None:
        with self._lock:
            self.path.write_text(json.dumps({
                "watch_channel_id": self.watch_channel_id,
                "voice_channel_id": self.voice_channel_id,
            }, indent=2), encoding="utf-8")

    def set_watch(self, channel_id: int) -> None:
        self.watch_channel_id = int(channel_id); self.save()

    def set_voice(self, channel_id: int) -> None:
        self.voice_channel_id = int(channel_id); self.save()

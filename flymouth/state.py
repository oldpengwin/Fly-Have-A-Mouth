"""Shared world state — the single source of truth the browser renders.

The controller (fly brain) mutates this; the web server serialises it and pushes
it to every connected browser. The flying is vanity; the fields below are the
real thing (buffer, words, mood, and the live motor-pool activity)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class WorldState:
    mode: str = "idle"                      # idle | typing | eating | poked
    message: str = "waiting for a ping..."
    brain_label: str = ""                   # which brain source is driving

    buffer: str = ""                        # current candidate the fly is building
    last_key: Optional[str] = None          # last key struck
    target_key: Optional[str] = None        # key the fly is flying at
    just_wiped: bool = False
    
    # For animation-synced keystrokes: pending_letter/target hold the next key
    # until the fly animation reaches it (so letter appears AFTER fly hits)
    pending_letter: Optional[str] = None
    pending_target: Optional[int] = None

    completed_words: List[str] = field(default_factory=list)
    words_done: int = 0
    words_total: int = 0
    word_target_len: int = 0                # this word's random target length

    requester: Optional[str] = None
    queue_len: int = 0

    mood: float = 0.6                       # 0 distressed .. 1 happy
    bowl: float = 0.0                       # food level 0..1
    poke_flash: float = 0.0

    # live neural read-out: 26 values (a..z), the motor-pool activity that chose
    # the last key. Lets the viewer show the fly's real brain output.
    pool_activity: List[float] = field(default_factory=lambda: [0.0] * 26)
    # live raster: per-neuron spike counts this window, grouped into the 26 key
    # pools (26 lists of ~15 leg motor neurons). The viewer flashes real spikes.
    neuro_cols: List[List[int]] = field(default_factory=list)
    neuro_rate: float = 0.0                 # motor spikes read this window

    seq: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

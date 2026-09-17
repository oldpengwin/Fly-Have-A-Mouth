"""Turn the fly's real motor-neuron spikes into keystrokes.

The connectome has 381 leg motor neurons (build/motor_map.json, Stage 0). Their
firing is the only motor output we read. We partition them, deterministically,
into 26 pools -- one per letter a..z -- and each decision tick the pool that
spiked most in the window wins and its letter is struck. That is the whole
"fixed arithmetic" from wiring to keyboard, in the spirit of therealfly's
coupling (a pool's firing rate becomes an actuator command; here it becomes a
key).

MEASURED: which connectome neuron is a leg motor neuron, and its leg/side/joint
          (read from motor_map.json, which reads the annotations).
CHOSEN:   the ordering (leg T1<T2<T3, side L<R, joint, then connectome index)
          and the contiguous split into 26 equal pools; the min-spike gate; the
          argmax + lowest-pool tie-break. None of it is tuned to an outcome --
          the map is a pure function of motor_map.json and the constants here.

This does NOT claim the fly "wants" to type a word. It claims: real spikes of
real motor neurons, under a fixed rule, choose the keys. Legibility is judged
separately by the dictionary.
"""

from __future__ import annotations

import json
import string
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

LETTERS = string.ascii_lowercase   # 26 pools

# joint ordering so a pool is a contiguous, meaningful band of the leg
_JOINT_ORDER = {
    "thorax-coxa": 0, "coxa-trochanter": 1, "trochanter-femur": 2,
    "femur-tibia": 3, "tibia-tarsus": 4, "pretarsus (long tendon)": 5, None: 9,
}
_LEG_ORDER = {"T1": 0, "T2": 1, "T3": 2, None: 9}
_SIDE_ORDER = {"L": 0, "R": 1, None: 9}


class MotorReadout:
    def __init__(self, motor_map_path: Path, min_spikes: int = 1,
                 mode: str = "sample", temperature: float = 0.6,
                 baseline_alpha: float = 0.05, seed: int = 0):
        self.mode = mode                    # "sample" (default) or "argmax"
        self.temperature = max(1e-3, temperature)
        self.baseline_alpha = baseline_alpha
        self._rng = np.random.default_rng(seed)
        doc = json.loads(Path(motor_map_path).read_text(encoding="utf-8"))
        legs = [e for e in doc["motor_neurons"] if e["class"] == "leg"]
        legs.sort(key=lambda e: (
            _LEG_ORDER.get(e["leg"], 9),
            _SIDE_ORDER.get(e["side"], 9),
            _JOINT_ORDER.get(e["joint"], 9),
            e["index"],
        ))
        self.min_spikes = min_spikes
        self.n_pools = len(LETTERS)
        # contiguous split into 26 pools
        self.pools: List[np.ndarray] = []
        self.pool_of_index: Dict[int, int] = {}
        chunks = np.array_split(np.arange(len(legs)), self.n_pools)
        for pid, chunk in enumerate(chunks):
            idxs = np.array([legs[i]["index"] for i in chunk], dtype=np.int64)
            self.pools.append(idxs)
            for ix in idxs:
                self.pool_of_index[int(ix)] = pid
        # every leg-MN connectome index we care about (for fast masking)
        self.motor_indices = np.array(sorted(self.pool_of_index), dtype=np.int64)
        # running per-pool baseline so no single anatomical hotspot dominates:
        # what wins is the pool firing ABOVE its own recent average.
        self._baseline = np.ones(self.n_pools, dtype=np.float64)
        self.last_weights = np.ones(self.n_pools) / self.n_pools
        self.last_counts = np.zeros(self.n_pools, dtype=np.int64)

    def reset(self) -> None:
        self._baseline[:] = 1.0

    def pool_letters(self) -> List[str]:
        return list(LETTERS)

    def pool_neuron_counts(self, counts: Dict[int, int]) -> List[List[int]]:
        """Per-neuron spike counts, grouped into the 26 pools (for the live
        raster). Returns 26 lists; entry j of pool p is that neuron's spikes."""
        return [[int(counts.get(int(ix), 0)) for ix in pool] for pool in self.pools]

    def pool_layout(self) -> List[int]:
        """Neuron count in each of the 26 pools (so the viewer can lay out the
        raster before any spikes arrive)."""
        return [len(p) for p in self.pools]

    def pool_counts(self, counts: Dict[int, int]) -> np.ndarray:
        """Sum a {neuron_index: spike_count} dict into 26 per-letter totals."""
        out = np.zeros(self.n_pools, dtype=np.int64)
        for idx, c in counts.items():
            pid = self.pool_of_index.get(int(idx))
            if pid is not None:
                out[pid] += c
        return out

    def decide(self, counts: Dict[int, int]) -> Tuple[Optional[str], np.ndarray]:
        """One keystroke from one window of motor spikes.

        Returns (letter or None, 26-vector of pool spike counts). None means the
        motor output was too quiet this tick -- the fly hovered, no key struck.
        Otherwise each pool's firing relative to its own running baseline forms a
        distribution over the 26 keys; we sample it (or take the argmax)."""
        pc = self.pool_counts(counts)
        self.last_counts = pc
        if int(pc.sum()) < self.min_spikes:
            return None, pc
        a = self.baseline_alpha
        self._baseline = (1 - a) * self._baseline + a * pc
        rel = pc / (self._baseline + 1.0)          # relative to own baseline
        z = rel - rel.mean()
        w = np.exp(z / self.temperature)
        w = w / w.sum()
        self.last_weights = w
        if self.mode == "argmax":
            pid = int(w.argmax())
        else:
            pid = int(self._rng.choice(self.n_pools, p=w))
        return LETTERS[pid], pc

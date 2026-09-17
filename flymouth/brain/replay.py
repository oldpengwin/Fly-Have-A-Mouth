"""ReplayBrain: stream real recorded connectome spikes from cord_spikes.npz.

The file holds, per condition/seed, the step index and neuron index of every
recorded spike from therealfly's Stage-1 runs (real flysim over the real
connectome). We replay one condition's motor spikes as a continuous stream,
looping when it ends, so the fly can "type" indefinitely from real data with no
2.5 GB graph and no GPU.

When the fly is not being driven (idle between requests), we emit nothing --
the recorded warm-up window is silent anyway, matching the real model's lack of
spontaneous activity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

from .base import BrainSource


class ReplayBrain(BrainSource):
    def __init__(self, spikes_path: Path, condition: str = "DRIVE", seed: int = 0):
        z = np.load(Path(spikes_path), allow_pickle=False)
        key = f"{condition}__s{seed}"
        steps = z[f"{key}__steps"].astype(np.int64)
        neurons = z[f"{key}__neurons"].astype(np.int64)
        # re-base so the first recorded step is 0, and remember the span to loop
        if len(steps):
            base = steps.min()
            steps = steps - base
            self.span = int(steps.max()) + 1
        else:
            self.span = 1
        order = np.argsort(steps, kind="stable")
        self._steps = steps[order]
        self._neurons = neurons[order]
        self._cursor = 0.0          # brain-time position within the loop
        self._driving = False
        self.condition = condition
        self.seed = seed

    def set_driving(self, driving: bool) -> None:
        self._driving = driving

    def step_window(self, n_steps: int) -> Dict[int, int]:
        if not self._driving:
            # advance the clock but stay silent while idle
            self._cursor = (self._cursor + n_steps) % self.span
            return {}
        counts: Dict[int, int] = {}
        remaining = n_steps
        while remaining > 0:
            start = self._cursor
            take = min(remaining, self.span - start)
            lo = np.searchsorted(self._steps, start, side="left")
            hi = np.searchsorted(self._steps, start + take, side="left")
            for nix in self._neurons[lo:hi]:
                counts[int(nix)] = counts.get(int(nix), 0) + 1
            self._cursor += take
            if self._cursor >= self.span:
                self._cursor = 0.0
            remaining -= take
        return counts

    @property
    def label(self) -> str:
        return f"ReplayBrain(real recorded spikes: {self.condition} seed {self.seed})"

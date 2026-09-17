"""LiveBrain: run the real flysim LIF brain over the connectome, live.

This is the full "brain in the loop": while the fly is being asked to type, the
descending command neurons are driven with Poisson input and the whole 165,122
neuron network is integrated forward; the leg motor neurons' spikes are read out
into keystrokes by MotorReadout.

Requires the sibling flybrain checkout (flysim.py + build/graph.npz, ~2.5 GB,
>= 6 GB free RAM; a CUDA GPU via flysim's GPU path is far faster). See
setup/SETUP.md. If the graph or flysim is missing, construction raises and the
launcher falls back to ReplayBrain.

flysim API (as used by therealfly/cord/rhythm.py):
    fb = flysim.FlyBrain(graph_path)
    out = fb.run({tuple(indices): hz}, n_steps, state=prev_state, spike_log=True)
    out["_spikes"]  -> list[n_steps] of arrays of fired neuron indices
    out["_state"]   -> opaque state to chain the next run
    fb.types        -> str[n] cell type per neuron (for DN selection)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

from .base import BrainSource

# Descending neurons driven while typing. DNa01 + DNa02 are the forward-walking
# command set therealfly's Stage 1 used; driving them ignites the cord's motor
# output. CHOSEN, like the rest of the drive -- not a measured "type this" command.
DEFAULT_DRIVE_TYPES = ("DNa01", "DNa02")


class LiveBrain(BrainSource):
    def __init__(self, flybrain_root: Path, graph_path: Path,
                 motor_indices: Sequence[int],
                 drive_types: Sequence[str] = DEFAULT_DRIVE_TYPES,
                 drive_hz: float = 150.0, seed: int = 0):
        flybrain_root = Path(flybrain_root)
        graph_path = Path(graph_path)
        if not graph_path.exists():
            raise FileNotFoundError(f"connectome graph not found: {graph_path}")
        if str(flybrain_root) not in sys.path:
            sys.path.insert(0, str(flybrain_root))
        import flysim  # noqa: E402  (from the sibling checkout)
        self._fb = flysim.FlyBrain(str(graph_path))
        self._state = None
        self._driving = False
        self._seed = seed
        self._first = True
        self.drive_hz = drive_hz
        self.motor_index_set = set(int(i) for i in motor_indices)

        drive_idx: List[int] = []
        for t in drive_types:
            hits = np.flatnonzero(self._fb.types == t)
            if len(hits) == 0:
                raise KeyError(f"no neuron of type {t!r} in the graph")
            drive_idx.extend(int(i) for i in hits)
        self._drive_idx = tuple(sorted(set(drive_idx)))
        self.drive_types = tuple(drive_types)

    def set_driving(self, driving: bool) -> None:
        self._driving = driving

    def step_window(self, n_steps: int) -> Dict[int, int]:
        drive = {self._drive_idx: self.drive_hz} if self._driving else {}
        kw = {}
        if self._first:
            kw["seed"] = self._seed
            self._first = False
        out = self._fb.run(drive, n_steps, state=self._state, spike_log=True, **kw)
        self._state = out["_state"]
        counts: Dict[int, int] = {}
        for fired in out["_spikes"]:
            for nix in fired:
                ni = int(nix)
                if ni in self.motor_index_set:
                    counts[ni] = counts.get(ni, 0) + 1
        return counts

    @property
    def label(self) -> str:
        return f"LiveBrain(real flysim, drive={'+'.join(self.drive_types)}@{self.drive_hz:.0f}Hz)"

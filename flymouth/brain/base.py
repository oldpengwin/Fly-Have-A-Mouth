"""Common interface for a source of the fly's motor spikes.

A BrainSource advances an internal BRAIN clock (0.2 ms steps, like flysim) and,
each decision tick, reports how many times each recorded neuron fired in the
window. Two implementations:

  ReplayBrain -- streams real recorded connectome spikes (build/cord_spikes.npz).
                 Runs anywhere, no 2.5 GB graph, no GPU. Genuinely the fly's
                 spikes, just pre-recorded.
  LiveBrain   -- runs the real flysim LIF brain live over the connectome graph,
                 driving descending command neurons while the fly is "typing".

The controller only ever sees this interface, so the game is identical either
way; only how faithfully/expensively the spikes are produced changes.
"""

from __future__ import annotations

from typing import Dict


class BrainSource:
    #: brain-time this source has advanced, in 0.2 ms steps
    dt_ms: float = 0.2

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def set_driving(self, driving: bool) -> None:
        """True while a request is active (the command neurons are driven)."""
        ...

    def step_window(self, n_steps: int) -> Dict[int, int]:
        """Advance n_steps of brain time; return {neuron_index: spike_count}
        for the recorded motor neurons over that window."""
        raise NotImplementedError

    @property
    def label(self) -> str:
        return self.__class__.__name__

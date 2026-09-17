"""The game loop: the fly's brain drives the keyboard, the dictionary judges.

Runs in its own thread because the live brain (flysim) is blocking, CPU/GPU
heavy work. Communicates with the async Discord bot + web server through
thread-safe queues and the shared WorldState.

Per request (one Discord ping):
  1. RNG picks N in [MIN_WORDS, MAX_WORDS] words the fly must legibly type.
  2. Drive the command neurons; each decision tick, one window of real motor
     spikes -> one keystroke (MotorReadout).
        - buffer still a valid dictionary prefix -> keep bashing
        - buffer is a whole word                 -> reward, bank it, clear buffer
        - buffer is a dead end                   -> the fly hits CLEAR (wipe),
                                                    mild distress
  3. N words banked -> the bowl fills, the sentence goes back to Discord, the
     fly eats for a beat, then takes the next queued ping.
Only one request at a time; extra pings queue.
"""

from __future__ import annotations

import queue
import random
import threading
import time
from dataclasses import dataclass
from typing import Optional

from .brain.base import BrainSource
from .brain.readout import MotorReadout
from .dictionary import Dictionary
from .state import WorldState


@dataclass
class Request:
    requester: str
    requester_id: int
    channel_id: int


@dataclass
class Completion:
    requester: str
    requester_id: int
    channel_id: int
    sentence: str
    word_count: int


class MouthController:
    def __init__(self, brain: BrainSource, readout: MotorReadout,
                 dictionary: Dictionary, cfg, state: Optional[WorldState] = None):
        self.brain = brain
        self.readout = readout
        self.dict = dictionary
        self.cfg = cfg
        self.state = state or WorldState(mood=cfg.MOOD_START)
        self.state.brain_label = brain.label
        self.requests: "queue.Queue[Request]" = queue.Queue()
        self.completions: "queue.Queue[Completion]" = queue.Queue()
        self._busy = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.decision_steps = max(1, int(round(cfg.DECISION_MS / brain.dt_ms)))
        self._press_dt = 1.0 / max(0.05, cfg.PRESS_HZ)
        # empty raster layout so idle viewers see the neuron grid before spikes
        self.state.neuro_cols = [[0] * n for n in readout.pool_layout()]

    # ---- API used by the bot (async thread) -----------------------------
    def submit(self, req: Request) -> int:
        pos = self.requests.qsize() + (1 if self._busy else 0)
        self.requests.put(req)
        self.state.queue_len = self.requests.qsize()
        return pos

    def poke(self, who: str) -> None:
        self.state.poke_flash = 1.0
        self.state.mood = max(0.0, self.state.mood - 0.04)
        if self.state.mode == "idle":
            self.state.message = f"{who} tapped the glass!"
        self.state.seq += 1

    def is_busy(self) -> bool:
        return self._busy

    # ---- thread lifecycle ----------------------------------------------
    def start(self) -> None:
        self.brain.start()
        self._thread = threading.Thread(target=self._loop, name="mouth", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self.brain.stop()

    # ---- main loop ------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                req = self.requests.get(timeout=0.3)
            except queue.Empty:
                continue
            self._busy = True
            try:
                self._run_request(req)
            except Exception as e:  # never let one request kill the fly
                self.state.message = f"(the fly got confused: {e})"
                self.state.seq += 1
            self._busy = False
            self.state.queue_len = self.requests.qsize()

    def _run_request(self, req: Request) -> None:
        s, cfg = self.state, self.cfg
        n = random.randint(cfg.MIN_WORDS, cfg.MAX_WORDS)
        s.mode = "typing"; s.requester = req.requester
        s.words_total = n; s.words_done = 0
        s.completed_words = []; s.buffer = ""
        s.bowl = 0.0; s.mood = max(s.mood, cfg.MOOD_START)
        s.message = f"{req.requester} pinged! the fly must say {n} word(s)."
        s.seq += 1
        self.readout.reset()
        self.brain.set_driving(True)

        lengths = self.dict.available_target_lengths(cfg.WORD_LEN_MIN, cfg.WORD_LEN_MAX) or [cfg.MIN_WORD_LEN]
        next_press = time.monotonic()
        while s.words_done < n and not self._stop.is_set():
            # second randomiser: this word's target letter count
            target = random.choice(lengths)
            s.word_target_len = target
            s.buffer = ""
            s.message = (f"word {s.words_done + 1}/{n}: make a {target}-letter word"
                         + (("  " + " ".join(s.completed_words)) if s.completed_words else ""))
            s.seq += 1

            while not self._stop.is_set():
                counts = self.brain.step_window(self.decision_steps)  # real motor spikes
                letter, _pc = self.readout.decide(counts)
                s.pool_activity = [float(x) for x in self.readout.last_weights]
                s.neuro_cols = self.readout.pool_neuron_counts(counts)   # live raster
                s.neuro_rate = float(sum(counts.values()))

                now = time.monotonic()                 # throttle to PRESS_HZ wall-clock
                if now < next_press:
                    time.sleep(next_press - now)
                next_press = time.monotonic() + self._press_dt

                if letter is None:                     # motor output too quiet -> hover
                    s.just_wiped = False
                    s.seq += 1
                    continue
                if self._press(letter, target):        # True == this word is done
                    break

        self.brain.set_driving(False)
        if self._stop.is_set():
            return

        sentence = " ".join(s.completed_words)
        s.mode = "eating"; s.bowl = 1.0; s.mood = 1.0
        s.target_key = None
        s.message = f"fly says: “{sentence}” — nom nom \U0001F35A"
        s.seq += 1
        self.completions.put(Completion(req.requester, req.requester_id,
                                        req.channel_id, sentence, n))
        time.sleep(cfg.EAT_SECONDS)

        if self.requests.empty():
            s.mode = "idle"; s.requester = None
            s.words_total = 0; s.words_done = 0; s.buffer = ""
            s.target_key = None; s.message = "waiting for a ping..."
            s.seq += 1

    def _press(self, letter: str, target: int) -> bool:
        """Strike one key toward a legible word of exactly `target` letters.
        Returns True when the word is completed."""
        s, cfg = self.state, self.cfg
        s.just_wiped = False
        s.last_key = letter; s.target_key = letter
        s.buffer += letter
        s.mood = max(0.0, s.mood - cfg.MOOD_DECAY_PER_PRESS)

        if self.dict.is_word_of_len(s.buffer, target):
            s.completed_words.append(s.buffer)
            s.words_done += 1
            s.mood = min(1.0, s.mood + cfg.MOOD_WORD_REWARD)
            s.message = (f"legible! ({s.words_done}/{s.words_total})  "
                         + " ".join(s.completed_words))
            s.seq += 1
            return True
        if self.dict.can_reach_len(s.buffer, target):
            s.seq += 1
            return False
        # dead end (illegible, or can't reach the target length) -> CLEAR
        s.buffer = ""
        s.just_wiped = True
        s.mood = max(0.0, s.mood - cfg.MOOD_WIPE_PENALTY)
        s.seq += 1
        return False

"""Dictionary + legibility engine.

Two checks drive the game:
  is_prefix(buf) -> could this still become a real word? If not, the fly hits
                    CLEAR (wipes the buffer) -- "realises it messed up".
  is_word(buf)   -> is this exactly a legible word now? If so, reward + bank it.

We precompute every prefix of every word so both checks are O(1). The brain
chooses the letters; this only judges legibility.
"""

from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Set

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DEFAULT_WORDS = os.path.join(_DATA_DIR, "words.txt")


class Dictionary:
    def __init__(self, words: Iterable[str], min_word_len: int = 2):
        self.min_word_len = min_word_len
        self.words: Set[str] = set()
        self.prefixes: Set[str] = {""}
        # per-target-length views: to build a legible word of EXACTLY length T,
        # words_by_len[T] is the goal set and prefixes_by_len[T] the strings that
        # can still reach one (so the fly wipes the moment it can't).
        self.words_by_len: Dict[int, Set[str]] = {}
        self.prefixes_by_len: Dict[int, Set[str]] = {}
        for raw in words:
            w = raw.strip().lower()
            if not w or w.startswith("#") or not w.isalpha():
                continue
            self.words.add(w)
            self.words_by_len.setdefault(len(w), set()).add(w)
            pl = self.prefixes_by_len.setdefault(len(w), {""})
            for i in range(1, len(w) + 1):
                self.prefixes.add(w[:i])
                if i < len(w):
                    pl.add(w[:i])
        if not self.words:
            raise ValueError("Dictionary is empty -- check data/words.txt")

    @classmethod
    def load(cls, path: Optional[str] = None, min_word_len: int = 2) -> "Dictionary":
        with open(path or _DEFAULT_WORDS, "r", encoding="utf-8") as fh:
            return cls(fh.readlines(), min_word_len=min_word_len)

    def is_word(self, buf: str) -> bool:
        return len(buf) >= self.min_word_len and buf.lower() in self.words

    def is_prefix(self, buf: str) -> bool:
        return buf.lower() in self.prefixes

    # ---- exact-length targets (the second randomiser) -------------------
    def is_word_of_len(self, buf: str, target: int) -> bool:
        """A legible word of exactly `target` letters."""
        return len(buf) == target and buf.lower() in self.words_by_len.get(target, ())

    def can_reach_len(self, buf: str, target: int) -> bool:
        """Could `buf` still grow into a legible word of exactly `target` letters?"""
        return len(buf) < target and buf.lower() in self.prefixes_by_len.get(target, {""})

    def available_target_lengths(self, lo: int, hi: int) -> List[int]:
        """Lengths in [lo, hi] that actually have words (so a target is reachable)."""
        return [t for t in range(lo, hi + 1) if self.words_by_len.get(t)]

    def __len__(self) -> int:
        return len(self.words)

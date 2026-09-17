"""Central config. Environment variables (see .env.example) override defaults."""

from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent


def _s(name, default): return os.getenv(name, default)
def _f(name, default):
    try: return float(os.getenv(name, default))
    except (TypeError, ValueError): return default
def _i(name, default):
    try: return int(os.getenv(name, default))
    except (TypeError, ValueError): return default


# ---- Discord ----------------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
# Right-click the channel (Developer Mode on) -> Copy Channel ID. 0 = any channel.
CHANNEL_ID = _i("CHANNEL_ID", 0)          # text channel to watch (0 = any); seeds settings.json
VOICE_CHANNEL_ID = _i("VOICE_CHANNEL_ID", 0)   # voice channel to join; seeds settings.json
POKE_KEYWORD = os.getenv("POKE_KEYWORD", "poke")
# runtime settings the /fly slash commands write to (survive restarts)
SETTINGS_PATH = Path(_s("SETTINGS_PATH", str(ROOT / "settings.json")))

# ---- Web sim server ---------------------------------------------------------
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = _i("WEB_PORT", 8080)
BROADCAST_HZ = _f("BROADCAST_HZ", 20.0)

# ---- Brain ------------------------------------------------------------------
# "auto"   : use the live flysim brain if the graph is present, else replay.
# "live"   : force the live flysim brain (raises if the graph/flysim is missing).
# "replay" : force replay of recorded connectome spikes (cord_spikes.npz).
BRAIN_MODE = os.getenv("BRAIN_MODE", "auto").lower()

# Where therealfly's data + the flybrain checkout live. Defaults assume the
# sibling layout GITHUB-REPOS/{Fly Have A Mouth, FLY BODY, flybrain}.
FLY_BODY_ROOT = Path(_s("FLY_BODY_ROOT", str(ROOT.parent / "FLY BODY")))
FLYBRAIN_ROOT = Path(_s("FLYBRAIN_ROOT", str(ROOT.parent / "flybrain")))
GRAPH = Path(_s("GRAPH", str(FLYBRAIN_ROOT / "build" / "graph.npz")))

# Bundled copies (self-contained replay); fall back to FLY BODY/build if absent.
MOTOR_MAP = Path(_s("MOTOR_MAP", str(ROOT / "data" / "motor_map.json")))
SPIKES = Path(_s("SPIKES", str(ROOT / "data" / "cord_spikes.npz")))
REPLAY_CONDITION = _s("REPLAY_CONDITION", "DRIVE")
REPLAY_SEED = _i("REPLAY_SEED", 0)

# Live-brain drive: descending command neurons + Poisson rate while typing.
DRIVE_TYPES = tuple(t.strip() for t in _s("DRIVE_TYPES", "DNa01,DNa02").split(",") if t.strip())
DRIVE_HZ = _f("DRIVE_HZ", 150.0)

# ---- Read-out ---------------------------------------------------------------
# ms of BRAIN time read per keystroke (0.2 ms steps, like flysim).
DECISION_MS = _f("DECISION_MS", 40.0)
READOUT_MODE = _s("READOUT_MODE", "sample")     # "sample" or "argmax"
READOUT_TEMP = _f("READOUT_TEMP", 0.6)
READOUT_MIN_SPIKES = _i("READOUT_MIN_SPIKES", 1)

# ---- Fly game ---------------------------------------------------------------
MIN_WORDS = _i("MIN_WORDS", 1)
MAX_WORDS = _i("MAX_WORDS", 10)
# shortest string that counts as a legible word (2 keeps it fun; 3 is harder).
MIN_WORD_LEN = _i("MIN_WORD_LEN", 2)
# Second randomiser: each word gets a RANDOM target length in [WORD_LEN_MIN,
# WORD_LEN_MAX], and the fly must land a legible word of EXACTLY that many
# letters before moving on. 2-3 is watchable (~12-20s/word); 4 is a long grind
# (hundreds of keystrokes); 5 barely exists in the default dictionary.
WORD_LEN_MIN = _i("WORD_LEN_MIN", 2)
WORD_LEN_MAX = _i("WORD_LEN_MAX", 3)
# max keystrokes per second, wall-clock, so replay stays watchable (the live
# brain is usually slower than this on its own).
PRESS_HZ = _f("PRESS_HZ", 3.0)

MOOD_START = _f("MOOD_START", 0.6)
MOOD_DECAY_PER_PRESS = _f("MOOD_DECAY_PER_PRESS", 0.006)
MOOD_WIPE_PENALTY = _f("MOOD_WIPE_PENALTY", 0.05)
MOOD_WORD_REWARD = _f("MOOD_WORD_REWARD", 0.35)
DISTRESS_THRESHOLD = _f("DISTRESS_THRESHOLD", 0.35)
EAT_SECONDS = _f("EAT_SECONDS", 3.0)

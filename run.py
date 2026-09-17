"""Fly Have A Mouth -- launcher.

Wires the fly's brain -> keyboard -> dictionary -> web viewer -> Discord bot.

  python run.py              # normal: Discord bot + web viewer
  python run.py --no-bot     # web viewer only (no Discord token needed) -- great
                             # for watching the fly type locally
  python run.py --self-test  # fire one fake ping, no Discord, print what it types
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import config
from flymouth.dictionary import Dictionary
from flymouth.state import WorldState
from flymouth.brain.readout import MotorReadout
from flymouth.controller import MouthController, Request


def build_brain(readout: MotorReadout):
    """Pick the brain source per BRAIN_MODE, falling back to replay."""
    from flymouth.brain.replay import ReplayBrain

    def make_replay():
        path = config.SPIKES if config.SPIKES.exists() else config.FLY_BODY_ROOT / "build" / "cord_spikes.npz"
        return ReplayBrain(path, config.REPLAY_CONDITION, config.REPLAY_SEED)

    if config.BRAIN_MODE == "replay":
        return make_replay()

    if config.BRAIN_MODE in ("auto", "live"):
        try:
            from flymouth.brain.live import LiveBrain
            return LiveBrain(config.FLYBRAIN_ROOT, config.GRAPH,
                             motor_indices=readout.motor_indices,
                             drive_types=config.DRIVE_TYPES, drive_hz=config.DRIVE_HZ)
        except Exception as e:
            if config.BRAIN_MODE == "live":
                raise
            print(f"[brain] live brain unavailable ({e}); using recorded spikes.", flush=True)
            return make_replay()
    return make_replay()


def build_controller() -> MouthController:
    motor_map = config.MOTOR_MAP if config.MOTOR_MAP.exists() else config.FLY_BODY_ROOT / "build" / "motor_map.json"
    readout = MotorReadout(motor_map, min_spikes=config.READOUT_MIN_SPIKES,
                           mode=config.READOUT_MODE, temperature=config.READOUT_TEMP)
    brain = build_brain(readout)
    dictionary = Dictionary.load(min_word_len=config.MIN_WORD_LEN)
    state = WorldState(mood=config.MOOD_START)
    ctl = MouthController(brain, readout, dictionary, config, state)
    print(f"[fly] dictionary: {len(dictionary)} words | brain: {brain.label}", flush=True)
    return ctl


def self_test() -> None:
    ctl = build_controller()
    ctl.cfg.PRESS_HZ = 1000.0            # go fast for the test
    ctl.start()
    ctl.submit(Request("selftest", 1, 0))
    comp = ctl.completions.get()
    print(f"\nfly typed {comp.word_count} word(s): {comp.sentence!r}")
    ctl.stop()


async def serve(no_bot: bool) -> None:
    from flymouth.server import SimServer
    ctl = build_controller()
    ctl.start()
    server = SimServer(ctl.state, config)
    await server.start()
    print(f"[web] fly viewer at http://{config.WEB_HOST}:{config.WEB_PORT}", flush=True)
    tasks = [asyncio.create_task(server.broadcast_loop())]

    if not no_bot:
        if not config.DISCORD_TOKEN:
            print("[bot] no DISCORD_TOKEN set -- running web viewer only. "
                  "Set it in .env, or use --no-bot to silence this.", flush=True)
        else:
            from flymouth.bot import make_bot
            from flymouth.settings import Settings
            settings = Settings(config.SETTINGS_PATH,
                                watch_channel_id=config.CHANNEL_ID,
                                voice_channel_id=config.VOICE_CHANNEL_ID)
            bot, completion_poster = make_bot(ctl, config, settings)
            tasks.append(asyncio.create_task(completion_poster()))
            tasks.append(asyncio.create_task(bot.start(config.DISCORD_TOKEN)))

    await asyncio.gather(*tasks)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fly Have A Mouth")
    ap.add_argument("--no-bot", action="store_true", help="web viewer only, no Discord")
    ap.add_argument("--self-test", action="store_true", help="one fake ping, print output")
    args = ap.parse_args()
    if args.self_test:
        self_test(); return
    try:
        asyncio.run(serve(args.no_bot))
    except KeyboardInterrupt:
        print("\nbye \U0001FAB0")


if __name__ == "__main__":
    main()

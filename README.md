# fly have a mouth

A fruit fly in a glass box with a keyboard, a monitor, and a food bowl. Ping it
from Discord and it has to type legible words — bashing keys until the letters
spell something real, wiping when it hits a dead end, earning food when it
succeeds. The twist: **the keys are chosen by a real fly's brain.** The fly's
leg motor-neuron spikes — from the FlyEM male-CNS connectome, simulated as LIF —
are read out into keystrokes.

It's a browser page; you watch it in a Discord voice channel by screen-sharing
the tab.

## How the brain drives the keyboard

```
Discord ping ──▶ drive the fly's command neurons
                        │
              real motor-neuron spikes            (LiveBrain: flysim LIF over the
              (381 leg MNs, build/motor_map.json)   connectome, live;  or
                        │                            ReplayBrain: recorded spikes)
                        ▼
        26 motor-neuron pools ──▶ one keystroke per tick   (flymouth/brain/readout.py)
                        │
                        ▼
        dictionary judges legibility        (flymouth/dictionary.py)
          prefix still valid → keep bashing
          whole word         → reward, bank it, fill the bowl a bit
          dead end           → CLEAR (wipe), mild distress
                        │
              N words done ──▶ bowl fills, sentence posted back to Discord
```

- **MEASURED**: which connectome neuron is a leg motor neuron and its leg / side /
  joint (straight from `therealfly`'s `build/motor_map.json`); the spikes themselves
  (real flysim output over the real wiring).
- **CHOSEN**: the split of the 381 leg motor neurons into 26 letter-pools; the
  activity-weighted, baseline-normalised sampling that turns pool firing into a key;
  the dictionary, word length and reward feel. None of it is tuned to an outcome.

This does **not** claim the fly *intends* to spell. It claims: real spikes of real
motor neurons, under a fixed rule, choose the keys — and a dictionary decides which
strings are words. It is not validated locomotion (your `therealfly` Stage 1/2 say
the wiring doesn't walk a body yet); the flying in the viewer is vanity, the brain
read-out is the real part.

## Run it

```
py -m pip install -r requirements.txt
py run.py --self-test     # one fake ping → prints e.g.  fly typed: 'on be ok so hi dip as sin by we'
py run.py --no-bot        # just watch: http://127.0.0.1:8080
py run.py                 # Discord bot + viewer (needs a token in .env)
```

Default brain = **recorded real connectome spikes** (`data/cord_spikes.npz`) — runs
anywhere, no 2.5 GB graph, no GPU. To run the **full flysim network live**, and for
Discord/streaming setup, see [`setup/SETUP.md`](setup/SETUP.md).

## Discord

`@fly` → it types 1–10 words (random). `@fly poke` → taps the glass and startles it.
One request at a time; extra pings queue. Stream it by joining a VC and Go-Live /
screen-sharing the viewer tab (fully within Discord's ToS — no self-bot).

## Layout

```
run.py                     launcher (--no-bot, --self-test)
config.py                  all settings (env-overridable; see .env.example)
flymouth/dictionary.py     prefix/word legibility checks
flymouth/brain/readout.py  motor-neuron pools → keystrokes
flymouth/brain/replay.py   ReplayBrain — recorded connectome spikes
flymouth/brain/live.py     LiveBrain — real flysim LIF over the connectome
flymouth/controller.py     the game loop (threaded; drives the brain, judges words)
flymouth/state.py          the world state the browser renders
flymouth/server.py         aiohttp server + WebSocket state stream
flymouth/bot.py            Discord bot (ping / poke)
web/                       the viewer (glass box, keyboard, monitor, bowl, neural strip)
data/words.txt             the dictionary
data/motor_map.json        copied from FLY BODY/build (Stage 0 motor map)
data/cord_spikes.npz       copied from FLY BODY/build (real recorded spikes)
setup/SETUP.md             quick start, Discord, streaming, live-brain install
```

## Credits & licence

The brain and body science is **`therealfly`** (`../FLY BODY`): the FlyEM male-CNS
connectome (HHMI Janelia FlyEM / Cambridge Connectomics / Google Research, CC-BY 4.0)
simulated with `flysim` after Shiu et al. 2024. `data/motor_map.json` and
`data/cord_spikes.npz` are derivatives of that work (CC-BY 4.0 — keep the attribution).
This game layer is yours to license as you like.

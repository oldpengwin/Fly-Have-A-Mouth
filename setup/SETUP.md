# Setup

## 0. Quick start (recorded real-brain spikes — runs anywhere, no GPU)

```
cd "Fly Have A Mouth"
py -m pip install -r requirements.txt
py run.py --self-test        # fires one fake ping, prints what the fly types
py run.py --no-bot           # opens the viewer at http://127.0.0.1:8080
```

This uses `data/cord_spikes.npz` — **real** recorded spikes from your `therealfly`
Stage-1 runs (real flysim over the real connectome). The fly's real leg
motor-neuron pools choose every key. No 2.5 GB graph, no GPU. This is the default
and it's the recommended way to run the Discord bot too.

## 1. Discord bot

1. https://discord.com/developers/applications → New Application → **Bot** → copy the token.
2. Turn ON **Message Content Intent** (Bot page → Privileged Gateway Intents).
3. Invite it: OAuth2 → URL Generator → scopes `bot`, permissions *Send Messages*,
   *Read Message History*, *Add Reactions* → open the URL, add it to your server.
4. `copy .env.example .env`, paste the token into `DISCORD_TOKEN`, set `CHANNEL_ID`
   (right-click the channel → Copy Channel ID; Developer Mode must be on).
5. `py run.py`
6. In the channel: `@YourBot` → the fly types 1–10 words. `@YourBot poke` → taps the glass.

## 2. Stream it to a voice channel

The fly is a web page, so you stream it the normal (ToS-safe) way:

- Join the voice channel, then **Go Live / Screen Share** the browser tab (or window)
  showing `http://127.0.0.1:8080`. Fullscreen the tab for a clean shot.
- Or add it as a Browser Source in OBS and stream/record from there.

## 3. LIVE brain (optional — run the real flysim network in real time)

The live brain integrates the full 165,122-neuron LIF network forward while the
fly types, driving the descending command neurons you set in `DRIVE_TYPES`.

You need the public **flybrain** checkout (the `flysim` simulator + the built
`graph.npz`) that `therealfly` already depends on:

```
cd ..                                   # into GITHUB-REPOS
git clone https://github.com/fruitflydev/flycoinrh flybrain
cd flybrain
py -m pip install -r requirements.txt   # flysim's own deps (numpy/scipy; torch for GPU)
```

Download the three public FlyEM male-CNS v1.0 files (CC-BY 4.0, no account) into
`flybrain/data/` as its README describes, then build the graph:

```
py build_graph.py                       # writes build/graph.npz (~2.5 GB; needs >= 6 GB free RAM)
```

Point the game at it (in `.env`):

```
BRAIN_MODE=live
FLYBRAIN_ROOT=C:/Users/ayaz1/Documents/GITHUB-REPOS/flybrain
GRAPH=C:/Users/ayaz1/Documents/GITHUB-REPOS/flybrain/build/graph.npz
```

Then `py run.py`. Notes:

- **Speed.** The full LIF net runs slower than real time on CPU (your Stage-1 runs
  were ~20× slower than real time; the GPU port ~7×). So the fly types slowly. That's
  fine for a stream — increase `DECISION_MS` to read a bigger brain window per key, or
  keep `BRAIN_MODE=replay` for a lively fly and switch to `live` when you want the real
  network in the loop.
- If `graph.npz` or `flysim` isn't found and `BRAIN_MODE=auto`, the game logs it and
  falls back to the recorded spikes automatically.

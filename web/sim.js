/* Fly Have A Mouth — browser overlay renderer.
   The server owns all logic. This file just draws WorldState and animates the
   fly flying/bashing between snapshots. Point OBS / a browser source at this
   page, or just watch it. */

(() => {
  "use strict";
  const W = 960, H = 600;
  const canvas = document.getElementById("box");
  const ctx = canvas.getContext("2d");
  const connEl = document.getElementById("conn");
  const brainEl = document.getElementById("brain");
  const requesterEl = document.getElementById("requester");
  const progressEl = document.getElementById("progress");
  const queueEl = document.getElementById("queue");
  const moodbar = document.getElementById("moodbar");
  const bowlbar = document.getElementById("bowlbar");

  function fit() {
    const dpr = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  fit();
  window.addEventListener("resize", fit);

  // ---- keyboard geometry (letters + a fake space bar) ----------------------
  const ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm"];
  const KB = { x: 120, y: 388, w: 720, keyH: 46, gap: 8 };
  const keyRects = {};   // letter -> {x,y,w,h,cx,cy}
  (function layoutKeyboard() {
    for (let r = 0; r < ROWS.length; r++) {
      const row = ROWS[r];
      const kw = (KB.w - KB.gap * (row.length - 1)) / row.length;
      const rowW = row.length * kw + (row.length - 1) * KB.gap;
      const startX = KB.x + (KB.w - rowW) / 2;
      const y = KB.y + r * (KB.keyH + KB.gap);
      for (let i = 0; i < row.length; i++) {
        const x = startX + i * (kw + KB.gap);
        keyRects[row[i]] = { x, y, w: kw, h: KB.keyH, cx: x + kw / 2, cy: y + KB.keyH / 2 };
      }
    }
  })();

  // ---- state ---------------------------------------------------------------
  let S = null;                 // latest server snapshot
  let prev = { seq: -1, completed: 0, bufLen: 0, lastKey: null };
  const fly = { x: W / 2, y: 240, vx: 0, vy: 0, wing: 0, landT: 0, shake: 0 };
  let bowlShown = 0, moodShown = 0.6, boxShake = 0;
  const particles = [];
  const events = { wordPop: 0, wipe: 0 };
  let wanderT = 0, wanderX = W / 2, wanderY = 240;
  let rasterBuf = null;   // JS-decayed per-neuron glow: array[26][poolSize]

  // ---- websocket -----------------------------------------------------------
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => { connEl.textContent = "live"; connEl.className = "pill ok"; };
    ws.onclose = () => { connEl.textContent = "reconnecting…"; connEl.className = "pill bad"; setTimeout(connect, 1200); };
    ws.onerror = () => ws.close();
    ws.onmessage = (m) => { try { onState(JSON.parse(m.data)); } catch (e) {} };
  }

  function onState(next) {
    // derive animation events from diffs so we never miss one between snapshots
    if (next.seq !== prev.seq) {
      const doneNow = (next.completed_words || []).length;
      if (doneNow > prev.completed) {
        events.wordPop = 1;
        popParticles(keyRects[(next.last_key || "m")] || { cx: W / 2, cy: 300 }, "#6be3a2");
      } else if (next.buffer.length < prev.bufLen && next.buffer.length === 0 && next.mode === "typing") {
        events.wipe = 1; boxShake = 6;
      }
      // Fly animation sync: when target_key changes, fly to that key first.
      // When last_key changes (after animation delay), the letter appears in buffer.
      if (next.target_key && next.target_key !== prev.targetKey && next.mode === "typing") {
        aimAt(next.target_key);
      }
      if (next.poke_flash > 0.6 && S && next.poke_flash > S.poke_flash) boxShake = 10;
      // accumulate real spikes into the decaying raster glow
      if (next.neuro_cols && next.neuro_cols.length) {
        if (!rasterBuf || rasterBuf.length !== next.neuro_cols.length ||
            (rasterBuf[0] || []).length !== (next.neuro_cols[0] || []).length) {
          rasterBuf = next.neuro_cols.map(col => col.map(() => 0));
        }
        for (let p = 0; p < next.neuro_cols.length; p++) {
          const col = next.neuro_cols[p];
          for (let j = 0; j < col.length; j++) {
            if (col[j] > 0) rasterBuf[p][j] = Math.min(1, rasterBuf[p][j] + 0.5 + 0.25 * col[j]);
          }
        }
      }
      prev = { seq: next.seq, completed: doneNow, bufLen: next.buffer.length, 
               lastKey: next.last_key, targetKey: next.target_key };
    }
    S = next;
    if (brainEl) brainEl.textContent = "brain: " + (S.brain_label || "—");
    requesterEl.textContent = S.requester || "—";
    progressEl.textContent = S.mode === "typing"
      ? `${S.words_done}/${S.words_total} words` : S.mode;
    queueEl.textContent = S.queue_len || 0;
  }

  function aimAt(letter) {
    const k = keyRects[letter];
    if (k) { fly._tx = k.cx; fly._ty = k.cy; fly.landT = 0; }
  }

  function popParticles(at, color) {
    for (let i = 0; i < 14; i++) {
      const a = Math.random() * Math.PI * 2, s = 1 + Math.random() * 3;
      particles.push({ x: at.cx, y: at.cy, vx: Math.cos(a) * s, vy: Math.sin(a) * s - 1, life: 1, color });
    }
  }

  // ---- render loop ---------------------------------------------------------
  let last = performance.now();
  function frame(now) {
    const dt = Math.min(50, now - last) / 1000; last = now;
    update(dt);
    draw();
    requestAnimationFrame(frame);
  }

  function update(dt) {
    if (!S) return;
    moodShown += (S.mood - moodShown) * Math.min(1, dt * 6);
    bowlShown += (S.bowl - bowlShown) * Math.min(1, dt * 4);
    moodbar.style.width = (moodShown * 100).toFixed(0) + "%";
    moodbar.style.background = moodShown < 0.35 ? "#ff6b7d" : "#6be3a2";
    bowlbar.style.width = (bowlShown * 100).toFixed(0) + "%";
    boxShake *= 0.86;
    events.wordPop *= 0.9; events.wipe *= 0.9;
    if (rasterBuf) {                     // fade the neural glow
      const k = Math.pow(0.04, dt);
      for (const col of rasterBuf) for (let j = 0; j < col.length; j++) col[j] *= k;
    }
    fly.wing += dt * (28 + (1 - moodShown) * 40);

    // target: a key while typing, the bowl while eating, gentle wander when idle
    let tx, ty;
    if (S.mode === "typing" && fly._tx != null) {
      tx = fly._tx; ty = fly._ty;
    } else if (S.mode === "eating") {
      tx = 812 + Math.cos(now / 260) * 14; ty = 470 + Math.sin(now / 200) * 8;
    } else {
      wanderT -= dt;
      if (wanderT <= 0) { wanderT = 0.7 + Math.random(); wanderX = 200 + Math.random() * 560; wanderY = 170 + Math.random() * 130; }
      tx = wanderX; ty = wanderY;
    }
    // distress = jittery, frantic; happy = smooth
    const frantic = (1 - moodShown);
    const jitter = frantic * 26;
    tx += (Math.random() - 0.5) * jitter;
    ty += (Math.random() - 0.5) * jitter;
    const accel = 8 + frantic * 10;
    fly.vx += (tx - fly.x) * accel * dt;
    fly.vy += (ty - fly.y) * accel * dt;
    const damp = Math.pow(0.001, dt);
    fly.vx *= damp; fly.vy *= damp;
    fly.x += fly.vx * dt; fly.y += fly.vy * dt;

    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx; p.y += p.vy; p.vy += 0.15; p.life -= dt * 1.6;
      if (p.life <= 0) particles.splice(i, 1);
    }
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    const sx = (Math.random() - 0.5) * boxShake, sy = (Math.random() - 0.5) * boxShake;
    ctx.save(); ctx.translate(sx, sy);

    drawGlassBox();
    drawMonitor();
    drawNeural();
    drawKeyboard();
    drawBowl();
    drawParticles();
    drawFly();
    drawPoke();

    ctx.restore();
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawGlassBox() {
    // floor
    const g = ctx.createLinearGradient(0, 60, 0, 560);
    g.addColorStop(0, "#0f1320"); g.addColorStop(1, "#0b0e17");
    roundRect(40, 40, 880, 520, 18); ctx.fillStyle = g; ctx.fill();
    // glass edges
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(150,190,255,0.18)";
    roundRect(40, 40, 880, 520, 18); ctx.stroke();
    ctx.lineWidth = 1; ctx.strokeStyle = "rgba(255,255,255,0.06)";
    roundRect(48, 48, 864, 504, 14); ctx.stroke();
    // corner glare
    ctx.fillStyle = "rgba(255,255,255,0.04)";
    ctx.beginPath(); ctx.moveTo(60, 60); ctx.lineTo(230, 60); ctx.lineTo(60, 230); ctx.closePath(); ctx.fill();
  }

  function drawMonitor() {
    const mx = 150, my = 78, mw = 660, mh = 118;
    roundRect(mx, my, mw, mh, 10);
    ctx.fillStyle = "#05221a"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "rgba(107,227,162,0.35)"; ctx.stroke();

    ctx.textBaseline = "top";
    // task / status line
    ctx.fillStyle = "#5bd99a"; ctx.font = "13px ui-monospace, monospace";
    const msg = S ? S.message : "connecting…";
    ctx.fillText(clip(msg, 74), mx + 16, my + 12);

    // the current typed buffer (big) with blinking cursor
    ctx.font = "28px ui-monospace, monospace";
    const wiping = events.wipe > 0.25;
    ctx.fillStyle = wiping ? "#ff6b7d" : "#eafff2";
    const buf = S ? S.buffer : "";
    const cursor = (Math.floor(performance.now() / 400) % 2) ? "_" : " ";
    ctx.fillText("> " + buf + cursor, mx + 16, my + 40);
    if (S && S.mode === "typing" && S.word_target_len) {
      ctx.font = "12px ui-monospace, monospace"; ctx.fillStyle = "#5bd99a";
      ctx.fillText(`need ${S.word_target_len} letters  (${buf.length}/${S.word_target_len})`, mx + mw - 150, my + 30);
    }
    if (wiping) { ctx.font = "13px ui-monospace, monospace"; ctx.fillStyle = "#ff6b7d"; ctx.fillText("CLEAR", mx + mw - 70, my + 48); }

    // chat bar: completed legible words
    ctx.font = "15px ui-monospace, monospace"; ctx.fillStyle = "#8fe9c0";
    const chat = S && S.completed_words.length ? S.completed_words.join(" ") : "…";
    ctx.fillText("chat: " + clip(chat, 66), mx + 16, my + 84);
  }

  function drawNeural() {
    // LIVE RASTER: 381 real leg motor neurons as cells that flash with spikes,
    // grouped into the 26 key-columns. Watch a column ignite -> that key is hit.
    const x0 = 150, y0 = 206, w = 660, h = 48;
    ctx.textAlign = "left"; ctx.font = "10px ui-monospace, monospace";
    ctx.fillStyle = "#7a8296";
    ctx.fillText("live connectome · leg motor neurons firing", x0, y0 - 4);
    if (S && S.neuro_rate != null) {
      ctx.fillStyle = "#5bd99a"; ctx.textAlign = "right";
      ctx.fillText(`${Math.round(S.neuro_rate)} spikes`, x0 + w, y0 - 4);
      ctx.textAlign = "left";
    }
    const cols = rasterBuf || (S && S.neuro_cols);
    if (!cols || !cols.length) return;
    const n = cols.length;                 // 26
    const cw = w / n;
    for (let p = 0; p < n; p++) {
      const col = cols[p], m = col.length || 1;
      const ch = (h - 2) / m;
      const letter = String.fromCharCode(97 + p);
      const hot = S && S.last_key === letter && S.mode === "typing";
      // column backing
      ctx.fillStyle = hot ? "rgba(107,227,162,0.14)" : "rgba(255,255,255,0.02)";
      ctx.fillRect(x0 + p * cw, y0, cw - 1, h);
      for (let j = 0; j < col.length; j++) {
        const v = Math.max(0, Math.min(1, col[j]));
        ctx.fillStyle = v > 0.02
          ? `rgba(${Math.round(120 + 135 * v)},255,${Math.round(150 + 40 * v)},${0.35 + 0.65 * v})`
          : "rgba(60,72,92,0.5)";
        ctx.fillRect(x0 + p * cw + 1, y0 + j * ch + 0.5, cw - 3, Math.max(1.5, ch - 1));
      }
      ctx.fillStyle = hot ? "#eafff2" : "#4a5468";
      ctx.textAlign = "center"; ctx.font = "9px ui-monospace, monospace";
      ctx.fillText(letter, x0 + p * cw + cw / 2, y0 + h + 8);
    }
    ctx.textAlign = "left";
  }

  function drawKeyboard() {
    ctx.font = "15px ui-monospace, monospace"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    for (const letter in keyRects) {
      const k = keyRects[letter];
      const hot = S && S.last_key === letter && S.mode === "typing" ? 1 : 0;
      roundRect(k.x, k.y, k.w, k.h, 6);
      ctx.fillStyle = hot ? "#1c3a2c" : "#161b28"; ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = hot ? "#6be3a2" : "#2a3145"; ctx.stroke();
      ctx.fillStyle = hot ? "#7dffb7" : "#aab4c9";
      ctx.fillText(letter, k.cx, k.cy + 1);
    }
    ctx.textAlign = "left";
  }

  function drawBowl() {
    const bx = 812, by = 486, rw = 66, rh = 30;
    // dish
    ctx.beginPath(); ctx.ellipse(bx, by, rw, rh, 0, 0, Math.PI * 2);
    ctx.fillStyle = "#20140b"; ctx.fill();
    ctx.lineWidth = 2; ctx.strokeStyle = "#3a2a1a"; ctx.stroke();
    // food fills as the fly succeeds
    const fill = Math.max(0, Math.min(1, bowlShown));
    if (fill > 0.01) {
      ctx.save();
      ctx.beginPath(); ctx.ellipse(bx, by, rw - 6, rh - 5, 0, 0, Math.PI * 2); ctx.clip();
      ctx.fillStyle = "#c98a3a";
      const top = by + (rh - 6) - fill * (rh * 1.6);
      ctx.fillRect(bx - rw, top, rw * 2, rh * 2);
      // pellets
      ctx.fillStyle = "#e0a24d";
      for (let i = 0; i < fill * 10; i++) {
        ctx.beginPath();
        ctx.arc(bx - rw + 12 + (i * 13) % (rw * 2 - 20), by + 6 - (i % 3) * 5, 3, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    ctx.fillStyle = "#6b6152"; ctx.font = "11px ui-monospace, monospace"; ctx.textAlign = "center";
    ctx.fillText("bowl", bx, by + 40); ctx.textAlign = "left";
  }

  function drawFly() {
    const happy = moodShown;
    ctx.save();
    ctx.translate(fly.x, fly.y);
    // aura
    const auraR = 20 + (1 - happy) * 6;
    const aura = ctx.createRadialGradient(0, 0, 2, 0, 0, auraR);
    aura.addColorStop(0, happy < 0.35 ? "rgba(255,107,125,0.30)" : "rgba(107,227,162,0.22)");
    aura.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = aura; ctx.beginPath(); ctx.arc(0, 0, auraR, 0, Math.PI * 2); ctx.fill();

    // wings (flap)
    const flap = Math.sin(fly.wing) * 0.6 + 0.7;
    ctx.fillStyle = "rgba(200,220,255,0.35)";
    ctx.save(); ctx.scale(1, flap);
    ctx.beginPath(); ctx.ellipse(-6, -6, 9, 5, -0.6, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(6, -6, 9, 5, 0.6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    // body
    ctx.fillStyle = "#20242e";
    ctx.beginPath(); ctx.ellipse(0, 0, 8, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#2b3040";
    ctx.beginPath(); ctx.ellipse(0, -8, 6, 5, 0, 0, Math.PI * 2); ctx.fill();
    // eyes
    ctx.fillStyle = happy < 0.35 ? "#ff6b7d" : "#e34b5a";
    ctx.beginPath(); ctx.arc(-3, -9, 2.2, 0, Math.PI * 2); ctx.arc(3, -9, 2.2, 0, Math.PI * 2); ctx.fill();
    // little mouth (it has a mouth, after all)
    ctx.strokeStyle = "#e9c56b"; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.arc(0, -5, 2.4, 0.15 * Math.PI, 0.85 * Math.PI); ctx.stroke();
    ctx.restore();
  }

  function drawParticles() {
    for (const p of particles) {
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, 2.5, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function drawPoke() {
    if (!S || S.poke_flash <= 0) return;
    const a = S.poke_flash;
    ctx.strokeStyle = `rgba(150,200,255,${a * 0.7})`;
    ctx.lineWidth = 2;
    const cx = 480, cy = 300;
    for (let i = 0; i < 3; i++) {
      const r = (1 - a) * 120 + i * 26;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    }
  }

  function clip(s, n) { s = s || ""; return s.length > n ? s.slice(0, n - 1) + "…" : s; }

  connect();
  requestAnimationFrame(frame);
})();

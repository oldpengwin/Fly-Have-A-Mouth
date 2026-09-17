"""Local web server: serves the sim page and streams world state to browsers.

Runs in the asyncio loop with the Discord bot. Every connected browser gets a
JSON snapshot of WorldState ~BROADCAST_HZ times a second over a WebSocket; the
browser does all the drawing. Point OBS / a Discord Go-Live / a browser source
at http://WEB_HOST:WEB_PORT to stream the fly."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Set

from aiohttp import web, WSMsgType

from .state import WorldState

_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")


class SimServer:
    def __init__(self, state: WorldState, cfg):
        self.state = state
        self.cfg = cfg
        self.app = web.Application()
        self._clients: Set[web.WebSocketResponse] = set()
        self.app.router.add_get("/", self._index)
        self.app.router.add_get("/ws", self._ws)
        self.app.router.add_static("/static/", _WEB_DIR, name="static")
        self._runner = None

    async def _index(self, request):
        return web.FileResponse(os.path.join(_WEB_DIR, "index.html"))

    async def _ws(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._clients.add(ws)
        try:
            await ws.send_str(json.dumps(self.state.to_dict()))
            async for msg in ws:
                if msg.type == WSMsgType.ERROR:
                    break
        finally:
            self._clients.discard(ws)
        return ws

    async def broadcast_loop(self):
        dt = 1.0 / max(1.0, self.cfg.BROADCAST_HZ)
        while True:
            await asyncio.sleep(dt)
            if self.state.poke_flash > 0:
                self.state.poke_flash = max(0.0, self.state.poke_flash - dt * 1.6)
            if not self._clients:
                continue
            payload = json.dumps(self.state.to_dict())
            for ws in list(self._clients):
                try:
                    await ws.send_str(payload)
                except Exception:
                    self._clients.discard(ws)

    async def start(self):
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.cfg.WEB_HOST, self.cfg.WEB_PORT)
        await site.start()

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

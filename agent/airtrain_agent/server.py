"""WebSocket server the phone app connects to: ws://<lan-ip>:<port>/?token=<token>."""

from __future__ import annotations

import asyncio
import hmac
import json
from http import HTTPStatus
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from websockets.asyncio.server import ServerConnection, broadcast, serve

from .controller import Controller


def _token_ok(path: str, token: str) -> bool:
    got = parse_qs(urlparse(path).query).get("token", [""])[0]
    return hmac.compare_digest(got.encode(), token.encode())


async def run_server(
    ctrl: Controller,
    host: str,
    port: int,
    token: str,
    quiet: bool = False,
    on_snapshot: Callable[[dict[str, Any], int], None] | None = None,
) -> None:
    """Serve telemetry until cancelled. `on_snapshot(snapshot, connected_apps)` runs after every push."""
    clients: set[ServerConnection] = set()
    latest: dict[str, Any] = {}

    def log(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    def process_request(connection: ServerConnection, request: Any) -> Any:
        if not _token_ok(request.path, token):
            log(f"rejected {connection.remote_address[0]}: bad or missing token")
            return connection.respond(HTTPStatus.UNAUTHORIZED, "invalid or missing token\n")
        return None

    async def handler(ws: ServerConnection) -> None:
        peer = ws.remote_address[0] if ws.remote_address else "?"
        clients.add(ws)
        log(f"app connected from {peer} ({len(clients)} connected)")
        try:
            await ws.send(json.dumps({"type": "hello", "v": 1, "device_id": ctrl.cfg.device_id}))
            if latest:
                await ws.send(json.dumps(latest))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    cmd = str(msg.get("cmd", "")).lower()
                except (ValueError, AttributeError):
                    await ws.send(json.dumps({"type": "ack", "ok": False, "error": "expected JSON {\"cmd\": ...}"}))
                    continue
                result = ctrl.command(cmd)
                if result.get("ok") and cmd in ("pause", "resume"):
                    log(f"{cmd} requested by {peer}")
                await ws.send(json.dumps({"type": "ack", "cmd": cmd, **result}))
                if cmd in ("pause", "resume", "snapshot"):
                    snap = await asyncio.get_running_loop().run_in_executor(None, ctrl.snapshot)
                    latest.update(snap)
                    await ws.send(json.dumps(snap))
        except Exception:
            pass
        finally:
            clients.discard(ws)
            log(f"app disconnected from {peer} ({len(clients)} connected)")

    def push(snap: dict[str, Any]) -> None:
        latest.clear()
        latest.update(snap)
        if clients:
            broadcast(clients, json.dumps(snap))
        if on_snapshot:
            on_snapshot(snap, len(clients))

    async with serve(handler, host, port, process_request=process_request, ping_interval=20):
        await ctrl.run(push)

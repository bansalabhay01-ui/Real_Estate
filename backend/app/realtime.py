"""Live updates for the sales dashboard over WebSocket.

Connections live in memory, so run a single server process (fine for the hackathon).
Message shapes are in docs/CONTRACTS.md.
"""

from typing import Any

from fastapi import WebSocket


class DashboardHub:
    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        """Start sending updates to an accepted connection."""
        self._sockets.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._sockets.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for ws in list(self._sockets):
            try:
                await ws.send_json(message)
            except Exception:  # the dashboard tab closed mid-send; any send error means it's gone
                self.remove(ws)


hub = DashboardHub()

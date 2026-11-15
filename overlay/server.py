import asyncio
import json
import threading
from typing import Set, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PySide6.QtCore import QObject, Signal

from overlay.config import ConfigManager


class ServerBridge(QObject):
    """
    Qt Signal Bridge to safely dispatch events from the async FastAPI
    WebSocket thread to the PySide6 main UI thread.
    """
    bounds_received = Signal(int, int, int, int, int)      # left, top, width, height, tab_count
    tab_activated = Signal(int, int)                       # tab_index, tab_count
    blocked_tab_opened = Signal(int, int, int, str, str)   # tab_id, tab_index, tab_count, url, title
    calibration_updated = Signal()


class TabPetServer:
    """
    Local FastAPI + WebSocket server bound to 127.0.0.1 only.
    Handles communication with the Chrome Extension using token authentication.
    """

    def __init__(self, config_manager: ConfigManager, bridge: ServerBridge):
        self.config = config_manager
        self.bridge = bridge
        self.app = FastAPI(title="TabPet Local Server", docs_url=None, redoc_url=None)
        self.active_connections: Set[WebSocket] = set()
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        # Strict CORS - allow extensions
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.get("/health")
        async def health():
            return {"status": "ok", "app": "TabPet", "version": "1.0.0"}

        @self.app.get("/token")
        async def get_token():
            # Local token check helper
            return {"auth_token": self.config.get("auth_token")}

        @self.app.websocket("/ws")
        async def websocket_endpoint(
            websocket: WebSocket,
            token: Optional[str] = Query(None)
        ):
            # Check authentication token
            expected_token = self.config.get("auth_token")
            if not token or token != expected_token:
                await websocket.close(code=4001, reason="Unauthorized: invalid token")
                return

            await websocket.accept()
            self.active_connections.add(websocket)
            print(f"[Server] Chrome Extension connected via WebSocket (token verified).")

            # Send initial config to extension
            await websocket.send_json({
                "type": "init",
                "config": {
                    "tab_offset_x": self.config.get("tab_offset_x"),
                    "tab_offset_y": self.config.get("tab_offset_y"),
                    "max_tab_width": self.config.get("max_tab_width"),
                    "pet_name": self.config.get("pet_name"),
                }
            })

            try:
                while True:
                    text = await websocket.receive_text()
                    try:
                        data = json.loads(text)
                        await self._handle_client_message(data, websocket)
                    except json.JSONDecodeError:
                        continue
            except WebSocketDisconnect:
                self.active_connections.discard(websocket)
                print("[Server] Chrome Extension disconnected.")
            except Exception as e:
                print(f"[Server] WebSocket error: {e}")
                self.active_connections.discard(websocket)

    async def _handle_client_message(self, data: Dict[str, Any], websocket: WebSocket) -> None:
        msg_type = data.get("type")

        if msg_type == "window_bounds":
            # Extension sent Chrome window bounds
            left = int(data.get("left", 0))
            top = int(data.get("top", 0))
            width = int(data.get("width", 1200))
            height = int(data.get("height", 800))
            tab_count = int(data.get("tab_count", 1))
            self.bridge.bounds_received.emit(left, top, width, height, tab_count)

        elif msg_type == "tab_activated":
            # Active tab changed
            tab_index = int(data.get("tab_index", 0))
            tab_count = int(data.get("tab_count", 1))
            self.bridge.tab_activated.emit(tab_index, tab_count)

        elif msg_type == "blocked_tab_opened":
            # Blocked tab opened!
            tab_id = int(data.get("tab_id", 0))
            tab_index = int(data.get("tab_index", 0))
            tab_count = int(data.get("tab_count", 1))
            url = str(data.get("url", ""))
            title = str(data.get("title", ""))
            self.bridge.blocked_tab_opened.emit(tab_id, tab_index, tab_count, url, title)

        elif msg_type == "ping":
            await websocket.send_json({"type": "pong"})

    async def broadcast_tab_closed(self, tab_id: int) -> None:
        """Notifies the extension that the pet has completed closing a tab."""
        dead_connections = set()
        msg = json.dumps({"type": "tab_closed", "tab_id": tab_id})
        for ws in self.active_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead_connections.add(ws)
        self.active_connections.difference_update(dead_connections)

    def notify_tab_closed(self, tab_id: int) -> None:
        """Thread-safe trigger to broadcast tab closure to extension."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_tab_closed(tab_id), self._loop)

    def start_background(self) -> None:
        """Starts the FastAPI server in a dedicated daemon thread."""
        host = self.config.get("host", "127.0.0.1")
        port = int(self.config.get("port", 8765))

        def run_server():
            try:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                config = uvicorn.Config(
                    self.app,
                    host=host,
                    port=port,
                    log_level="warning",
                    access_log=False,
                    loop="asyncio",
                )
                server = uvicorn.Server(config)
                self._loop.run_until_complete(server.serve())
            except OSError as e:
                if "address already in use" in str(e).lower() or getattr(e, "errno", None) == 48:
                    print(f"[Server] ⚠️ Notice: Port {port} is already in use by another instance. Reusing existing server.")
                else:
                    print(f"[Server] Server startup error: {e}")
            except Exception as e:
                print(f"[Server] Server thread exception: {e}")

        self._server_thread = threading.Thread(target=run_server, daemon=True, name="TabPetServerThread")
        self._server_thread.start()
        print(f"[Server] FastAPI + WebSocket listening on ws://{host}:{port}/ws")

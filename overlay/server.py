import asyncio
import json
import threading
from typing import Set, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PySide6.QtCore import QObject, Signal

from overlay.config import ConfigManager
from overlay.memory import MemoryStore
from overlay.ai import GeminiPetAI


class ServerBridge(QObject):
    """
    Qt Signal Bridge to safely dispatch events from the async FastAPI
    WebSocket thread to the PySide6 main UI thread.
    """
    bounds_received = Signal(int, int, int, int, int)      # left, top, width, height, tab_count
    tab_activated = Signal(int, int)                       # tab_index, tab_count
    blocked_tab_opened = Signal(int, int, int, str, str, int, int, str) # tab_id, tab_index, tab_count, url, title, blocks_today, streak, goal
    calibration_updated = Signal()
    trust_updated = Signal(int, str)                       # trust_score, mood


# API Request Models
class JudgeReq(BaseModel):
    url: str
    title: str = ""
    goal: str = ""


class PleaReq(BaseModel):
    tab_id: int
    url: str
    title: str = ""
    goal: str = ""
    plea: str


class GoalReq(BaseModel):
    goal: str


class LocalOnlyReq(BaseModel):
    local_only: bool


class TabPetServer:
    """
    Local FastAPI + WebSocket server bound to 127.0.0.1 only.
    Handles communication with the Chrome Extension, AI Judge, and Plea Bargain arbitrations.
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        bridge: ServerBridge,
        ai: GeminiPetAI,
        memory: MemoryStore
    ):
        self.config = config_manager
        self.bridge = bridge
        self.ai = ai
        self.memory = memory
        self.app = FastAPI(title="TabPet Local Server", docs_url=None, redoc_url=None)
        self.active_connections: Set[WebSocket] = set()
        self._server_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        # Strict CORS - allow local extensions
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.app.get("/health")
        async def health():
            return {
                "status": "ok",
                "app": "TabPet",
                "version": "1.1.0",
                "ai_offline": self.ai.is_offline,
                "local_only": self.ai.local_only,
                "model_name": self.ai.model_name
            }

        @self.app.get("/token")
        async def get_token():
            return {"auth_token": self.config.get("auth_token")}

        @self.app.post("/judge")
        async def judge_endpoint(req: JudgeReq):
            goal = req.goal or self.config.get("current_goal", "")
            result = await self.ai.judge_tab(req.url, req.title, goal)
            return result

        @self.app.post("/plea")
        async def plea_endpoint(req: PleaReq):
            goal = req.goal or self.config.get("current_goal", "")
            result = await self.ai.judge_plea(req.plea, req.url, req.title, goal)
            # Update pet mood
            summary = self.memory.get_notes_summary()
            self.bridge.trust_updated.emit(summary["trust_score"], summary["mood"])
            return result

        @self.app.get("/notes")
        async def notes_endpoint():
            summary = self.memory.get_notes_summary()
            summary.update({
                "offline_mode": self.ai.is_offline,
                "local_only": self.ai.local_only,
                "current_goal": self.config.get("current_goal", "")
            })
            return summary

        @self.app.post("/goal")
        async def goal_endpoint(req: GoalReq):
            self.config.set("current_goal", req.goal)
            return {"status": "ok", "goal": req.goal}

        @self.app.post("/settings/local_only")
        async def local_only_endpoint(req: LocalOnlyReq):
            self.ai.local_only = req.local_only
            self.config.set("local_only", req.local_only)
            return {"status": "ok", "local_only": req.local_only}

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
            summary = self.memory.get_notes_summary()
            await websocket.send_json({
                "type": "init",
                "config": {
                    "tab_offset_x": self.config.get("tab_offset_x"),
                    "tab_offset_y": self.config.get("tab_offset_y"),
                    "max_tab_width": self.config.get("max_tab_width"),
                    "pet_name": self.config.get("pet_name"),
                    "current_goal": self.config.get("current_goal", ""),
                    "trust_score": summary["trust_score"],
                    "mood": summary["mood"],
                    "ai_offline": self.ai.is_offline,
                    "local_only": self.ai.local_only
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
            left = int(data.get("left", 0))
            top = int(data.get("top", 0))
            width = int(data.get("width", 1200))
            height = int(data.get("height", 800))
            tab_count = int(data.get("tab_count", 1))
            self.bridge.bounds_received.emit(left, top, width, height, tab_count)

        elif msg_type == "tab_activated":
            tab_index = int(data.get("tab_index", 0))
            tab_count = int(data.get("tab_count", 1))
            self.bridge.tab_activated.emit(tab_index, tab_count)

        elif msg_type == "set_goal":
            goal = str(data.get("goal", ""))
            self.config.set("current_goal", goal)
            print(f"[Server] Focus goal updated: '{goal}'")

        elif msg_type == "blocked_tab_opened":
            tab_id = int(data.get("tab_id", 0))
            tab_index = int(data.get("tab_index", 0))
            tab_count = int(data.get("tab_count", 1))
            url = str(data.get("url", ""))
            title = str(data.get("title", ""))
            blocks_today = int(data.get("blocks_today", 1))
            streak_days = int(data.get("streak_days", 1))
            goal = str(data.get("goal", "") or self.config.get("current_goal", ""))
            self.bridge.blocked_tab_opened.emit(
                tab_id, tab_index, tab_count, url, title, blocks_today, streak_days, goal
            )

        elif msg_type == "judge_tab":
            req_id = data.get("req_id")
            url = str(data.get("url", ""))
            title = str(data.get("title", ""))
            goal = str(data.get("goal", "") or self.config.get("current_goal", ""))
            result = await self.ai.judge_tab(url, title, goal)
            await websocket.send_json({
                "type": "judge_result",
                "req_id": req_id,
                **result
            })

        elif msg_type == "plea_request":
            req_id = data.get("req_id")
            tab_id = int(data.get("tab_id", 0))
            url = str(data.get("url", ""))
            title = str(data.get("title", ""))
            plea = str(data.get("plea", ""))
            goal = str(data.get("goal", "") or self.config.get("current_goal", ""))
            result = await self.ai.judge_plea(plea, url, title, goal)
            summary = self.memory.get_notes_summary()
            self.bridge.trust_updated.emit(summary["trust_score"], summary["mood"])
            await websocket.send_json({
                "type": "plea_result",
                "req_id": req_id,
                "tab_id": tab_id,
                **result
            })

        elif msg_type == "ping":
            await websocket.send_json({"type": "pong"})

    async def broadcast_tab_closed(self, tab_id: int, roast_text: str = "") -> None:
        """Notifies the extension that the pet has completed closing a tab."""
        dead_connections = set()
        msg = json.dumps({"type": "tab_closed", "tab_id": tab_id, "roast": roast_text})
        for ws in self.active_connections:
            try:
                await ws.send_text(msg)
            except Exception:
                dead_connections.add(ws)
        self.active_connections.difference_update(dead_connections)

    def notify_tab_closed(self, tab_id: int, roast_text: str = "") -> None:
        """Thread-safe trigger to broadcast tab closure to extension."""
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast_tab_closed(tab_id, roast_text), self._loop)

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

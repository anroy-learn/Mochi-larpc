import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

MEMORY_DIR = Path.home() / ".tabpet"
MEMORY_FILE = MEMORY_DIR / "memory.json"

DEFAULT_MEMORY: Dict[str, Any] = {
    "trust_score": 50,  # 0 to 100
    "events": [],
    "stats": {
        "blocks": 0,
        "saves": 0,
        "pleas_granted": 0,
        "pleas_denied": 0
    }
}


class MemoryStore:
    """Persistent storage for pet memory, recent browsing events, and trust score."""

    def __init__(self):
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        self.data: Dict[str, Any] = dict(DEFAULT_MEMORY)
        self.load()

    def load(self) -> None:
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.data.update(saved)
            except Exception as e:
                print(f"[Memory] Could not load memory.json: {e}. Using defaults.")

    def save(self) -> None:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[Memory] Could not save memory.json: {e}")

    def get_trust_score(self) -> int:
        return int(self.data.get("trust_score", 50))

    def update_trust(self, delta: int) -> int:
        score = self.get_trust_score() + delta
        score = max(0, min(100, score))
        self.data["trust_score"] = score
        self.save()
        return score

    def record_event(
        self,
        domain: str,
        title: str,
        verdict: str,
        plea: Optional[str] = None,
        grant_minutes: int = 0,
        reason: str = ""
    ) -> None:
        event = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "domain": domain,
            "title": title[:60] if title else "",
            "verdict": verdict,  # "allow" | "block" | "plea_granted" | "plea_denied"
            "plea": plea[:100] if plea else None,
            "grant_minutes": grant_minutes,
            "reason": reason[:100] if reason else ""
        }
        events = self.data.get("events", [])
        events.append(event)
        # Keep last 100 events
        if len(events) > 100:
            events = events[-100:]
        self.data["events"] = events

        stats = self.data.setdefault("stats", {"blocks": 0, "saves": 0, "pleas_granted": 0, "pleas_denied": 0})
        if verdict == "allow" or verdict == "plea_granted":
            stats["saves"] = stats.get("saves", 0) + 1
        if verdict == "block" or verdict == "plea_denied":
            stats["blocks"] = stats.get("blocks", 0) + 1
        if verdict == "plea_granted":
            stats["pleas_granted"] = stats.get("pleas_granted", 0) + 1
        elif verdict == "plea_denied":
            stats["pleas_denied"] = stats.get("pleas_denied", 0) + 1

        self.save()

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        events = self.data.get("events", [])
        return events[-limit:]

    def get_notes_summary(self) -> Dict[str, Any]:
        stats = self.data.get("stats", {})
        trust = self.get_trust_score()
        mood = "neutral"
        if trust >= 70:
            mood = "proud"
        elif trust < 40:
            mood = "suspicious"

        return {
            "trust_score": trust,
            "mood": mood,
            "blocks": stats.get("blocks", 0),
            "saves": stats.get("saves", 0),
            "pleas_granted": stats.get("pleas_granted", 0),
            "pleas_denied": stats.get("pleas_denied", 0),
            "recent_events": self.get_recent_events(8)
        }

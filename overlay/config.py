import json
import os
import secrets
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    "auth_token": "",
    "host": "127.0.0.1",
    "port": 8765,
    "tab_offset_x": 80,       # Distance from window left to first tab (clears macOS window buttons)
    "tab_offset_y": 14,       # Vertical offset where pet rests on the tab strip
    "max_tab_width": 240,     # Maximum Chrome tab width
    "min_tab_width": 45,      # Minimum tab width when many tabs are open
    "tab_right_margin": 120,  # Space reserved for tab search, new tab (+), window controls
    "pet_name": "Mochi",
    "pet_color": "#FF8A65",   # Warm cute coral
    "pet_secondary": "#FFD54F", # Soft sunny accent
    "sound_enabled": True,
}

CONFIG_DIR = Path.home() / ".tabpet"
CONFIG_FILE = CONFIG_DIR / "config.json"


class ConfigManager:
    """Manages application configuration, calibration settings, and secure auth token."""

    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                print(f"[Config] Error loading config: {e}. Using defaults.")

        # Ensure a secure token is generated if not present
        if not self.config.get("auth_token"):
            self.config["auth_token"] = secrets.token_hex(16)
            self.save()

    def save(self) -> None:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            
            # Sync token directly into extension/config.json for automatic zero-config extension auth
            ext_config = Path(__file__).resolve().parent.parent / "extension" / "config.json"
            if ext_config.parent.exists():
                with open(ext_config, "w", encoding="utf-8") as f:
                    json.dump({
                        "authToken": self.config.get("auth_token", ""),
                        "wsPort": self.config.get("port", 8765)
                    }, f, indent=2)
        except Exception as e:
            print(f"[Config] Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value
        self.save()

    def calculate_tab_x(self, window_width: int, tab_index: int, tab_count: int) -> float:
        """
        Calculates the estimated horizontal center of a tab given window width,
        current tab count, and tab index.
        """
        offset_x = self.get("tab_offset_x", 80)
        max_w = self.get("max_tab_width", 240)
        min_w = self.get("min_tab_width", 45)
        right_margin = self.get("tab_right_margin", 120)

        tab_count = max(1, tab_count)
        available_width = max(100, window_width - offset_x - right_margin)
        tab_width = min(float(max_w), max(float(min_w), available_width / tab_count))

        # Center of tab[tab_index]
        return offset_x + (tab_index * tab_width) + (tab_width / 2.0)

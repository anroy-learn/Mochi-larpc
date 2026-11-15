# 🐾 Tab Pet - Desktop Chrome Tab Guardian & Pomodoro Companion

A cute procedural desktop pet that lives directly on top of your Google Chrome tab bar. During Pomodoro focus sessions, it monitors your browsing: if you open a blocked tab, the pet covers the distraction, walks over across the tab strip, and closes it!

## ✨ Features
- **Procedural Desktop Overlay**: Smooth, transparent, always-on-top, click-through overlay window built with PySide6. The pet squashes, stretches, hops, blinks, and naps procedurally without needing heavy external sprite assets.
- **Chrome Tab Bar Follower**: Dynamically aligns itself with the active Chrome window's tab strip as the browser moves or resizes.
- **Local WebSocket Bridge**: FastAPI + WebSocket server bound to `127.0.0.1` with token-based authentication.
- **MV3 Chrome Extension**:
  - Focus session enforcement using `chrome.alarms` (safe against service worker sleep).
  - Domain & URL blocklist.
  - Immediate page blanking ("Pet is on its way...") when a blocked tab is opened.
  - Multi-tab walk & close queue.
- **Tab Calibration UI**: Visual sliders for tab width, offset X, and offset Y.
- **Privacy First**: Only URL paths (without query parameters) and titles are inspected. Page content is never transmitted.
- **Productivity Stats**: Focus minutes, blocks prevented, and daily streaks.

## 📁 Project Structure
```
tab-pet/
├── overlay/               # PySide6 desktop overlay & server
│   ├── app.py             # Main entry point: PySide6 application
│   ├── pet.py             # Procedural pet renderer (shapes, eyes, squash/stretch)
│   ├── server.py          # FastAPI + WebSocket server (127.0.0.1, auth token)
│   ├── window.py          # Transparent, click-through overlay window
│   ├── calibration.py     # Tab position calibration dialog
│   └── state.py           # Shared state & configuration management
├── extension/             # Chrome Extension (Manifest V3)
│   ├── manifest.json      # Extension manifest
│   ├── background.js      # Service worker (alarms, WebSocket client, tab tracking)
│   ├── content/
│   │   ├── overlay.js     # Blocker screen injected into blocked tabs
│   │   └── overlay.css    # "Pet is coming" full-page styling
│   ├── popup/
│   │   ├── popup.html     # Pomodoro timer, stats, & quick toggles
│   │   ├── popup.js       # Popup logic & timer controls
│   │   └── popup.css      # Popup styling
│   ├── options/
│   │   ├── options.html   # Blocklist editor, calibration settings, timer intervals
│   │   ├── options.js     # Settings storage & sync
│   │   └── options.css    # Options page styling
│   └── icons/             # Extension icons
├── requirements.txt       # Python dependencies
├── .gitignore             # Ignored directories and files
└── README.md              # Project documentation
```

## 🚀 Setup & Testing Steps
1. **Step 1: Overlay & Idle Loop** — PySide6 transparent window following Chrome window bounds.
2. **Step 2: Extension Bridge** — WebSocket connection between MV3 extension and overlay server.
3. **Step 3: Pomodoro & Walk-and-Close** — Blocklist enforcement, cover overlay, and tab closing queue.
4. **Step 4: Polish & Audio** — Sound effects, mute toggle, stats, and visual feedback.

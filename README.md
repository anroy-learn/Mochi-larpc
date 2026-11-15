# 🐾 Tab Pet - Desktop Chrome Tab Guardian & Pomodoro Companion

A cute procedural desktop pet that lives directly on top of your Google Chrome tab bar. During Pomodoro focus sessions, it monitors your browsing: if you open a blocked tab, the pet covers the distraction, walks over across the tab strip, and stomps it shut!

---

## ✨ Features
- **Procedural Desktop Overlay**: Smooth, transparent, always-on-top, click-through overlay window built with PySide6. The pet squashes, stretches, hops, blinks, and naps procedurally without needing heavy external sprite assets.
- **Chrome Tab Bar Follower**: Dynamically aligns itself with the active Chrome window's tab strip as the browser moves or resizes.
- **Local WebSocket Bridge**: FastAPI + WebSocket server bound strictly to `127.0.0.1` with token-based authentication.
- **MV3 Chrome Extension**:
  - Focus session enforcement using `chrome.alarms` (safe against service worker sleep).
  - Domain & URL blocklist (one per line).
  - Immediate page blanking ("Tab Pet is coming!") when a blocked tab is opened.
  - Multi-tab walk & close queue.
- **Tab Calibration UI**: Visual sliders for tab width, offset X, and offset Y.
- **Privacy First**: Only URL paths (without query parameters) and titles are inspected. Page content is never transmitted.
- **Productivity Stats & Audio**: Focus minutes, blocks prevented, daily streak, and procedural Web Audio chimes with mute toggle.

---

## 📁 Project Structure
```text
tab-pet/
├── overlay/               # PySide6 desktop overlay & server
│   ├── config.py          # Token generator, calibration offsets & config storage
│   ├── pet.py             # Procedural pet renderer (shapes, eyes, squash/stretch)
│   ├── server.py          # FastAPI + WebSocket server (127.0.0.1, auth token)
│   ├── window.py          # Transparent, click-through overlay window
│   └── calibration.py     # Tab position calibration dialog
├── extension/             # Chrome Extension (Manifest V3)
│   ├── manifest.json      # Extension manifest
│   ├── background/
│   │   └── service_worker.js # Service worker (alarms, WebSocket client, tab tracking)
│   ├── content/
│   │   ├── cover.js       # Blocker screen injected into blocked tabs
│   │   └── cover.css      # "Pet is coming" full-page styling
│   ├── popup/
│   │   ├── popup.html     # Pomodoro timer, stats, & quick toggles
│   │   ├── popup.css
│   │   └── popup.js
│   ├── options/
│   │   ├── options.html   # Blocklist editor, session duration, auth token
│   │   ├── options.css
│   │   └── options.js
│   └── icons/             # Procedurally generated PNG icons (16, 48, 128)
├── requirements.txt       # Python dependencies
├── run.py                 # Application launcher
└── README.md
```

---

## 🚀 How to Run and Test Each Step

### 1. Start the Desktop Pet Overlay
Activate the virtual environment and run `run.py`:

```bash
cd /Users/angelroy/.gemini/antigravity/scratch/tab-pet
source venv/bin/activate
python run.py
```

* **Step 1 Test (Overlay & Click-Through)**:
  - The transparent pet overlay will appear at the top of your screen.
  - Test click-through: clicking on anything directly underneath the pet passes clicks through transparently to the app below.
  - Notice the pet squashes, breathes, blinks, looks left/right, and takes naps (with floating "z" particles).
  - *(Optional)* Run with `--demo` (`python run.py --demo`) to watch the pet hop between simulated tabs.
  - *(Optional)* Run with `--calibrate` (`python run.py --calibrate`) to adjust horizontal/vertical offsets live.

---

### 2. Load the Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** in the top right.
3. Click **Load unpacked** and select the [`tab-pet/extension`](file:///Users/angelroy/.gemini/antigravity/scratch/tab-pet/extension) directory.
4. The cute 🐾 Tab Pet icon will appear in your Chrome toolbar.

* **Step 2 Test (Extension Connection & Tab Hopping)**:
  - Click the 🐾 extension icon in Chrome toolbar. You will see `Overlay Connected` in green.
  - Move or resize the Chrome window: the desktop overlay window follows the Chrome window.
  - Click between different Chrome tabs: the pet hops across the tab bar directly onto the tab you switch to.

---

### 3. Test Blocklist & Walk-and-Close (Core Demo)
1. Click the 🐾 extension icon and click **Start Focus** (starts a Pomodoro work session).
2. Open a new tab and navigate to any blocked website (e.g. `youtube.com`, `reddit.com`, `x.com`).
3. **What happens**:
   - The page immediately displays the cute fullscreen cover: *"Tab Pet is coming! This site is blocked during your Focus Session..."*.
   - The desktop pet walks across your tab bar to that tab's position.
   - The pet plays its stomp/pounce animation!
   - The extension automatically closes the blocked tab.
   - If you quickly open multiple blocked tabs, the pet queues them and closes them one by one.

---

### 4. Polish, Settings & Stats
- **Blocklist & Durations**: Click the ⚙️ gear icon in the popup (or open Extension Options) to paste custom domains (one per line) or change Focus/Break lengths.
- **Audio & Mute Toggle**: Toggle the sound effects checkbox in the popup or calibration screen.
- **Productivity Stats**: Check your daily prevented blocks counter, focus minutes, and streak in the extension popup.

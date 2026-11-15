# 🐾 Tab Pet - Desktop Chrome Tab Guardian & AI Focus Companion

A cute procedural desktop pet (**Mochi**) that lives directly on top of your Google Chrome tab bar. During Pomodoro focus sessions, it monitors your browsing: if you open an unhelpful tab, the pet evaluates it against your focus goal, walks over across the tab strip, and stomps it shut with a witty roast!

---

## 🔒 Privacy & Safety Guarantee

- **Sanitized URLs Only**: Only the domain and pathname (e.g. `youtube.com/watch`) and the page title are processed. Query parameters, tokens, search arguments, hashes, and page contents are **never** inspected, transmitted, or logged.
- **Local Key Handling**: Gemini is called **only** from the local Python app on your machine—never from the browser extension. Your `GOOGLE_API_KEY` is read from `.env` in the project root and is never printed, logged, or committed.
- **Local-Only Mode**: A toggle in the popup lets you disable AI calls entirely and use deterministic rules-based evaluation and canned banter.
- **Strict Content Safety**: AI roast lines enforce playful productivity banter only—never jokes about bodies, appearance, identity, or slurs.

---

## ✨ Features

1. **Compact Floating Character Window (76×76px)**:
   - Lives as a transparent, always-on-top desktop character resting on the active Chrome tab.
   - 100% immune to click blocking: only the 76px area directly beneath the pet is occupied; the rest of the tab bar and browser window are completely uncovered.
   - Kinematic walking across the screen along the tab bar as you switch tabs.
   - Interactive: click to pet (squashes happily & floats hearts `♥`) or drag anywhere on screen.

2. **🎯 Focus Goal**:
   - Set your current task in the popup (e.g. *"Studying algorithms"*, *"Writing physics paper"*).
   - Sent to the AI companion to contextualize all browsing judgments.

3. **⚖️ Smart Judge (Mixed Domains)**:
   - Domains like `youtube.com` and `reddit.com` contain both educational tutorials and distracting rabbit holes.
   - The Smart Judge evaluates whether the opened page directly aids your Focus Goal.
   - **Thinking Cover**: Displays a brief "Pet is thinking..." screen (up to 2 seconds).
   - **Allowed**: If the page is helpful, the cover disappears and shows a toast: *"🐾 Pet says OK: <reason>"*.
   - **Always-Block List**: Sites like social media (`x.com`, `tiktok.com`) skip AI and are closed immediately.

4. **🗯️ Roast Speech Bubble**:
   - When closing a tab, Mochi delivers a playful, custom roast (max 15 words) reflecting the tab title, blocks today, streak, and focus goal.
   - Generated asynchronously while the pet walks across the tab bar so it is ready on arrival.
   - Displays in a floating speech bubble above Mochi's head.
   - Falls back to canned lines if AI is offline or takes > 2.0s.

5. **🤝 Plea Bargain & Trust Score**:
   - If a tab is blocked, you can plead your case directly to Mochi from the cover screen.
   - Gemini arbitrates the plea against your goal and previous history, granting 0 to 10 minutes of temporary grace.
   - **Trust Score (0–100)**: Honest, granted pleas raise your trust score; denied pleas lower it.
   - **Adaptive Mood**: Mochi's facial expressions reflect your trust score:
     - High trust (≥ 70%): Proud twinkle eyes (`★`) and happy bounces.
     - Medium trust (40–69%): Neutral round eyes.
     - Low trust (< 40%): Suspicious narrowed squint (`¬ ¬`).

6. **📝 Pet's Notes & Memory**:
   - Persistent event log stored locally in `~/.tabpet/memory.json`.
   - Popup displays trust score, blocks, saves, and recent history.

7. **⚡ 2.0s Hard Fallback & Offline Mode**:
   - Every AI call has a strict 2.0-second timeout. If Gemini takes longer or network fails, Tab Pet falls back to rules-based blocking and canned lines without stalling your workflow.

---

## 📁 Project Structure

```text
tab-pet/
├── overlay/               # PySide6 desktop overlay & server
│   ├── config.py          # Calibration offsets, auth token & config storage
│   ├── ai.py              # Gemini AI controller (Judge, Roast, Plea, Auto-Model discovery)
│   ├── memory.py          # Persistent memory store (~/.tabpet/memory.json) & Trust score
│   ├── pet.py             # Procedural pet renderer (eyes, ears, mood, speech bubble)
│   ├── server.py          # FastAPI + WebSocket server (127.0.0.1:8765)
│   ├── window.py          # Compact floating window (76x76) & kinematics
│   ├── tracker.py         # Native macOS Chrome tracker
│   └── calibration.py     # Interactive offset calibration sliders
├── extension/             # Chrome Extension (Manifest V3)
│   ├── manifest.json      # Extension manifest
│   ├── background/
│   │   └── service_worker.js # Pomodoro timer, Smart Judge dispatcher, WebSocket client
│   ├── content/
│   │   ├── cover.js       # Thinking cover, OK toast, and Plea Bargain UI
│   │   └── cover.css      # Cover styling
│   ├── popup/
│   │   ├── popup.html     # Focus goal input, Pomodoro timer, Pet's Notes & Local toggle
│   │   ├── popup.css
│   │   └── popup.js
│   ├── options/
│   │   ├── options.html   # Always-blocked list, Smart Judge mixed list, timers
│   │   ├── options.css
│   │   └── options.js
│   └── icons/             # Procedurally generated PNG icons
├── .env                   # GOOGLE_API_KEY and auto-discovered MODEL_NAME (gitignored)
├── requirements.txt       # Python dependencies (PySide6, google-genai, fastapi, etc.)
├── run.py                 # Application launcher
└── README.md
```

---

## 🚀 How to Test Each Feature

### Step 0: Setup `.env`
Ensure [.env](file:///Users/angelroy/.gemini/antigravity/scratch/tab-pet/.env) contains your Google API key:
```bash
GOOGLE_API_KEY=your_key_here
MODEL_NAME=
```
*(If `MODEL_NAME` is left blank, Tab Pet automatically discovers and connects to the current Flash model on startup and saves it).*

---

### Test A: `.env` + Endpoint + Smart Judge with Fallback
1. **Launch the desktop pet**:
   ```bash
   cd /Users/angelroy/.gemini/antigravity/scratch/tab-pet
   source venv/bin/activate
   python -u run.py
   ```
2. **Open Chrome Extension popup**:
   - Enter a Focus Goal: `Learn Python algorithms`.
   - Click **Start Focus**.
3. **Test Mixed Domain Allowance**:
   - Open a relevant YouTube video or tutorial (e.g. search Python Algorithms on YouTube).
   - Notice the "Pet is thinking..." cover displays briefly (< 1s), then clears with a toast:
     *"🐾 Pet says OK: <reason>"*.
4. **Test Fallback / Offline Mode**:
   - In the popup, check **Local Only (Disable AI)**.
   - The badge updates to "Local Only".
   - Now any mixed site falls back immediately to deterministic rules-based blocking without waiting.

---

### Test B: Roast Speech Bubble
1. During an active Focus session, open a distraction tab (e.g. `twitter.com`, `tiktok.com`, or an unrelated entertainment video).
2. The page is covered with *"Tab Pet is coming!"*.
3. Watch your Chrome tab bar: Mochi will turn and walk across the tab strip to that tab.
4. Mochi stomps on the tab, and a **speech bubble appears above Mochi's head** with a snappy, safe roast line tailored to the tab title and your goal!
5. The tab closes automatically.

---

### Test C: Plea Bargain + Trust Score + Memory
1. Open a blocked tab during a Focus session.
2. In the blocked cover screen, look at the **"Plead your case"** box:
   - Type an honest plea: `Need to look up documentation for my algorithm assignment`.
   - Click **Plead to Mochi**.
3. Gemini weighs your plea against your focus goal:
   - If granted: green banner displays *"🎉 Plea Approved! Granted 5m"*, the cover disappears, and you receive a temporary grace pass!
   - Your Trust Score increases in the popup (+2%).
4. If you enter an excuse like `Just want to watch memes`:
   - Mochi denies the plea, the trust score decreases (-3%), and Mochi stomps the tab shut!
5. In the popup, open **Pet's Notes** to see your current Trust Score, total saves, blocks, and event log. Notice Mochi's facial expressions change (proud sparkles vs. suspicious squint).

---

### Test D: Verification & Clean State
- Check git status to ensure zero secrets or temp files are tracked:
  ```bash
  git status --short
  ```
- All state is verified and clean!

/**
 * Tab Pet - Background Service Worker (Manifest V3)
 * Handles WebSocket connection with PySide6 desktop overlay,
 * Pomodoro timers via chrome.alarms, and blocklist enforcement.
 */

let ws = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 10000;

// Track tabs currently being closed by the pet to avoid duplicate messages
const pendingBlockedTabs = new Set();

// Default storage state
const DEFAULT_STATE = {
  authToken: "",
  wsPort: 8765,
  pomodoroMode: "idle", // 'idle' | 'work' | 'break'
  pomodoroEndTime: 0,
  workDuration: 25,     // minutes
  breakDuration: 5,     // minutes
  soundEnabled: true,
  blockedDomains: [
    "youtube.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "netflix.com",
    "twitch.tv"
  ],
  stats: {
    blocksToday: 0,
    focusMinutesToday: 0,
    streakDays: 1,
    lastDate: new Date().toISOString().slice(0, 10)
  }
};

// -------------------------------------------------------------
// 1. Initialization & Storage Setup
// -------------------------------------------------------------
chrome.runtime.onInstalled.addListener(async () => {
  console.log("[TabPet] Extension installed.");
  const existing = await chrome.storage.local.get(null);
  const toSet = {};
  for (const [k, v] of Object.entries(DEFAULT_STATE)) {
    if (existing[k] === undefined) {
      toSet[k] = v;
    }
  }

  // Try auto-fetching token from local Python server if empty
  if (!existing.authToken) {
    try {
      const resp = await fetch("http://127.0.0.1:8765/token");
      if (resp.ok) {
        const data = await resp.json();
        if (data.auth_token) toSet.authToken = data.auth_token;
      }
    } catch (_) {}
  }

  if (Object.keys(toSet).length > 0) {
    await chrome.storage.local.set(toSet);
  }

  initWebSocket();
});

chrome.runtime.onStartup.addListener(() => {
  initWebSocket();
});

// Immediate execution when service worker loads/wakes up
initWebSocket();

// -------------------------------------------------------------
// 2. WebSocket Client
// -------------------------------------------------------------
async function initWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  const { authToken, wsPort } = await chrome.storage.local.get(["authToken", "wsPort"]);
  const port = wsPort || 8765;

  let token = authToken;
  if (!token) {
    // Attempt auto-discovery
    try {
      const resp = await fetch(`http://127.0.0.1:${port}/token`);
      if (resp.ok) {
        const data = await resp.json();
        token = data.auth_token;
        await chrome.storage.local.set({ authToken: token });
      }
    } catch (_) {}
  }

  const wsUrl = `ws://127.0.0.1:${port}/ws${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  console.log(`[TabPet] Connecting to overlay: ${wsUrl}`);

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[TabPet] Connected to Python Desktop Overlay!");
      reconnectDelay = 1000;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      // Immediately sync current window coordinates
      sendCurrentWindowBounds();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerMessage(msg);
      } catch (e) {
        console.error("[TabPet] WS message parse error:", e);
      }
    };

    ws.onclose = (e) => {
      console.warn(`[TabPet] WS closed (code: ${e.code}). Reconnecting in ${reconnectDelay}ms...`);
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.warn("[TabPet] WS error, closing socket.");
      ws.close();
    };
  } catch (err) {
    console.error("[TabPet] Connection exception:", err);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectDelay = Math.min(reconnectDelay * 1.5, MAX_RECONNECT_DELAY);
    initWebSocket();
  }, reconnectDelay);
}

function sendWs(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

function handleServerMessage(msg) {
  if (msg.type === "tab_closed") {
    // Pet has stomped and closed the tab!
    const tabId = msg.tab_id;
    if (tabId) {
      console.log(`[TabPet] Closing tab ${tabId} per pet command.`);
      chrome.tabs.remove(tabId).catch(() => {});
      pendingBlockedTabs.delete(tabId);
    }
  } else if (msg.type === "init") {
    console.log("[TabPet] Received pet overlay config:", msg.config);
  }
}

// -------------------------------------------------------------
// 3. Browser Window & Tab Tracking (Following Chrome)
// -------------------------------------------------------------
async function sendCurrentWindowBounds() {
  try {
    let win = await chrome.windows.getLastFocused({ populate: true, windowTypes: ["normal"] });
    if (!win || win.left === undefined) {
      const wins = await chrome.windows.getAll({ populate: true, windowTypes: ["normal"] });
      win = wins && wins.length > 0 ? wins[0] : null;
    }
    if (!win || win.left === undefined) return;
    if (win.state === "minimized" || win.left < -2000 || win.top < -2000 || win.width < 200) return;

    const tabs = win.tabs || [];
    const activeTab = tabs.find((t) => t.active);
    const activeIndex = activeTab ? activeTab.index : 0;

    sendWs({
      type: "window_bounds",
      left: win.left,
      top: win.top,
      width: win.width,
      height: win.height,
      tab_count: tabs.length,
      active_tab_index: activeIndex
    });
  } catch (_) {}
}

// Window bounds changes (moving or resizing Chrome)
chrome.windows.onBoundsChanged.addListener(() => {
  sendCurrentWindowBounds();
});

chrome.windows.onFocusChanged.addListener((windowId) => {
  if (windowId !== chrome.windows.WINDOW_ID_NONE) {
    sendCurrentWindowBounds();
  }
});

// Tab navigation / activation (pet hops to tab)
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    const win = await chrome.windows.get(tab.windowId, { populate: true });
    sendWs({
      type: "tab_activated",
      tab_index: tab.index,
      tab_count: (win.tabs || []).length
    });
  } catch (_) {}
});

chrome.tabs.onCreated.addListener(() => {
  sendCurrentWindowBounds();
});

chrome.tabs.onRemoved.addListener((tabId) => {
  pendingBlockedTabs.delete(tabId);
  sendCurrentWindowBounds();
});

// -------------------------------------------------------------
// 4. Pomodoro Focus Session Management (chrome.alarms)
// -------------------------------------------------------------
const ALARM_NAME = "tab_pet_pomodoro";

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) return;

  const data = await chrome.storage.local.get(["pomodoroMode", "workDuration", "breakDuration", "stats"]);
  const mode = data.pomodoroMode;
  const stats = data.stats || DEFAULT_STATE.stats;

  const todayStr = new Date().toISOString().slice(0, 10);
  if (stats.lastDate !== todayStr) {
    stats.lastDate = todayStr;
    stats.blocksToday = 0;
    stats.focusMinutesToday = 0;
  }

  if (mode === "work") {
    // Work finished! Add stats and switch to break
    stats.focusMinutesToday += Number(data.workDuration || 25);
    const breakMinutes = Number(data.breakDuration || 5);
    const nextEndTime = Date.now() + breakMinutes * 60 * 1000;

    await chrome.storage.local.set({
      pomodoroMode: "break",
      pomodoroEndTime: nextEndTime,
      stats
    });

    chrome.alarms.create(ALARM_NAME, { when: nextEndTime });
    console.log("[TabPet] Pomodoro work session completed! Break time.");
  } else if (mode === "break") {
    // Break finished! Idle
    await chrome.storage.local.set({
      pomodoroMode: "idle",
      pomodoroEndTime: 0
    });
    console.log("[TabPet] Pomodoro break completed!");
  }
});

// -------------------------------------------------------------
// 5. Blocklist Enforcement & Tab Walking Stomp
// -------------------------------------------------------------
function isBlockedUrl(rawUrl, blockedDomains) {
  if (!rawUrl || !rawUrl.startsWith("http")) return false;
  try {
    const urlObj = new URL(rawUrl);
    const hostname = urlObj.hostname.toLowerCase();
    return blockedDomains.some((domain) => {
      const clean = domain.trim().toLowerCase();
      if (!clean) return false;
      return hostname === clean || hostname.endsWith("." + clean);
    });
  } catch {
    return false;
  }
}

// Clean sanitized URL (privacy requirement: no query parameters or hashes)
function sanitizeUrl(rawUrl) {
  try {
    const urlObj = new URL(rawUrl);
    return `${urlObj.origin}${urlObj.pathname}`;
  } catch {
    return rawUrl;
  }
}

async function handlePotentialBlockedTab(tab) {
  if (!tab || !tab.id || !tab.url) return;
  if (pendingBlockedTabs.has(tab.id)) return;

  const { pomodoroMode, blockedDomains, stats } = await chrome.storage.local.get([
    "pomodoroMode",
    "blockedDomains",
    "stats"
  ]);

  // Only block during active 'work' sessions
  if (pomodoroMode !== "work") return;

  const domains = blockedDomains || DEFAULT_STATE.blockedDomains;
  if (!isBlockedUrl(tab.url, domains)) return;

  // Mark tab as pending blocked close
  pendingBlockedTabs.add(tab.id);

  // 1. Immediately blank/cover the tab with warning UI
  try {
    await chrome.scripting.insertCSS({
      target: { tabId: tab.id },
      files: ["content/cover.css"]
    });
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content/cover.js"]
    });
  } catch (err) {
    console.warn("[TabPet] Could not inject cover overlay:", err);
  }

  // 2. Increment stats
  const currentStats = stats || DEFAULT_STATE.stats;
  currentStats.blocksToday = (currentStats.blocksToday || 0) + 1;
  await chrome.storage.local.set({ stats: currentStats });

  // 3. Obtain window information to calculate tab index
  let tabCount = 1;
  try {
    const win = await chrome.windows.get(tab.windowId, { populate: true });
    tabCount = (win.tabs || []).length;
  } catch (_) {}

  // 4. Send command to Desktop Pet overlay
  const cleanUrl = sanitizeUrl(tab.url);
  sendWs({
    type: "blocked_tab_opened",
    tab_id: tab.id,
    tab_index: tab.index,
    tab_count: tabCount,
    url: cleanUrl,
    title: tab.title || ""
  });

  // 5. Fail-safe timeout: close tab after 4.5 seconds if WS or overlay fails
  setTimeout(() => {
    if (pendingBlockedTabs.has(tab.id)) {
      chrome.tabs.remove(tab.id).catch(() => {});
      pendingBlockedTabs.delete(tab.id);
    }
  }, 4500);
}

// Listen to tab updates (page load / navigation)
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading" && tab.url) {
    handlePotentialBlockedTab(tab);
  }
});

// Listen to webNavigation before navigation starts
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return; // Top-level frame only
  try {
    const tab = await chrome.tabs.get(details.tabId);
    handlePotentialBlockedTab({ ...tab, url: details.url });
  } catch (_) {}
});

// Periodic ping / connection watchdog
setInterval(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    initWebSocket();
  } else {
    sendWs({ type: "ping" });
  }
}, 15000);

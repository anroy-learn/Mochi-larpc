/**
 * Tab Pet - Background Service Worker (Manifest V3)
 * Handles WebSocket connection with PySide6 desktop overlay,
 * Pomodoro timers via chrome.alarms, Smart Judge, and Plea Bargaining.
 */

let ws = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
const MAX_RECONNECT_DELAY = 10000;

// Track tabs currently being closed by the pet to avoid duplicate messages
const pendingBlockedTabs = new Set();

// Temporary passes granted through plea bargaining (tabId -> expirationTimestamp)
const temporaryPasses = new Map();

// Default storage state
const DEFAULT_STATE = {
  authToken: "",
  wsPort: 8765,
  pomodoroMode: "idle", // 'idle' | 'work' | 'break'
  pomodoroEndTime: 0,
  workDuration: 25,     // minutes
  breakDuration: 5,     // minutes
  soundEnabled: true,
  focusGoal: "",
  localOnly: false,
  mixedDomains: [
    "youtube.com",
    "reddit.com"
  ],
  blockedDomains: [
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
  chrome.storage.local.set({ pomodoroMode: "idle", pomodoroEndTime: 0 });
  initWebSocket();
});

initWebSocket();

// -------------------------------------------------------------
// 2. WebSocket Client
// -------------------------------------------------------------
async function initWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  let { authToken, wsPort } = await chrome.storage.local.get(["authToken", "wsPort"]);

  // 1. Check bundled extension/config.json
  if (!authToken) {
    try {
      const resp = await fetch(chrome.runtime.getURL("config.json"));
      if (resp.ok) {
        const cfg = await resp.json();
        if (cfg.authToken) {
          authToken = cfg.authToken;
          wsPort = cfg.wsPort || 8765;
          await chrome.storage.local.set({ authToken, wsPort });
        }
      }
    } catch (_) {}
  }

  // 2. Fallback: query local server /token
  const port = wsPort || 8765;
  if (!authToken) {
    try {
      const resp = await fetch(`http://127.0.0.1:${port}/token`);
      if (resp.ok) {
        const data = await resp.json();
        authToken = data.auth_token;
        await chrome.storage.local.set({ authToken });
      }
    } catch (_) {}
  }

  const wsUrl = `ws://127.0.0.1:${port}/ws${authToken ? `?token=${encodeURIComponent(authToken)}` : ""}`;
  console.log(`[TabPet] Connecting to overlay: ${wsUrl}`);

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[TabPet] Connected to Python Desktop Overlay!");
      reconnectDelay = 1000;
      if (reconnectTimer) clearTimeout(reconnectTimer);
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
    const tabId = msg.tab_id;
    if (tabId) {
      console.log(`[TabPet] Closing tab ${tabId} per pet command. Roast: ${msg.roast || ""}`);
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

    const sendLeft = Math.max(0, win.left || 0);
    sendWs({
      type: "window_bounds",
      left: sendLeft,
      top: win.top,
      width: win.width,
      height: win.height,
      tab_count: tabs.length,
      active_tab_index: activeIndex
    });
  } catch (_) {}
}

chrome.windows.onBoundsChanged.addListener(() => sendCurrentWindowBounds());
chrome.windows.onFocusChanged.addListener((windowId) => {
  if (windowId !== chrome.windows.WINDOW_ID_NONE) sendCurrentWindowBounds();
});

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

chrome.tabs.onCreated.addListener(() => sendCurrentWindowBounds());
chrome.tabs.onRemoved.addListener((tabId) => {
  pendingBlockedTabs.delete(tabId);
  temporaryPasses.delete(tabId);
  sendCurrentWindowBounds();
});

// -------------------------------------------------------------
// 4. Pomodoro Focus Session Management
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
    stats.focusMinutesToday += Number(data.workDuration || 25);
    const breakMinutes = Number(data.breakDuration || 5);
    const nextEndTime = Date.now() + breakMinutes * 60 * 1000;

    await chrome.storage.local.set({
      pomodoroMode: "break",
      pomodoroEndTime: nextEndTime,
      stats
    });
    chrome.alarms.create(ALARM_NAME, { when: nextEndTime });
  } else if (mode === "break") {
    await chrome.storage.local.set({
      pomodoroMode: "idle",
      pomodoroEndTime: 0
    });
  }
});

// -------------------------------------------------------------
// 5. Blocklist, Smart Judge & Plea Bargain
// -------------------------------------------------------------
function isDomainMatch(rawUrl, domainList) {
  if (!rawUrl || !rawUrl.startsWith("http")) return false;
  try {
    const urlObj = new URL(rawUrl);
    const hostname = urlObj.hostname.toLowerCase();
    return domainList.some((d) => {
      const clean = d.trim().toLowerCase();
      if (!clean) return false;
      return hostname === clean || hostname.endsWith("." + clean);
    });
  } catch {
    return false;
  }
}

// Sanitize URL to protocol + domain + pathname only (privacy: NO query parameters or tokens)
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

  // Check temporary grace pass
  if (temporaryPasses.has(tab.id)) {
    const expiresAt = temporaryPasses.get(tab.id);
    if (Date.now() < expiresAt) return; // Grace period active
    temporaryPasses.delete(tab.id);
  }

  const data = await chrome.storage.local.get([
    "pomodoroMode",
    "blockedDomains",
    "mixedDomains",
    "focusGoal",
    "stats",
    "wsPort",
    "localOnly"
  ]);

  if (data.pomodoroMode !== "work") return;

  const alwaysBlocked = data.blockedDomains || DEFAULT_STATE.blockedDomains;
  const mixed = data.mixedDomains || DEFAULT_STATE.mixedDomains;
  const isAlways = isDomainMatch(tab.url, alwaysBlocked);
  const isMixed = isDomainMatch(tab.url, mixed);

  if (!isAlways && !isMixed) return;

  const port = data.wsPort || 8765;
  const goal = data.focusGoal || "";
  const cleanUrl = sanitizeUrl(tab.url);

  // Inject cover overlay into tab
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
    console.warn("[TabPet] Could not inject cover:", err);
  }

  // 1. SMART JUDGE for mixed domains (YouTube, Reddit, etc.)
  if (isMixed && !data.localOnly) {
    try {
      chrome.tabs.sendMessage(tab.id, { action: "set_thinking", goal }).catch(() => {});

      // Call local AI Judge endpoint with 2.0s hard timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);

      const resp = await fetch(`http://127.0.0.1:${port}/judge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: cleanUrl,
          title: tab.title || "",
          goal
        }),
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (resp.ok) {
        const judgeData = await resp.json();
        if (judgeData.verdict === "allow") {
          console.log(`[TabPet] AI Judge allowed page: ${cleanUrl} (${judgeData.reason})`);
          chrome.tabs.sendMessage(tab.id, {
            action: "allow_tab",
            reason: judgeData.reason
          }).catch(() => {});
          return;
        }
      }
    } catch (e) {
      console.warn("[TabPet] AI Judge call failed/timed out. Falling back to block:", e);
    }
  }

  // 2. ALWAYS-BLOCK or AI Verdict = Block
  pendingBlockedTabs.add(tab.id);

  // Tell cover to show blocked state with Plea Bargain form
  chrome.tabs.sendMessage(tab.id, {
    action: "set_blocked",
    url: cleanUrl,
    title: tab.title || "",
    goal
  }).catch(() => {});

  // Increment stats
  const currentStats = data.stats || DEFAULT_STATE.stats;
  currentStats.blocksToday = (currentStats.blocksToday || 0) + 1;
  await chrome.storage.local.set({ stats: currentStats });

  let tabCount = 1;
  try {
    const win = await chrome.windows.get(tab.windowId, { populate: true });
    tabCount = (win.tabs || []).length;
  } catch (_) {}

  // Send stomping command to Desktop Pet overlay
  sendWs({
    type: "blocked_tab_opened",
    tab_id: tab.id,
    tab_index: tab.index,
    tab_count: tabCount,
    url: cleanUrl,
    title: tab.title || "",
    blocks_today: currentStats.blocksToday,
    streak_days: currentStats.streakDays,
    goal
  });

  // Fail-safe close after 7 seconds if pet or user doesn't plea
  setTimeout(() => {
    if (pendingBlockedTabs.has(tab.id)) {
      chrome.tabs.remove(tab.id).catch(() => {});
      pendingBlockedTabs.delete(tab.id);
    }
  }, 7000);
}

// -------------------------------------------------------------
// 6. Content Script & Popup Message Dispatcher
// -------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "submit_plea") {
    // Plea bargain from cover screen
    (async () => {
      const { wsPort, focusGoal } = await chrome.storage.local.get(["wsPort", "focusGoal"]);
      const port = wsPort || 8765;
      const tabId = sender.tab ? sender.tab.id : message.tabId;

      try {
        const resp = await fetch(`http://127.0.0.1:${port}/plea`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tab_id: tabId,
            url: sanitizeUrl(message.url),
            title: message.title || "",
            goal: focusGoal || "",
            plea: message.plea
          })
        });

        if (resp.ok) {
          const pleaData = await resp.json();
          if (pleaData.grant_minutes > 0) {
            // Grant temporary grace pass
            temporaryPasses.set(tabId, Date.now() + (pleaData.grant_minutes * 60 * 1000));
            pendingBlockedTabs.delete(tabId);
          }
          sendResponse({
            granted: pleaData.grant_minutes > 0,
            minutes: pleaData.grant_minutes,
            reason: pleaData.reason,
            trust_score: pleaData.trust_score,
            offline: pleaData.offline
          });
          return;
        }
      } catch (e) {
        console.warn("[TabPet] Plea API error:", e);
      }
      sendResponse({ granted: false, minutes: 0, reason: "Plea evaluation failed.", trust_score: 50, offline: true });
    })();
    return true; // Keep message channel open for async response
  }

  if (message.action === "set_goal") {
    (async () => {
      await chrome.storage.local.set({ focusGoal: message.goal });
      const { wsPort } = await chrome.storage.local.get(["wsPort"]);
      const port = wsPort || 8765;
      fetch(`http://127.0.0.1:${port}/goal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: message.goal })
      }).catch(() => {});
      sendWs({ type: "set_goal", goal: message.goal });
      sendResponse({ status: "ok" });
    })();
    return true;
  }
});

// Tab navigation listeners
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "loading" && tab.url) {
    handlePotentialBlockedTab(tab);
  }
});

chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  if (details.frameId !== 0) return;
  try {
    const tab = await chrome.tabs.get(details.tabId);
    handlePotentialBlockedTab({ ...tab, url: details.url });
  } catch (_) {}
});

setInterval(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    initWebSocket();
  } else {
    sendWs({ type: "ping" });
  }
}, 15000);

/**
 * Tab Pet Popup Controller with AI Focus Goal and Pet's Notes
 */

const sessionBadge = document.getElementById("sessionBadge");
const timeDisplay = document.getElementById("timeDisplay");
const startWorkBtn = document.getElementById("startWorkBtn");
const startBreakBtn = document.getElementById("startBreakBtn");
const stopBtn = document.getElementById("stopBtn");

const statBlocks = document.getElementById("statBlocks");
const statFocus = document.getElementById("statFocus");
const statStreak = document.getElementById("statStreak");

const focusGoalInput = document.getElementById("focusGoalInput");
const soundToggle = document.getElementById("soundToggle");
const localOnlyToggle = document.getElementById("localOnlyToggle");
const connectionStatus = document.getElementById("connectionStatus");
const aiStatus = document.getElementById("aiStatus");

const trustBadge = document.getElementById("trustBadge");
const notesSaves = document.getElementById("notesSaves");
const notesBlocks = document.getElementById("notesBlocks");
const notesPleas = document.getElementById("notesPleas");
const recentEventsList = document.getElementById("recentEventsList");

let timerInterval = null;

async function checkServerConnection() {
  try {
    const { wsPort } = await chrome.storage.local.get(["wsPort"]);
    const port = wsPort || 8765;
    const resp = await fetch(`http://127.0.0.1:${port}/health`);
    if (resp.ok) {
      const data = await resp.json();
      connectionStatus.textContent = "Overlay Connected";
      connectionStatus.className = "status-badge connected";

      if (data.local_only) {
        aiStatus.textContent = "Local Only";
        aiStatus.classList.remove("hidden");
      } else if (data.ai_offline) {
        aiStatus.textContent = "Offline Mode";
        aiStatus.classList.remove("hidden");
      } else {
        aiStatus.classList.add("hidden");
      }

      loadPetNotes(port);
      return;
    }
  } catch (_) {}

  connectionStatus.textContent = "Overlay Offline";
  connectionStatus.className = "status-badge disconnected";
  aiStatus.textContent = "Offline Mode";
  aiStatus.classList.remove("hidden");
}

async function loadPetNotes(port) {
  try {
    const resp = await fetch(`http://127.0.0.1:${port}/notes`);
    if (resp.ok) {
      const notes = await resp.json();
      const moodCapitalized = (notes.mood || "neutral").charAt(0).toUpperCase() + (notes.mood || "neutral").slice(1);
      trustBadge.textContent = `Trust: ${notes.trust_score}% • ${moodCapitalized}`;
      notesSaves.textContent = notes.saves || 0;
      notesBlocks.textContent = notes.blocks || 0;
      notesPleas.textContent = notes.pleas_granted || 0;

      const events = notes.recent_events || [];
      if (events.length > 0) {
        recentEventsList.innerHTML = events.map(e => `
          <div class="event-item">
            <span class="event-domain" title="${e.title || ''}">${e.domain}</span>
            <span class="event-tag ${e.verdict}">${e.verdict}</span>
          </div>
        `).join("");
      } else {
        recentEventsList.innerHTML = `<div class="event-empty">No recent events yet. Stay focused!</div>`;
      }
    }
  } catch (_) {}
}

function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

async function renderState() {
  const data = await chrome.storage.local.get([
    "pomodoroMode",
    "pomodoroEndTime",
    "workDuration",
    "breakDuration",
    "stats",
    "soundEnabled",
    "focusGoal",
    "localOnly"
  ]);

  const mode = data.pomodoroMode || "idle";
  const endTime = data.pomodoroEndTime || 0;
  const workDuration = data.workDuration || 25;
  const breakDuration = data.breakDuration || 5;

  soundToggle.checked = data.soundEnabled !== false;
  localOnlyToggle.checked = data.localOnly === true;
  if (data.focusGoal) {
    focusGoalInput.value = data.focusGoal;
  }

  // Stats
  const stats = data.stats || {};
  statBlocks.textContent = stats.blocksToday || 0;
  statFocus.textContent = `${stats.focusMinutesToday || 0}m`;
  statStreak.textContent = `${stats.streakDays || 1}d`;

  // UI state
  if (mode === "work") {
    sessionBadge.textContent = "Focus Session (Tabs Guarded)";
    sessionBadge.className = "session-badge work";
    startWorkBtn.classList.add("hidden");
    startBreakBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    focusGoalInput.disabled = true;
  } else if (mode === "break") {
    sessionBadge.textContent = "Break Time (Free Browsing)";
    sessionBadge.className = "session-badge break";
    startWorkBtn.classList.add("hidden");
    startBreakBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    focusGoalInput.disabled = false;
  } else {
    sessionBadge.textContent = "Ready to Focus";
    sessionBadge.className = "session-badge idle";
    startWorkBtn.classList.remove("hidden");
    startBreakBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
    focusGoalInput.disabled = false;
    timeDisplay.textContent = `${String(workDuration).padStart(2, "0")}:00`;
  }

  // Timer loop
  if (timerInterval) clearInterval(timerInterval);

  if (mode !== "idle" && endTime > Date.now()) {
    updateCountdown(endTime);
    timerInterval = setInterval(() => updateCountdown(endTime), 500);
  }
}

function updateCountdown(endTime) {
  const remainingMs = endTime - Date.now();
  if (remainingMs <= 0) {
    if (timerInterval) clearInterval(timerInterval);
    renderState();
    return;
  }
  const totalSeconds = Math.ceil(remainingMs / 1000);
  timeDisplay.textContent = formatTime(totalSeconds);
}

// -------------------------------------------------------------
// Button Handlers
// -------------------------------------------------------------
startWorkBtn.addEventListener("click", async () => {
  const data = await chrome.storage.local.get(["workDuration"]);
  const minutes = Number(data.workDuration || 25);
  const endTime = Date.now() + minutes * 60 * 1000;
  const goal = focusGoalInput.value.trim();

  await chrome.storage.local.set({
    pomodoroMode: "work",
    pomodoroEndTime: endTime,
    focusGoal: goal
  });

  // Sync goal with Python app
  chrome.runtime.sendMessage({ action: "set_goal", goal });

  chrome.alarms.create("tab_pet_pomodoro", { when: endTime });
  renderState();
});

startBreakBtn.addEventListener("click", async () => {
  const data = await chrome.storage.local.get(["breakDuration"]);
  const minutes = Number(data.breakDuration || 5);
  const endTime = Date.now() + minutes * 60 * 1000;

  await chrome.storage.local.set({
    pomodoroMode: "break",
    pomodoroEndTime: endTime
  });

  chrome.alarms.create("tab_pet_pomodoro", { when: endTime });
  renderState();
});

stopBtn.addEventListener("click", async () => {
  await chrome.storage.local.set({
    pomodoroMode: "idle",
    pomodoroEndTime: 0
  });

  chrome.alarms.clear("tab_pet_pomodoro");
  renderState();
});

soundToggle.addEventListener("change", async () => {
  await chrome.storage.local.set({ soundEnabled: soundToggle.checked });
});

localOnlyToggle.addEventListener("change", async () => {
  const isLocal = localOnlyToggle.checked;
  await chrome.storage.local.set({ localOnly: isLocal });
  const { wsPort } = await chrome.storage.local.get(["wsPort"]);
  const port = wsPort || 8765;
  fetch(`http://127.0.0.1:${port}/settings/local_only`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ local_only: isLocal })
  }).catch(() => {});
  checkServerConnection();
});

focusGoalInput.addEventListener("change", () => {
  const goal = focusGoalInput.value.trim();
  chrome.storage.local.set({ focusGoal: goal });
  chrome.runtime.sendMessage({ action: "set_goal", goal });
});

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  renderState();
  checkServerConnection();
});

/**
 * Tab Pet Popup Controller
 */

const sessionBadge = document.getElementById("sessionBadge");
const timeDisplay = document.getElementById("timeDisplay");
const startWorkBtn = document.getElementById("startWorkBtn");
const startBreakBtn = document.getElementById("startBreakBtn");
const stopBtn = document.getElementById("stopBtn");

const statBlocks = document.getElementById("statBlocks");
const statFocus = document.getElementById("statFocus");
const statStreak = document.getElementById("statStreak");

const soundToggle = document.getElementById("soundToggle");
const connectionStatus = document.getElementById("connectionStatus");

let timerInterval = null;

async function checkServerConnection() {
  try {
    const { wsPort } = await chrome.storage.local.get(["wsPort"]);
    const port = wsPort || 8765;
    const resp = await fetch(`http://127.0.0.1:${port}/health`);
    if (resp.ok) {
      connectionStatus.textContent = "Overlay Connected";
      connectionStatus.className = "status-badge connected";
      return;
    }
  } catch (_) {}

  connectionStatus.textContent = "Overlay Offline";
  connectionStatus.className = "status-badge disconnected";
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
    "soundEnabled"
  ]);

  const mode = data.pomodoroMode || "idle";
  const endTime = data.pomodoroEndTime || 0;
  const workDuration = data.workDuration || 25;
  const breakDuration = data.breakDuration || 5;

  soundToggle.checked = data.soundEnabled !== false;

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
  } else if (mode === "break") {
    sessionBadge.textContent = "Break Time (Free Browsing)";
    sessionBadge.className = "session-badge break";
    startWorkBtn.classList.add("hidden");
    startBreakBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
  } else {
    sessionBadge.textContent = "Ready to Focus";
    sessionBadge.className = "session-badge idle";
    startWorkBtn.classList.remove("hidden");
    startBreakBtn.classList.remove("hidden");
    stopBtn.classList.add("hidden");
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
  const remainingSec = Math.ceil(remainingMs / 1000);
  timeDisplay.textContent = formatTime(remainingSec);
}

function playProceduralSound(type = "chime") {
  chrome.storage.local.get(["soundEnabled"], (res) => {
    if (res.soundEnabled === false) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();

      if (type === "chime") {
        // Two-tone cheerful focus chime (C5 -> G5)
        const notes = [523.25, 783.99];
        notes.forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();
          const start = ctx.currentTime + i * 0.12;
          osc.type = "sine";
          osc.frequency.setValueAtTime(freq, start);
          gain.gain.setValueAtTime(0.15, start);
          gain.gain.exponentialRampToValueAtTime(0.001, start + 0.3);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(start);
          osc.stop(start + 0.32);
        });
      }
    } catch (_) {}
  });
}

// Controls
startWorkBtn.addEventListener("click", async () => {
  const { workDuration } = await chrome.storage.local.get(["workDuration"]);
  const mins = workDuration || 25;
  const endTime = Date.now() + mins * 60 * 1000;

  await chrome.storage.local.set({
    pomodoroMode: "work",
    pomodoroEndTime: endTime
  });

  playProceduralSound("chime");
  chrome.alarms.create("tab_pet_pomodoro", { when: endTime });
  renderState();
});

startBreakBtn.addEventListener("click", async () => {
  const { breakDuration } = await chrome.storage.local.get(["breakDuration"]);
  const mins = breakDuration || 5;
  const endTime = Date.now() + mins * 60 * 1000;

  await chrome.storage.local.set({
    pomodoroMode: "break",
    pomodoroEndTime: endTime
  });

  chrome.alarms.create("tab_pet_pomodoro", { when: endTime });
  renderState();
});

stopBtn.addEventListener("click", async () => {
  await chrome.alarms.clear("tab_pet_pomodoro");
  await chrome.storage.local.set({
    pomodoroMode: "idle",
    pomodoroEndTime: 0
  });
  renderState();
});

soundToggle.addEventListener("change", async (e) => {
  await chrome.storage.local.set({ soundEnabled: e.target.checked });
});

// Init
checkServerConnection();
renderState();

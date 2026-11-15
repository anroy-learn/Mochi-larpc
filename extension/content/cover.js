(function () {
  // Prevent duplicate insertion
  if (document.getElementById("tab-pet-focus-cover")) return;

  const overlay = document.createElement("div");
  overlay.id = "tab-pet-focus-cover";

  overlay.innerHTML = `
    <div class="tab-pet-card" id="tabPetCard">
      <div class="tab-pet-avatar" id="tabPetAvatar">🐾</div>
      <h2 class="tab-pet-title" id="tabPetTitle">Pet is thinking...</h2>
      <p class="tab-pet-desc" id="tabPetDesc">
        Evaluating whether this tab aids your focus session...
      </p>
      <div class="tab-pet-meter" id="tabPetMeter">
        <div class="tab-pet-meter-bar"></div>
      </div>
      <div class="tab-pet-status" id="tabPetStatus">Checking with Mochi...</div>

      <!-- Plea Bargain Box -->
      <div class="tab-pet-plea-box" id="tabPetPleaBox" style="display: none;">
        <input type="text" id="tabPetPleaInput" class="tab-pet-plea-input" placeholder="Need this for your goal? Plead your case...">
        <button id="tabPetPleaBtn" class="tab-pet-plea-btn">Plead to Mochi</button>
        <div id="tabPetPleaFeedback" class="tab-pet-plea-feedback"></div>
      </div>
    </div>
  `;

  if (document.documentElement) {
    document.documentElement.appendChild(overlay);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(overlay);
    });
  }

  const titleEl = document.getElementById("tabPetTitle");
  const descEl = document.getElementById("tabPetDesc");
  const statusEl = document.getElementById("tabPetStatus");
  const pleaBox = document.getElementById("tabPetPleaBox");
  const pleaInput = document.getElementById("tabPetPleaInput");
  const pleaBtn = document.getElementById("tabPetPleaBtn");
  const pleaFeedback = document.getElementById("tabPetPleaFeedback");

  let currentTabUrl = window.location.href;
  let currentTabTitle = document.title;

  function showToast(reason) {
    const toast = document.createElement("div");
    toast.id = "tab-pet-ok-toast";
    toast.innerHTML = `<span>🐾</span> <span><strong>Pet says OK:</strong> ${reason}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => {
      toast.style.transition = "opacity 0.4s ease";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 400);
    }, 3500);
  }

  function setBlockedUI(reason) {
    titleEl.textContent = "Tab Pet is coming!";
    descEl.textContent = reason 
      ? `Blocked: ${reason}`
      : "This site is restricted during your Focus Session. Your pet is marching over to stomp it shut!";
    statusEl.textContent = "Closing tab shortly unless granted a plea...";
    pleaBox.style.display = "flex";
  }

  // Handle messages from background worker
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "set_thinking") {
      titleEl.textContent = "Pet is thinking...";
      descEl.textContent = msg.goal
        ? `Evaluating if this aids your goal: "${msg.goal}"...`
        : "Evaluating whether this page aids your focus session...";
      pleaBox.style.display = "none";
    } else if (msg.action === "allow_tab") {
      overlay.remove();
      showToast(msg.reason || "Relevant to your focus goal.");
    } else if (msg.action === "set_blocked") {
      setBlockedUI(msg.reason);
    }
  });

  // Plea Submission
  if (pleaBtn) {
    pleaBtn.addEventListener("click", () => {
      const pleaText = (pleaInput.value || "").trim();
      if (!pleaText) {
        pleaInput.focus();
        return;
      }

      pleaBtn.disabled = true;
      pleaBtn.textContent = "Evaluating plea with Gemini...";
      pleaFeedback.textContent = "";

      chrome.runtime.sendMessage({
        action: "submit_plea",
        url: currentTabUrl,
        title: currentTabTitle,
        plea: pleaText
      }, (res) => {
        if (!res) {
          pleaFeedback.className = "tab-pet-plea-feedback denied";
          pleaFeedback.textContent = "Plea request failed.";
          pleaBtn.disabled = false;
          pleaBtn.textContent = "Plead to Mochi";
          return;
        }

        if (res.granted) {
          pleaFeedback.className = "tab-pet-plea-feedback granted";
          pleaFeedback.textContent = `🎉 Plea Approved! Granted ${res.minutes}m (${res.reason})`;
          setTimeout(() => {
            overlay.remove();
            showToast(`Granted ${res.minutes} minutes for: ${pleaText}`);
          }, 1200);
        } else {
          pleaFeedback.className = "tab-pet-plea-feedback denied";
          pleaFeedback.textContent = `❌ Denied: ${res.reason}`;
          pleaBtn.disabled = false;
          pleaBtn.textContent = "Try another plea";
        }
      });
    });

    pleaInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        pleaBtn.click();
      }
    });
  }

  // Soft Web Audio sound alert
  try {
    chrome.storage.local.get(["soundEnabled"], (res) => {
      if (res.soundEnabled === false) return;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(440, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(160, ctx.currentTime + 0.35);
      gain.gain.setValueAtTime(0.18, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.36);
    });
  } catch (_) {}
})();

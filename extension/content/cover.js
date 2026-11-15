(function () {
  if (document.getElementById("tab-pet-focus-cover")) return;

  const overlay = document.createElement("div");
  overlay.id = "tab-pet-focus-cover";

  overlay.innerHTML = `
    <div class="tab-pet-card">
      <div class="tab-pet-avatar">🐾</div>
      <h2 class="tab-pet-title">Tab Pet is coming!</h2>
      <p class="tab-pet-desc">
        This site is blocked during your Focus Session.
        Your desktop guardian is marching over to stomp this tab shut!
      </p>
      <div class="tab-pet-meter">
        <div class="tab-pet-meter-bar"></div>
      </div>
      <div class="tab-pet-status">Closing tab shortly...</div>
    </div>
  `;

  if (document.documentElement) {
    document.documentElement.appendChild(overlay);
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      document.body.appendChild(overlay);
    });
  }

  // Synthesize cute procedural sound effects using Web Audio API
  try {
    chrome.storage.local.get(["soundEnabled"], (res) => {
      if (res.soundEnabled === false) return;

      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();

      // Play soft "whistle & stomp" alert
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

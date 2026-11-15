/**
 * Tab Pet - In-Browser Companion
 * Procedurally animated cute pet that lives directly on your browser pages!
 */

(function () {
  if (window.top !== window.self) return; // Top-level frame only
  if (document.getElementById("tab-pet-browser-companion")) return;

  function initCompanion() {
    const el = document.createElement("div");
    el.id = "tab-pet-browser-companion";
    el.innerHTML = `
      <div class="tab-pet-dom-avatar">
        <canvas class="tab-pet-dom-canvas" width="64" height="64"></canvas>
      </div>
      <div class="tab-pet-dom-info">
        <span class="tab-pet-dom-name">Mochi</span>
        <span id="tabPetStatusText" class="tab-pet-dom-status">Guarding</span>
      </div>
    `;

    document.body.appendChild(el);

    const canvas = el.querySelector(".tab-pet-dom-canvas");
    const ctx = canvas.getContext("2d");
    const statusText = document.getElementById("tabPetStatusText");

    // Animation state
    let stateTime = 0;
    let blink = 0;
    let isBlinking = false;
    let blinkProgress = 0;
    let squashX = 1;
    let squashY = 1;
    let isPetted = false;
    let pettedTimer = 0;

    // Procedural pet drawing (Squash & stretch, eyes, ears, blush)
    function drawPet() {
      ctx.clearRect(0, 0, 64, 64);
      ctx.save();
      ctx.translate(32, 48);
      ctx.scale(squashX, squashY);

      // Body Gradient
      const grad = ctx.createLinearGradient(0, -32, 0, 0);
      grad.addColorStop(0, "#FFA07A");
      grad.addColorStop(1, "#FF6347");

      // Left Ear
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(-13, -24);
      ctx.lineTo(-11, -35);
      ctx.lineTo(-4, -28);
      ctx.closePath();
      ctx.fill();

      // Right Ear
      ctx.beginPath();
      ctx.moveTo(4, -28);
      ctx.lineTo(11, -35);
      ctx.lineTo(13, -24);
      ctx.closePath();
      ctx.fill();

      // Inner ears
      ctx.fillStyle = "#FFB6C1";
      ctx.beginPath();
      ctx.moveTo(-11, -25);
      ctx.lineTo(-10, -32);
      ctx.lineTo(-5, -28);
      ctx.closePath();
      ctx.fill();

      ctx.beginPath();
      ctx.moveTo(5, -28);
      ctx.lineTo(10, -32);
      ctx.lineTo(11, -25);
      ctx.closePath();
      ctx.fill();

      // Body squircle
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(-16, -30, 32, 30, 14);
      ctx.fill();

      // Belly
      ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
      ctx.beginPath();
      ctx.ellipse(0, -14, 8, 7, 0, 0, Math.PI * 2);
      ctx.fill();

      // Cheeks
      ctx.fillStyle = "rgba(255, 105, 120, 0.75)";
      ctx.beginPath();
      ctx.ellipse(-11, -14, 3, 2, 0, 0, Math.PI * 2);
      ctx.ellipse(11, -14, 3, 2, 0, 0, Math.PI * 2);
      ctx.fill();

      // Eyes
      if (blink > 0.5) {
        // Happy squint ^ ^
        ctx.strokeStyle = "#1E272C";
        ctx.lineWidth = 1.8;
        ctx.lineCap = "round";

        ctx.beginPath();
        ctx.arc(-7, -19, 2.5, Math.PI, 0);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(7, -19, 2.5, Math.PI, 0);
        ctx.stroke();
      } else {
        // Open eyes with shine
        ctx.fillStyle = "#1E272C";
        ctx.beginPath();
        ctx.ellipse(-7, -19, 2.5, 2.8, 0, 0, Math.PI * 2);
        ctx.ellipse(7, -19, 2.5, 2.8, 0, 0, Math.PI * 2);
        ctx.fill();

        // White gleams
        ctx.fillStyle = "#FFFFFF";
        ctx.beginPath();
        ctx.arc(-6.2, -20.2, 0.9, 0, Math.PI * 2);
        ctx.arc(7.8, -20.2, 0.9, 0, Math.PI * 2);
        ctx.fill();
      }

      // Mouth :3
      ctx.strokeStyle = "#5A3025";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.arc(-1.5, -14.5, 1.5, 0, Math.PI);
      ctx.arc(1.5, -14.5, 1.5, 0, Math.PI);
      ctx.stroke();

      // Little paws
      ctx.fillStyle = "#FFA07A";
      ctx.beginPath();
      ctx.roundRect(-10, -2, 6, 4, 2);
      ctx.roundRect(4, -2, 6, 4, 2);
      ctx.fill();

      ctx.restore();
    }

    // Animation Loop
    function tick() {
      stateTime += 0.02;

      if (isPetted) {
        pettedTimer += 0.04;
        const spring = Math.sin(pettedTimer * Math.PI * 4) * Math.exp(-pettedTimer * 3);
        squashX = 1 + spring * 0.4;
        squashY = 1 - spring * 0.4;
        blink = 1;
        if (pettedTimer > 1) {
          isPetted = false;
          blink = 0;
        }
      } else {
        // Breathing
        const breath = Math.sin(stateTime * 2.5) * 0.04;
        squashX = 1 - breath;
        squashY = 1 + breath;

        // Random blinks
        if (!isBlinking && Math.random() < 0.008) {
          isBlinking = true;
          blinkProgress = 0;
        }
        if (isBlinking) {
          blinkProgress += 0.12;
          blink = Math.sin(blinkProgress * Math.PI);
          if (blinkProgress >= 1) {
            isBlinking = false;
            blink = 0;
          }
        }
      }

      drawPet();
      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);

    // Click / Pet interaction
    el.addEventListener("click", (e) => {
      isPetted = true;
      pettedTimer = 0;

      // Spawn floating heart
      const heart = document.createElement("div");
      heart.className = "tab-pet-floating-heart";
      heart.textContent = "♥";
      heart.style.left = `${e.clientX - 8}px`;
      heart.style.top = `${e.clientY - 16}px`;
      document.body.appendChild(heart);
      setTimeout(() => heart.remove(), 800);

      // Play soft chirp sound
      try {
        chrome.storage.local.get(["soundEnabled"], (res) => {
          if (res.soundEnabled === false) return;
          const AudioCtx = window.AudioContext || window.webkitAudioContext;
          if (!AudioCtx) return;
          const actx = new AudioCtx();
          const osc = actx.createOscillator();
          const g = actx.createGain();
          osc.type = "sine";
          osc.frequency.setValueAtTime(580, actx.currentTime);
          osc.frequency.exponentialRampToValueAtTime(880, actx.currentTime + 0.18);
          g.gain.setValueAtTime(0.12, actx.currentTime);
          g.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + 0.18);
          osc.connect(g);
          g.connect(actx.destination);
          osc.start();
          osc.stop(actx.currentTime + 0.19);
        });
      } catch (_) {}
    });

    // Draggable across the browser
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let elemStartX = 0;
    let elemStartY = 0;

    el.addEventListener("mousedown", (e) => {
      isDragging = true;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
      const rect = el.getBoundingClientRect();
      elemStartX = rect.left;
      elemStartY = rect.top;
      e.preventDefault();
    });

    window.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      el.style.left = `${Math.max(10, Math.min(window.innerWidth - 120, elemStartX + dx))}px`;
      el.style.top = `${Math.max(10, Math.min(window.innerHeight - 60, elemStartY + dy))}px`;
      el.style.right = "auto";
    });

    window.addEventListener("mouseup", () => {
      isDragging = false;
    });

    // Sync Pomodoro timer status
    function updateStatus() {
      chrome.storage.local.get(["pomodoroMode", "pomodoroEndTime"], (data) => {
        const mode = data.pomodoroMode || "idle";
        const end = data.pomodoroEndTime || 0;
        if (mode === "work" && end > Date.now()) {
          const sec = Math.ceil((end - Date.now()) / 1000);
          const m = Math.floor(sec / 60);
          const s = sec % 60;
          statusText.textContent = `Focus ${m}:${String(s).padStart(2, "0")}`;
          statusText.style.color = "#ff8a65";
        } else if (mode === "break" && end > Date.now()) {
          const sec = Math.ceil((end - Date.now()) / 1000);
          const m = Math.floor(sec / 60);
          const s = sec % 60;
          statusText.textContent = `Break ${m}:${String(s).padStart(2, "0")}`;
          statusText.style.color = "#60a5fa";
        } else {
          statusText.textContent = "Guarding";
          statusText.style.color = "#9ca3af";
        }
      });
    }

    updateStatus();
    setInterval(updateStatus, 1000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCompanion);
  } else {
    initCompanion();
  }
})();

/**
 * Tab Pet Options Controller
 */

const blocklistInput = document.getElementById("blocklistInput");
const workDuration = document.getElementById("workDuration");
const breakDuration = document.getElementById("breakDuration");
const authTokenInput = document.getElementById("authTokenInput");
const showTokenBtn = document.getElementById("showTokenBtn");
const saveBtn = document.getElementById("saveBtn");
const saveNotice = document.getElementById("saveNotice");

// Load stored settings
document.addEventListener("DOMContentLoaded", async () => {
  const data = await chrome.storage.local.get([
    "blockedDomains",
    "workDuration",
    "breakDuration",
    "authToken"
  ]);

  if (data.blockedDomains && Array.isArray(data.blockedDomains)) {
    blocklistInput.value = data.blockedDomains.join("\n");
  }

  workDuration.value = data.workDuration || 25;
  breakDuration.value = data.breakDuration || 5;
  authTokenInput.value = data.authToken || "";
});

// Toggle password visibility
showTokenBtn.addEventListener("click", () => {
  if (authTokenInput.type === "password") {
    authTokenInput.type = "text";
    showTokenBtn.textContent = "Hide";
  } else {
    authTokenInput.type = "password";
    showTokenBtn.textContent = "Show";
  }
});

// Save settings
saveBtn.addEventListener("click", async () => {
  // Parse blocklist entries
  const rawLines = blocklistInput.value.split("\n");
  const cleanedDomains = rawLines
    .map((line) => {
      let val = line.trim().toLowerCase();
      // Strip protocols and paths if user pasted full URLs
      val = val.replace(/^https?:\/\//i, "");
      val = val.replace(/\/.*$/, "");
      return val;
    })
    .filter((domain) => domain.length > 0 && domain.includes("."));

  // Remove duplicates
  const uniqueDomains = Array.from(new Set(cleanedDomains));

  await chrome.storage.local.set({
    blockedDomains: uniqueDomains,
    workDuration: Math.max(1, parseInt(workDuration.value, 10) || 25),
    breakDuration: Math.max(1, parseInt(breakDuration.value, 10) || 5),
    authToken: authTokenInput.value.trim()
  });

  saveNotice.classList.add("show");
  setTimeout(() => {
    saveNotice.classList.remove("show");
  }, 2200);
});

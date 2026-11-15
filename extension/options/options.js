/**
 * Tab Pet Options Controller with Mixed Domains
 */

const blocklistInput = document.getElementById("blocklistInput");
const mixedlistInput = document.getElementById("mixedlistInput");
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
    "mixedDomains",
    "workDuration",
    "breakDuration",
    "authToken"
  ]);

  if (data.blockedDomains && Array.isArray(data.blockedDomains)) {
    blocklistInput.value = data.blockedDomains.join("\n");
  } else {
    blocklistInput.value = [
      "twitter.com",
      "x.com",
      "instagram.com",
      "facebook.com",
      "tiktok.com",
      "netflix.com",
      "twitch.tv"
    ].join("\n");
  }

  if (data.mixedDomains && Array.isArray(data.mixedDomains)) {
    mixedlistInput.value = data.mixedDomains.join("\n");
  } else {
    mixedlistInput.value = ["youtube.com", "reddit.com"].join("\n");
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

function parseDomainList(text) {
  return text
    .split("\n")
    .map((line) => {
      let val = line.trim().toLowerCase();
      val = val.replace(/^https?:\/\//i, "");
      val = val.replace(/\/.*$/, "");
      return val;
    })
    .filter((domain) => domain.length > 0 && domain.includes("."));
}

// Save settings
saveBtn.addEventListener("click", async () => {
  const alwaysBlocked = Array.from(new Set(parseDomainList(blocklistInput.value)));
  const mixedBlocked = Array.from(new Set(parseDomainList(mixedlistInput.value)));

  await chrome.storage.local.set({
    blockedDomains: alwaysBlocked,
    mixedDomains: mixedBlocked,
    workDuration: Math.max(1, parseInt(workDuration.value, 10) || 25),
    breakDuration: Math.max(1, parseInt(breakDuration.value, 10) || 5),
    authToken: authTokenInput.value.trim()
  });

  saveNotice.classList.add("show");
  setTimeout(() => {
    saveNotice.classList.remove("show");
  }, 2200);
});

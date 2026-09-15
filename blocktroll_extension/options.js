const DEFAULTS = {
  serverUrl: "http://100.96.86.10:8787",
  mode: "blur_click",            // blur_click | blur | hide
  enableTaunt: false,
  enableToxic: true,
  enableSpam: true,
  useCustomThresholds: false,
  softThreshold: 0.45,
  hardThreshold: 0.60
};

function $(id) { return document.getElementById(id); }

async function loadOptions() {
  const data = await chrome.storage.sync.get(DEFAULTS);
  $("serverUrl").value = data.serverUrl;
  $("mode").value = data.mode;
  $("enableTaunt").checked = !!data.enableTaunt;
  $("enableToxic").checked = !!data.enableToxic;
  $("enableSpam").checked = !!data.enableSpam;
  $("softThreshold").value = data.softThreshold;
  $("hardThreshold").value = data.hardThreshold;
}

async function saveOptions() {
  const next = {
    serverUrl: $("serverUrl").value.trim() || DEFAULTS.serverUrl,
    mode: $("mode").value,
    enableTaunt: $("enableTaunt").checked,
    enableToxic: $("enableToxic").checked,
    enableSpam: $("enableSpam").checked,
    useCustomThresholds: true,
    softThreshold: Math.max(0, Math.min(1, Number($("softThreshold").value || DEFAULTS.softThreshold))),
    hardThreshold: Math.max(0, Math.min(1, Number($("hardThreshold").value || DEFAULTS.hardThreshold)))
  };

  await chrome.storage.sync.set(next);
  $("status").textContent = "저장됨";
  setTimeout(() => ($("status").textContent = ""), 1200);
}

document.addEventListener("DOMContentLoaded", () => {
  loadOptions();
  $("saveBtn").addEventListener("click", saveOptions);
});

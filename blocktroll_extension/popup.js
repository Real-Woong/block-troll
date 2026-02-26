const DEFAULTS = {
  intensity: 2,
  enableTaunt: true,
  enableToxic: true,
  enableSpam: true
};

async function load() {
  const v = await chrome.storage.sync.get(DEFAULTS);
  document.querySelectorAll("button[data-level]").forEach(b => {
    b.classList.toggle("active", Number(b.dataset.level) === Number(v.intensity));
    b.onclick = async () => {
      await chrome.storage.sync.set({ intensity: Number(b.dataset.level) });
      await load();
      document.getElementById("status").textContent = "저장됨";
      setTimeout(() => document.getElementById("status").textContent = "", 800);
    };
  });

  for (const k of ["enableTaunt","enableToxic","enableSpam"]) {
    const el = document.getElementById(k);
    el.checked = !!v[k];
    el.onchange = async () => chrome.storage.sync.set({ [k]: el.checked });
  }
}
load();
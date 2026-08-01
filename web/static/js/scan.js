const ICONS = {
  idle: "⏳",
  scanning: "🔍",
  clean: "✅",
  infected: "🦠",
  error: "⚠️",
  cancelled: "🛑",
};

const CLASSES = {
  idle: "status-waiting",
  scanning: "status-scanning",
  clean: "status-clean",
  infected: "status-infected",
  error: "status-error",
  cancelled: "status-cancelled",
};

const panel = document.getElementById("status-panel");
const icon = document.getElementById("status-icon");
const message = document.getElementById("status-message");
const logEl = document.getElementById("scan-log");
const scannersList = document.getElementById("scanners-list");
const currentScanner = document.getElementById("current-scanner");
const mediaList = document.getElementById("media-list");
const mediaHint = document.getElementById("media-hint");
const btnRefresh = document.getElementById("btn-refresh-media");
const progressContainer = document.getElementById("progress-container");
const progressLabel = document.getElementById("progress-label");
const progressPercent = document.getElementById("progress-percent");
const progressFill = document.getElementById("progress-fill");
const btnCancelScan = document.getElementById("btn-cancel-scan");

let isScanning = false;
let cancelRequested = false;

function updateProgress(progress, label) {
  if (!progressContainer) return;
  const value = Math.max(0, Math.min(100, progress || 0));
  progressContainer.classList.toggle("hidden", !isScanning);
  if (progressFill) progressFill.style.width = `${value}%`;
  if (progressPercent) progressPercent.textContent = `${value} %`;
  if (progressLabel && label) progressLabel.textContent = label;
}

function renderMediaList(media) {
  if (!mediaList) return;

  if (!media || !media.length) {
    mediaList.innerHTML = "<p class='muted media-empty'>Aucun média détecté. Branchez un disque ou une clé USB puis actualisez.</p>";
    if (mediaHint) mediaHint.textContent = "Formats supportés : NTFS, exFAT, ext4, FAT32";
    return;
  }

  if (mediaHint) mediaHint.textContent = `${media.length} média(s) détecté(s)`;

  mediaList.innerHTML = media.map((m) => `
    <div class="media-card" data-device="${m.device}">
      <div class="media-card-info">
        <div class="media-card-title">${m.label}</div>
        <div class="media-card-meta">
          <span class="media-tag">${m.device}</span>
          <span class="media-tag">${m.fstype.toUpperCase()}</span>
          <span class="media-tag">${m.size}</span>
          <span class="media-tag">${m.bus === "usb" ? "USB" : m.bus}</span>
          ${m.mounted
            ? `<span class="media-tag media-tag-ok">Monté : ${m.mountpoint}</span>`
            : `<span class="media-tag media-tag-warn">Non monté</span>`}
        </div>
        <div class="media-card-serial">Série : ${m.serial}</div>
      </div>
      <button class="btn btn-primary btn-scan-media" data-device="${m.device}" ${isScanning ? "disabled" : ""}>
        Analyser
      </button>
    </div>
  `).join("");

  mediaList.querySelectorAll(".btn-scan-media").forEach((btn) => {
    btn.addEventListener("click", () => startScan(btn.dataset.device));
  });
}

async function refreshMedia() {
  if (!btnRefresh) return;
  btnRefresh.disabled = true;
  btnRefresh.textContent = "Actualisation...";
  mediaList.innerHTML = "<p class='muted'>Recherche des médias...</p>";

  try {
    const res = await fetch("/api/scan/refresh", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur");
    renderMediaList(data.media);
  } catch (err) {
    mediaList.innerHTML = `<p class='muted media-empty'>${err.message}</p>`;
  }

  btnRefresh.disabled = isScanning;
  btnRefresh.textContent = "Actualiser la liste";
}

async function startScan(device) {
  if (isScanning) return;
  try {
    const res = await fetch("/api/scan/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur");
    isScanning = true;
    cancelRequested = false;
    if (btnCancelScan) {
      btnCancelScan.disabled = false;
      btnCancelScan.textContent = "Annuler l'analyse";
    }
    mediaList.querySelectorAll(".btn-scan-media").forEach((b) => (b.disabled = true));
    if (btnRefresh) btnRefresh.disabled = true;
    updateProgress(0, "Démarrage de l'analyse...");
  } catch (err) {
    message.textContent = err.message;
    panel.className = "status-panel status-error";
  }
}

async function cancelScan() {
  if (!isScanning || cancelRequested) return;
  cancelRequested = true;
  if (btnCancelScan) {
    btnCancelScan.disabled = true;
    btnCancelScan.textContent = "Annulation...";
  }
  try {
    const res = await fetch("/api/scan/cancel", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur");
    if (progressLabel) progressLabel.textContent = "Annulation en cours...";
  } catch (err) {
    cancelRequested = false;
    if (btnCancelScan) {
      btnCancelScan.disabled = false;
      btnCancelScan.textContent = "Annuler l'analyse";
    }
    message.textContent = err.message;
  }
}

async function poll() {
  try {
    const res = await fetch("/api/scan/status");
    const data = await res.json();

    icon.textContent = ICONS[data.state] || "⏳";
    message.textContent = data.message;
    panel.className = "status-panel " + (CLASSES[data.state] || "status-waiting");

    const wasScanning = isScanning;
    isScanning = data.scanning;

    if (isScanning) {
      updateProgress(data.progress, data.progress_label || "Analyse en cours...");
    } else if (progressContainer) {
      progressContainer.classList.add("hidden");
      cancelRequested = false;
      if (btnCancelScan) {
        btnCancelScan.disabled = false;
        btnCancelScan.textContent = "Annuler l'analyse";
      }
    }

    if (wasScanning && !isScanning) {
      if (btnRefresh) btnRefresh.disabled = false;
      renderMediaList(data.media);
    } else if (!isScanning && data.media) {
      renderMediaList(data.media);
    }

    if (data.scanners && scannersList) {
      scannersList.textContent = "Moteurs : " + data.scanners
        .map((s) => s.display_name + (s.available ? " ✓" : " ✗"))
        .join(" | ");
    }

    if (currentScanner) {
      currentScanner.textContent = data.current_scanner
        ? `En cours : ${data.current_scanner}`
        : "";
    }

    if (data.log && data.log.length) {
      logEl.textContent = data.log.join("\n");
      logEl.scrollTop = logEl.scrollHeight;
    }
  } catch (e) {
    message.textContent = "Connexion au service de scan impossible.";
  }
}

if (btnRefresh) {
  btnRefresh.addEventListener("click", refreshMedia);
}

if (btnCancelScan) {
  btnCancelScan.addEventListener("click", cancelScan);
}

refreshMedia();
setInterval(poll, 1500);
poll();

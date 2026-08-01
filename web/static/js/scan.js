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
const scanAnimation = document.getElementById("scan-animation");
const scanTip = document.getElementById("scan-tip");
const bitlockerModal = document.getElementById("bitlocker-modal");
const bitlockerBackdrop = document.getElementById("bitlocker-backdrop");
const bitlockerForm = document.getElementById("bitlocker-form");
const bitlockerDeviceLabel = document.getElementById("bitlocker-modal-device");
const bitlockerPassword = document.getElementById("bitlocker-password");
const bitlockerRecovery = document.getElementById("bitlocker-recovery");
const bitlockerError = document.getElementById("bitlocker-error");
const btnBitlockerCancel = document.getElementById("btn-bitlocker-cancel");
const btnBitlockerUnlock = document.getElementById("btn-bitlocker-unlock");

let pendingBitlockerDevice = null;

const SCAN_TIPS = [
  "Les virus n'ont aucune chance ici.",
  "Inspection méticuleuse de chaque fichier...",
  "On vérifie les recoins les plus sombres du disque.",
  "Patience — la sécurité ne se précipite pas.",
  "Recherche de menaces cachées en cours...",
  "Trois moteurs, une seule mission : vous protéger.",
  "Aucun octet suspect n'échappera à l'analyse.",
  "Presque comme un détective, mais pour les malwares.",
  "Le café est prêt, l'analyse aussi bientôt.",
  "Fouille en profondeur : c'est notre spécialité.",
];

let isScanning = false;
let cancelRequested = false;
let tipIndex = 0;
let tipTimer = null;

function setScanAnimation(active) {
  if (scanAnimation) scanAnimation.classList.toggle("hidden", !active);
  if (icon) icon.classList.toggle("is-scanning", active);
  if (scanTip) scanTip.classList.toggle("hidden", !active);
  if (active) {
    startTipRotation();
  } else {
    stopTipRotation();
  }
}

function startTipRotation() {
  if (!scanTip) return;
  tipIndex = Math.floor(Math.random() * SCAN_TIPS.length);
  scanTip.textContent = SCAN_TIPS[tipIndex];
  stopTipRotation();
  tipTimer = setInterval(() => {
    tipIndex = (tipIndex + 1) % SCAN_TIPS.length;
    scanTip.classList.add("scan-tip-fade");
    setTimeout(() => {
      scanTip.textContent = SCAN_TIPS[tipIndex];
      scanTip.classList.remove("scan-tip-fade");
    }, 250);
  }, 4000);
}

function stopTipRotation() {
  if (tipTimer) {
    clearInterval(tipTimer);
    tipTimer = null;
  }
  if (scanTip) scanTip.textContent = "";
}

function updateProgress(progress, label) {
  if (!progressContainer) return;
  const value = Math.max(0, Math.min(100, progress || 0));
  progressContainer.classList.toggle("hidden", !isScanning);
  if (progressFill) progressFill.style.width = `${value}%`;
  if (progressPercent) progressPercent.textContent = `${value} %`;
  if (progressLabel && label) progressLabel.textContent = label;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function openBitlockerModal(device, label) {
  pendingBitlockerDevice = device;
  if (bitlockerDeviceLabel) {
    bitlockerDeviceLabel.textContent = `${label} (${device})`;
  }
  if (bitlockerPassword) bitlockerPassword.value = "";
  if (bitlockerRecovery) bitlockerRecovery.value = "";
  if (bitlockerError) {
    bitlockerError.textContent = "";
    bitlockerError.classList.add("hidden");
  }
  if (bitlockerModal) bitlockerModal.classList.remove("hidden");
  if (bitlockerPassword) bitlockerPassword.focus();
}

function closeBitlockerModal() {
  pendingBitlockerDevice = null;
  if (bitlockerModal) bitlockerModal.classList.add("hidden");
}

async function submitBitlockerUnlock(event) {
  event.preventDefault();
  if (!pendingBitlockerDevice) return;

  const password = bitlockerPassword ? bitlockerPassword.value : "";
  const recoveryKey = bitlockerRecovery ? bitlockerRecovery.value : "";

  if (!password && !recoveryKey) {
    if (bitlockerError) {
      bitlockerError.textContent = "Indiquez un mot de passe ou une clé de récupération.";
      bitlockerError.classList.remove("hidden");
    }
    return;
  }

  if (btnBitlockerUnlock) {
    btnBitlockerUnlock.disabled = true;
    btnBitlockerUnlock.textContent = "Déverrouillage...";
  }

  try {
    const res = await fetch("/api/scan/bitlocker/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        device: pendingBitlockerDevice,
        password,
        recovery_key: recoveryKey,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur de déverrouillage");

    closeBitlockerModal();
    renderMediaList(data.media);
    if (message) message.textContent = data.message || "Volume déverrouillé.";
    if (panel) panel.className = "status-panel status-clean";
  } catch (err) {
    if (bitlockerError) {
      bitlockerError.textContent = err.message;
      bitlockerError.classList.remove("hidden");
    }
  } finally {
    if (btnBitlockerUnlock) {
      btnBitlockerUnlock.disabled = false;
      btnBitlockerUnlock.textContent = "Déverrouiller";
    }
  }
}

async function lockBitlocker(device) {
  try {
    const res = await fetch("/api/scan/bitlocker/lock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Erreur");
    renderMediaList(data.media);
  } catch (err) {
    if (message) message.textContent = err.message;
    if (panel) panel.className = "status-panel status-error";
  }
}

function renderMediaList(media) {
  if (!mediaList) return;

  if (!media || !media.length) {
    mediaList.innerHTML = "<p class='muted media-empty'>Aucun média détecté. Branchez un disque ou une clé USB puis actualisez.</p>";
    if (mediaHint) mediaHint.textContent = "Formats supportés : NTFS, exFAT, ext4, FAT32, BitLocker";
    return;
  }

  if (mediaHint) mediaHint.textContent = `${media.length} média(s) détecté(s)`;

  mediaList.innerHTML = media.map((m) => {
    const isBitlocker = m.bitlocker;
    const locked = m.bitlocker_locked;
    const actions = isBitlocker && locked
      ? `<button class="btn btn-primary btn-bitlocker-unlock" data-device="${m.device}" data-label="${escapeHtml(m.label)}" ${isScanning ? "disabled" : ""}>Déverrouiller</button>`
      : isBitlocker && !locked
        ? `<button class="btn btn-secondary btn-bitlocker-lock" data-device="${m.device}" ${isScanning ? "disabled" : ""}>Verrouiller</button>
           <button class="btn btn-primary btn-scan-media" data-device="${m.device}" ${isScanning ? "disabled" : ""}>Analyser</button>`
        : `<button class="btn btn-primary btn-scan-media" data-device="${m.device}" ${isScanning ? "disabled" : ""}>Analyser</button>`;

    return `
    <div class="media-card" data-device="${m.device}">
      <div class="media-card-info">
        <div class="media-card-title">${escapeHtml(m.label)}</div>
        <div class="media-card-meta">
          <span class="media-tag">${escapeHtml(m.device)}</span>
          <span class="media-tag ${isBitlocker ? "media-tag-bitlocker" : ""}">${isBitlocker ? "BITLOCKER" : escapeHtml(m.fstype.toUpperCase())}</span>
          <span class="media-tag">${escapeHtml(m.size)}</span>
          <span class="media-tag">${m.bus === "usb" ? "USB" : escapeHtml(m.bus)}</span>
          ${isBitlocker && locked
            ? `<span class="media-tag media-tag-warn">Verrouillé</span>`
            : isBitlocker
              ? `<span class="media-tag media-tag-ok">Déverrouillé</span>`
              : m.mounted
                ? `<span class="media-tag media-tag-ok">Monté : ${escapeHtml(m.mountpoint)}</span>`
                : `<span class="media-tag media-tag-warn">Non monté</span>`}
        </div>
        <div class="media-card-serial">Série : ${escapeHtml(m.serial)}</div>
      </div>
      <div class="media-card-actions">${actions}</div>
    </div>`;
  }).join("");

  mediaList.querySelectorAll(".btn-scan-media").forEach((btn) => {
    btn.addEventListener("click", () => startScan(btn.dataset.device));
  });

  mediaList.querySelectorAll(".btn-bitlocker-unlock").forEach((btn) => {
    btn.addEventListener("click", () => openBitlockerModal(btn.dataset.device, btn.dataset.label));
  });

  mediaList.querySelectorAll(".btn-bitlocker-lock").forEach((btn) => {
    btn.addEventListener("click", () => lockBitlocker(btn.dataset.device));
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
    setScanAnimation(true);
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
      setScanAnimation(true);
    } else if (progressContainer) {
      progressContainer.classList.add("hidden");
      setScanAnimation(false);
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

if (bitlockerForm) {
  bitlockerForm.addEventListener("submit", submitBitlockerUnlock);
}

if (btnBitlockerCancel) {
  btnBitlockerCancel.addEventListener("click", closeBitlockerModal);
}

if (bitlockerBackdrop) {
  bitlockerBackdrop.addEventListener("click", closeBitlockerModal);
}

refreshMedia();
setInterval(poll, 1500);
poll();

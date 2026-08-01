async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Erreur serveur");
  return data;
}

function showMsg(el, text, isError = false) {
  el.textContent = text;
  el.classList.remove("hidden");
  el.style.color = isError ? "var(--danger)" : "";
  if (!isError) el.classList.add("success-msg");
}

// --- Page de connexion ---
const loginForm = document.getElementById("login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const errEl = document.getElementById("login-error");
    errEl.classList.add("hidden");
    try {
      await api("/api/admin/login", {
        method: "POST",
        body: JSON.stringify({
          username: document.getElementById("username").value,
          password: document.getElementById("password").value,
        }),
      });
      window.location.href = "/admin";
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove("hidden");
    }
  });
}

// --- Page admin ---
const btnLogout = document.getElementById("btn-logout");
if (btnLogout) {
  btnLogout.addEventListener("click", async () => {
    await api("/api/admin/logout", { method: "POST" });
    window.location.href = "/admin";
  });
}

// --- Statut des moteurs antivirus ---
const scannersStatus = document.getElementById("scanners-status");
if (scannersStatus) {
  fetch("/api/scanners/status")
    .then((r) => r.json())
    .then((scanners) => {
      scannersStatus.innerHTML = scanners
        .map(
          (s) =>
            `<span class="${s.available ? "scanner-ok" : "scanner-off"}">` +
            `${s.available ? "✓" : "✗"} ${s.display_name}</span>`
        )
        .join("<br>");
    })
    .catch(() => {
      scannersStatus.textContent = "Impossible de charger les moteurs.";
    });
}

const btnUpdateStation = document.getElementById("btn-update-station");
if (btnUpdateStation) {
  btnUpdateStation.addEventListener("click", async () => {
    const out = document.getElementById("update-output");
    out.classList.remove("hidden");
    out.textContent = "Mise à jour en cours...";
    btnUpdateStation.disabled = true;
    try {
      const data = await api("/api/admin/update-station", { method: "POST" });
      out.textContent = data.output || "Terminé.";
    } catch (err) {
      out.textContent = err.message;
    }
    btnUpdateStation.disabled = false;
  });
}

const btnUpdateSigs = document.getElementById("btn-update-sigs");
if (btnUpdateSigs) {
  btnUpdateSigs.addEventListener("click", async () => {
    const out = document.getElementById("update-output");
    out.classList.remove("hidden");
    out.textContent = "Mise à jour des signatures...";
    btnUpdateSigs.disabled = true;
    try {
      const data = await api("/api/admin/update-signatures", { method: "POST" });
      out.textContent = data.output || "Terminé.";
    } catch (err) {
      out.textContent = err.message;
    }
    btnUpdateSigs.disabled = false;
  });
}

// --- Fonds d'écran presets ---
const presetsContainer = document.getElementById("wallpaper-presets");
if (presetsContainer) {
  api("/api/admin/wallpaper/presets")
    .then((presets) => {
      if (!presets.length) {
        presetsContainer.innerHTML = "<p class='muted'>Aucun preset disponible.</p>";
        return;
      }
      presetsContainer.innerHTML = presets
        .map(
          (p) =>
            `<button class="preset-btn" data-preset="${p.file}">${p.name}</button>`
        )
        .join("");

      presetsContainer.querySelectorAll(".preset-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const msg = document.getElementById("wallpaper-msg");
          const formData = new FormData();
          formData.append("preset", btn.dataset.preset);
          try {
            const res = await fetch("/api/admin/wallpaper", {
              method: "POST",
              body: formData,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Erreur");
            showMsg(msg, "Fond d'écran appliqué.");
          } catch (err) {
            showMsg(msg, err.message, true);
          }
        });
      });
    })
    .catch(() => {
      presetsContainer.innerHTML = "<p class='muted'>Impossible de charger les presets.</p>";
    });
}

const wallpaperForm = document.getElementById("wallpaper-form");
if (wallpaperForm) {
  wallpaperForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = document.getElementById("wallpaper-file").files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    const msg = document.getElementById("wallpaper-msg");
    try {
      const res = await fetch("/api/admin/wallpaper", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur");
      showMsg(msg, "Fond d'écran appliqué.");
    } catch (err) {
      showMsg(msg, err.message, true);
    }
  });
}

const passwordForm = document.getElementById("password-form");
if (passwordForm) {
  passwordForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("password-msg");
    const newPass = document.getElementById("new-password").value;
    const confirm = document.getElementById("confirm-password").value;
    if (newPass !== confirm) {
      showMsg(msg, "Les mots de passe ne correspondent pas.", true);
      return;
    }
    try {
      await api("/api/admin/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: document.getElementById("current-password").value,
          new_password: newPass,
        }),
      });
      showMsg(msg, "Mot de passe modifié avec succès.");
      passwordForm.reset();
    } catch (err) {
      showMsg(msg, err.message, true);
    }
  });
}

const btnEnableKiosk = document.getElementById("btn-enable-kiosk");
if (btnEnableKiosk) {
  btnEnableKiosk.addEventListener("click", async () => {
    const msg = document.getElementById("kiosk-msg");
    try {
      const data = await api("/api/admin/enable-kiosk", { method: "POST" });
      showMsg(msg, data.message);
    } catch (err) {
      showMsg(msg, err.message, true);
    }
  });
}

const btnDisableKiosk = document.getElementById("btn-disable-kiosk");
if (btnDisableKiosk) {
  btnDisableKiosk.addEventListener("click", async () => {
    if (!confirm("Quitter le mode kiosk et accéder au bureau ?")) return;
    const msg = document.getElementById("kiosk-msg");
    try {
      const data = await api("/api/admin/disable-kiosk", { method: "POST" });
      showMsg(msg, data.message);
    } catch (err) {
      showMsg(msg, err.message, true);
    }
  });
}

// --- Journal des analyses ---
const logsList = document.getElementById("logs-list");
const logContent = document.getElementById("log-content");

async function loadLogs() {
  if (!logsList) return;
  try {
    const logs = await api("/api/admin/logs");
    if (!logs.length) {
      logsList.innerHTML = "<p class='muted' style='padding:0.75rem'>Aucun log disponible.</p>";
      return;
    }
    logsList.innerHTML = logs
      .map(
        (l) =>
          `<button class="log-item" data-file="${l.filename}">${l.filename}</button>`
      )
      .join("");

    logsList.querySelectorAll(".log-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        logsList.querySelectorAll(".log-item").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        try {
          const data = await api(`/api/admin/logs/${encodeURIComponent(btn.dataset.file)}`);
          logContent.textContent = data.content;
        } catch (err) {
          logContent.textContent = err.message;
        }
      });
    });
  } catch (err) {
    logsList.innerHTML = `<p class='muted' style='padding:0.75rem'>${err.message}</p>`;
  }
}

if (logsList) loadLogs();

// --- Réseau ---
const networkPanel = document.getElementById("network-panel");
let selectedWifiSsid = "";

function showNetworkMsg(text, isError = false) {
  const el = document.getElementById("network-msg");
  if (!el) return;
  showMsg(el, text, isError);
}

function renderNetworkDevices(devices) {
  const container = document.getElementById("network-devices");
  const wifiSelect = document.getElementById("wifi-device-select");
  if (!container) return;

  if (!devices.length) {
    container.innerHTML = "<p class='muted'>Aucune interface réseau détectée.</p>";
    return;
  }

  container.innerHTML = devices.map((d) => {
    const isStatic = d.ipv4_method === "manual";
    return `
      <div class="net-card" data-device="${d.device}">
        <div class="net-card-header">
          <div>
            <div class="net-card-title">${d.device}</div>
            <div class="net-card-type">${d.type_label}</div>
          </div>
          <span class="net-badge ${d.connected ? "connected" : "disconnected"}">
            ${d.connected ? "Connecté" : d.state}
          </span>
        </div>
        <div class="net-info">
          IP : ${d.ipv4_address || "—"}<br>
          Mode : ${d.ipv4_method === "manual" ? "IP fixe" : d.ipv4_method === "auto" ? "DHCP" : d.ipv4_method || "—"}<br>
          Passerelle : ${d.ipv4_gateway || "—"}<br>
          DNS : ${d.ipv4_dns || "—"}
        </div>
        <div class="btn-group">
          <button class="btn btn-secondary btn-net-toggle" data-device="${d.device}" data-enabled="${!d.connected}">
            ${d.connected ? "Déconnecter" : "Connecter"}
          </button>
        </div>
        <form class="net-form net-ipv4-form" data-device="${d.device}">
          <label>Configuration IPv4</label>
          <select class="ipv4-method">
            <option value="auto" ${!isStatic ? "selected" : ""}>DHCP (automatique)</option>
            <option value="manual" ${isStatic ? "selected" : ""}>IP fixe</option>
          </select>
          <div class="static-fields ${isStatic ? "" : "hidden"}">
            <label>Adresse IP</label>
            <input type="text" class="ipv4-address" placeholder="192.168.1.100" value="${d.ipv4_address || ""}">
            <label>Masque (préfixe)</label>
            <input type="number" class="ipv4-prefix" value="24" min="1" max="32">
            <label>Passerelle</label>
            <input type="text" class="ipv4-gateway" placeholder="192.168.1.1" value="${d.ipv4_gateway || ""}">
            <label>DNS</label>
            <input type="text" class="ipv4-dns" placeholder="8.8.8.8" value="${d.ipv4_dns || ""}">
          </div>
          <button type="submit" class="btn btn-primary">Appliquer</button>
        </form>
      </div>`;
  }).join("");

  if (wifiSelect) {
    const wifiDevs = devices.filter((d) => d.type === "wifi");
    wifiSelect.innerHTML = '<option value="">Interface Wi-Fi...</option>' +
      wifiDevs.map((d) => `<option value="${d.device}">${d.device}</option>`).join("");
    if (wifiDevs.length === 1) wifiSelect.value = wifiDevs[0].device;
  }

  container.querySelectorAll(".ipv4-method").forEach((sel) => {
    sel.addEventListener("change", () => {
      const fields = sel.closest(".net-form").querySelector(".static-fields");
      fields.classList.toggle("hidden", sel.value !== "manual");
    });
  });

  container.querySelectorAll(".net-ipv4-form").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const device = form.dataset.device;
      const method = form.querySelector(".ipv4-method").value;
      const body = { device, method };
      if (method === "manual") {
        body.address = form.querySelector(".ipv4-address").value;
        body.prefix = parseInt(form.querySelector(".ipv4-prefix").value, 10);
        body.gateway = form.querySelector(".ipv4-gateway").value;
        body.dns = form.querySelector(".ipv4-dns").value;
      }
      try {
        const data = await api("/api/admin/network/ipv4", { method: "POST", body: JSON.stringify(body) });
        showNetworkMsg(data.message || "Configuration appliquée.");
        loadNetwork();
      } catch (err) {
        showNetworkMsg(err.message, true);
      }
    });
  });

  container.querySelectorAll(".btn-net-toggle").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const data = await api("/api/admin/network/device", {
          method: "POST",
          body: JSON.stringify({
            device: btn.dataset.device,
            enabled: btn.dataset.enabled === "true",
          }),
        });
        showNetworkMsg(data.message);
        loadNetwork();
      } catch (err) {
        showNetworkMsg(err.message, true);
      }
    });
  });
}

async function loadNetwork() {
  if (!networkPanel) return;
  try {
    const data = await api("/api/admin/network/status");
    const radioToggle = document.getElementById("wifi-radio-toggle");
    if (radioToggle) radioToggle.checked = data.wifi_radio;
    renderNetworkDevices(data.devices);
  } catch (err) {
    const container = document.getElementById("network-devices");
    if (container) container.innerHTML = `<p class='muted'>${err.message}</p>`;
  }
}

if (networkPanel) {
  loadNetwork();

  document.getElementById("btn-network-refresh")?.addEventListener("click", loadNetwork);

  document.getElementById("wifi-radio-toggle")?.addEventListener("change", async (e) => {
    try {
      const data = await api("/api/admin/network/wifi/radio", {
        method: "POST",
        body: JSON.stringify({ enabled: e.target.checked }),
      });
      showNetworkMsg(data.message);
      loadNetwork();
    } catch (err) {
      showNetworkMsg(err.message, true);
      e.target.checked = !e.target.checked;
    }
  });

  document.getElementById("btn-wifi-scan")?.addEventListener("click", async () => {
    const device = document.getElementById("wifi-device-select")?.value;
    const list = document.getElementById("wifi-networks");
    list.innerHTML = "<p class='muted' style='padding:0.75rem'>Scan en cours...</p>";
    try {
      const url = device
        ? `/api/admin/network/wifi/scan?device=${encodeURIComponent(device)}`
        : "/api/admin/network/wifi/scan";
      const res = await fetch(url);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur");
      if (!data.networks.length) {
        list.innerHTML = "<p class='muted' style='padding:0.75rem'>Aucun réseau détecté.</p>";
        return;
      }
      list.innerHTML = data.networks.map((n) => `
        <div class="wifi-item" data-ssid="${n.ssid.replace(/"/g, "&quot;")}">
          <span>${n.in_use ? "★ " : ""}${n.ssid} <small>(${n.security})</small></span>
          <span class="signal">${n.signal}%</span>
        </div>`).join("");

      list.querySelectorAll(".wifi-item").forEach((item) => {
        item.addEventListener("click", () => {
          list.querySelectorAll(".wifi-item").forEach((i) => i.classList.remove("active"));
          item.classList.add("active");
          selectedWifiSsid = item.dataset.ssid;
          document.getElementById("wifi-selected-ssid").textContent = selectedWifiSsid;
          document.getElementById("wifi-connect-form").classList.remove("hidden");
        });
      });
    } catch (err) {
      list.innerHTML = `<p class='muted' style='padding:0.75rem'>${err.message}</p>`;
    }
  });

  document.getElementById("wifi-connect-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedWifiSsid) return;
    const device = document.getElementById("wifi-device-select")?.value;
    const password = document.getElementById("wifi-password").value;
    try {
      const data = await api("/api/admin/network/wifi/connect", {
        method: "POST",
        body: JSON.stringify({ ssid: selectedWifiSsid, password, device: device || undefined }),
      });
      showNetworkMsg(data.message || "Connecté au Wi-Fi.");
      loadNetwork();
    } catch (err) {
      showNetworkMsg(err.message, true);
    }
  });
}

// --- Désinstallation ---
const uninstallForm = document.getElementById("uninstall-form");
if (uninstallForm) {
  uninstallForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const msg = document.getElementById("uninstall-msg");
    const password = document.getElementById("uninstall-password").value;
    const confirmText = document.getElementById("uninstall-confirm").value;

    if (
      !window.confirm(
        "Confirmer la désinstallation complète de Station Blanche ?\n\nLa machine va redémarrer et Peppermint sera restauré en configuration normale."
      )
    ) {
      return;
    }

    try {
      const res = await fetch("/api/admin/uninstall", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password, confirm_text: confirmText }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur");
      showMsg(msg, data.message);
      uninstallForm.querySelector("button").disabled = true;
    } catch (err) {
      showMsg(msg, err.message, true);
    }
  });
}

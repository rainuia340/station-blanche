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

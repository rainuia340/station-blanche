async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Erreur serveur");
  return data;
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
      msg.textContent = "Fond d'écran appliqué.";
      msg.classList.remove("hidden");
    } catch (err) {
      msg.textContent = err.message;
      msg.classList.remove("hidden");
      msg.classList.remove("success-msg");
      msg.style.color = "var(--danger)";
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
      msg.textContent = "Les mots de passe ne correspondent pas.";
      msg.classList.remove("hidden");
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
      msg.textContent = "Mot de passe modifié avec succès.";
      msg.classList.remove("hidden");
      passwordForm.reset();
    } catch (err) {
      msg.textContent = err.message;
      msg.classList.remove("hidden");
    }
  });
}

const btnDisableKiosk = document.getElementById("btn-disable-kiosk");
if (btnDisableKiosk) {
  btnDisableKiosk.addEventListener("click", async () => {
    if (!confirm("Quitter le mode kiosk et accéder au bureau ?")) return;
    try {
      const data = await api("/api/admin/disable-kiosk", { method: "POST" });
      alert(data.message);
    } catch (err) {
      alert(err.message);
    }
  });
}

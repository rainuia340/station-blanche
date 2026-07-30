#!/usr/bin/env python3
"""Interface web Station Blanche — Peppermint OS."""

import os
import subprocess
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config_manager import (
    change_admin_password,
    ensure_config,
    get_secret_key,
    load_config,
    save_config,
    verify_admin,
)
from scan_engine import ScanEngine

APP_DIR = Path(__file__).resolve().parent
INSTALL_DIR = "/opt/station-blanche"
WALLPAPER_DIR = "/etc/station-blanche/wallpapers"

ensure_config()
app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = get_secret_key()

scan_engine = ScanEngine()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Non autorisé"}), 401
            return redirect(url_for("admin_page"))
        return f(*args, **kwargs)

    return decorated


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/scan")
def scan_page():
    return render_template("scan.html")


@app.route("/admin")
def admin_page():
    if session.get("admin_logged_in"):
        return render_template("admin.html", config=load_config())
    return render_template("admin_login.html")


@app.route("/api/scan/status")
def api_scan_status():
    return jsonify(scan_engine.status())


@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if verify_admin(username, password):
        session["admin_logged_in"] = True
        return jsonify({"ok": True})
    return jsonify({"error": "Identifiants incorrects"}), 401


@app.route("/api/admin/logout", methods=["POST"])
@admin_required
def api_admin_logout():
    session.pop("admin_logged_in", None)
    return jsonify({"ok": True})


@app.route("/api/admin/update-station", methods=["POST"])
@admin_required
def api_update_station():
    script = f"{INSTALL_DIR}/install.sh"
    if not os.path.isfile(script):
        return jsonify({"error": "Script install.sh introuvable"}), 500
    proc = subprocess.run(
        ["bash", script, "--update"],
        capture_output=True,
        text=True,
        timeout=600,
    )
    return jsonify({
        "ok": proc.returncode == 0,
        "output": proc.stdout + proc.stderr,
    })


@app.route("/api/admin/update-signatures", methods=["POST"])
@admin_required
def api_update_signatures():
    proc = subprocess.run(
        ["freshclam"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return jsonify({
        "ok": proc.returncode == 0,
        "output": proc.stdout + proc.stderr,
    })


@app.route("/api/admin/change-password", methods=["POST"])
@admin_required
def api_change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current_password", "")
    new_pass = data.get("new_password", "")
    cfg = load_config()
    if not verify_admin(cfg.get("admin_user", "admin"), current):
        return jsonify({"error": "Mot de passe actuel incorrect"}), 400
    if len(new_pass) < 6:
        return jsonify({"error": "Le nouveau mot de passe doit faire au moins 6 caractères"}), 400
    change_admin_password(new_pass)
    return jsonify({"ok": True})


@app.route("/api/admin/wallpaper", methods=["POST"])
@admin_required
def api_wallpaper():
    os.makedirs(WALLPAPER_DIR, exist_ok=True)
    cfg = load_config()

    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        dest = os.path.join(WALLPAPER_DIR, "custom.jpg")
        f.save(dest)
        cfg["wallpaper"] = dest
    elif request.form.get("preset"):
        preset = request.form["preset"]
        path = APP_DIR / "static" / "img" / "presets" / preset
        if path.exists():
            cfg["wallpaper"] = str(path)

    save_config(cfg)
    subprocess.run(
        ["bash", f"{INSTALL_DIR}/scripts/apply-wallpaper.sh", cfg["wallpaper"]],
        check=False,
    )
    return jsonify({"ok": True, "wallpaper": cfg["wallpaper"]})


@app.route("/api/admin/disable-kiosk", methods=["POST"])
@admin_required
def api_disable_kiosk():
    cfg = load_config()
    cfg["kiosk_enabled"] = False
    save_config(cfg)
    subprocess.Popen(["bash", f"{INSTALL_DIR}/scripts/disable-kiosk.sh"])
    return jsonify({"ok": True, "message": "Mode kiosk désactivé. Retour au bureau..."})


@app.route("/api/admin/config")
@admin_required
def api_admin_config():
    return jsonify(load_config())


if __name__ == "__main__":
    scan_engine.start()
    app.run(host="127.0.0.1", port=8080, debug=False, threaded=True)

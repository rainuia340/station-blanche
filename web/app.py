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
from network_manager import (
    configure_ipv4,
    get_wifi_radio,
    is_available as nm_available,
    list_devices,
    set_device_state,
    set_wifi_radio,
    wifi_connect,
    wifi_scan,
)
from scan_engine import ScanEngine
from scanners import ALL_SCANNERS, scanners_status

LOG_DIR = "/var/log/antivirscan"
APP_DIR = Path(__file__).resolve().parent
INSTALL_DIR = "/opt/station-blanche"
WALLPAPER_DIR = "/etc/station-blanche/wallpapers"
PRESETS_DIR = APP_DIR / "static" / "img" / "presets"

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
    data = scan_engine.status()
    data["scanners"] = scanners_status()
    return jsonify(data)


@app.route("/api/scanners/status")
def api_scanners_status():
    return jsonify(scanners_status())


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
    script = f"{INSTALL_DIR}/scripts/update-signatures.sh"
    if os.path.isfile(script):
        proc = subprocess.run(
            ["bash", script],
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = proc.stdout + proc.stderr
        ok = proc.returncode == 0
    else:
        output_parts = []
        ok = True
        for scanner in ALL_SCANNERS:
            if scanner.is_available():
                success, msg = scanner.update_signatures()
                output_parts.append(f"--- {scanner.display_name} ---\n{msg}")
                if not success:
                    ok = False
        output = "\n".join(output_parts) or "Aucun moteur disponible."

    return jsonify({"ok": ok, "output": output})


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
        ext = Path(f.filename).suffix or ".jpg"
        dest = os.path.join(WALLPAPER_DIR, f"custom{ext}")
        f.save(dest)
        cfg["wallpaper"] = dest
    elif request.form.get("preset"):
        preset = os.path.basename(request.form["preset"])
        path = PRESETS_DIR / preset
        if path.exists() and path.parent.resolve() == PRESETS_DIR.resolve():
            cfg["wallpaper"] = str(path)
        else:
            return jsonify({"error": "Preset introuvable"}), 400

    save_config(cfg)
    subprocess.run(
        ["bash", f"{INSTALL_DIR}/scripts/apply-wallpaper.sh", cfg["wallpaper"]],
        check=False,
    )
    return jsonify({"ok": True, "wallpaper": cfg["wallpaper"]})


@app.route("/api/admin/wallpaper/presets")
@admin_required
def api_wallpaper_presets():
    presets = []
    if PRESETS_DIR.is_dir():
        for f in sorted(PRESETS_DIR.iterdir()):
            if f.suffix.lower() in (".svg", ".jpg", ".jpeg", ".png"):
                presets.append({"name": f.stem, "file": f.name})
    return jsonify(presets)


@app.route("/api/admin/enable-kiosk", methods=["POST"])
@admin_required
def api_enable_kiosk():
    cfg = load_config()
    cfg["kiosk_enabled"] = True
    save_config(cfg)
    subprocess.Popen(["bash", f"{INSTALL_DIR}/scripts/enable-kiosk.sh"])
    return jsonify({"ok": True, "message": "Mode kiosk réactivé."})


@app.route("/api/admin/logs")
@admin_required
def api_list_logs():
    logs = []
    if os.path.isdir(LOG_DIR):
        for name in sorted(os.listdir(LOG_DIR), reverse=True):
            if not name.endswith(".log"):
                continue
            path = os.path.join(LOG_DIR, name)
            if not os.path.isfile(path):
                continue
            stat = os.stat(path)
            logs.append({
                "filename": name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })
    return jsonify(logs)


@app.route("/api/admin/logs/<path:filename>")
@admin_required
def api_get_log(filename):
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".log") or ".." in safe_name:
        return jsonify({"error": "Fichier invalide"}), 400
    path = os.path.join(LOG_DIR, safe_name)
    if not os.path.isfile(path):
        return jsonify({"error": "Log introuvable"}), 404
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    return jsonify({"filename": safe_name, "content": content})


@app.route("/api/admin/disable-kiosk", methods=["POST"])
@admin_required
def api_disable_kiosk():
    cfg = load_config()
    cfg["kiosk_enabled"] = False
    save_config(cfg)
    subprocess.Popen(["bash", f"{INSTALL_DIR}/scripts/disable-kiosk.sh"])
    return jsonify({"ok": True, "message": "Mode kiosk désactivé. Retour au bureau..."})


@app.route("/api/admin/uninstall", methods=["POST"])
@admin_required
def api_uninstall():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    confirm = data.get("confirm_text", "")

    if confirm != "DESINSTALLER":
        return jsonify({"error": "Saisissez DESINSTALLER pour confirmer"}), 400

    cfg = load_config()
    if not verify_admin(cfg.get("admin_user", "admin"), password):
        return jsonify({"error": "Mot de passe incorrect"}), 401

    script = f"{INSTALL_DIR}/scripts/uninstall.sh"
    if not os.path.isfile(script):
        return jsonify({"error": "Script de désinstallation introuvable"}), 500

    subprocess.Popen(
        ["nohup", "bash", script, "--reboot"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return jsonify({
        "ok": True,
        "message": "Désinstallation lancée. La machine va redémarrer dans quelques secondes.",
    })


@app.route("/api/admin/config")
@admin_required
def api_admin_config():
    return jsonify(load_config())


# --- Réseau ---

@app.route("/api/admin/network/status")
@admin_required
def api_network_status():
    if not nm_available():
        return jsonify({"error": "NetworkManager (nmcli) non disponible"}), 503
    try:
        return jsonify({
            "available": True,
            "wifi_radio": get_wifi_radio(),
            "devices": list_devices(),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/network/device", methods=["POST"])
@admin_required
def api_network_device():
    data = request.get_json(silent=True) or {}
    device = data.get("device", "")
    enabled = data.get("enabled", True)
    try:
        ok, msg = set_device_state(device, enabled)
        return jsonify({"ok": ok, "message": msg})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/network/wifi/radio", methods=["POST"])
@admin_required
def api_network_wifi_radio():
    data = request.get_json(silent=True) or {}
    try:
        ok, msg = set_wifi_radio(bool(data.get("enabled", True)))
        return jsonify({"ok": ok, "message": msg})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/network/ipv4", methods=["POST"])
@admin_required
def api_network_ipv4():
    data = request.get_json(silent=True) or {}
    try:
        ok, msg = configure_ipv4(
            device=data.get("device", ""),
            method=data.get("method", "auto"),
            address=data.get("address"),
            prefix=int(data.get("prefix", 24)),
            gateway=data.get("gateway"),
            dns=data.get("dns"),
        )
        return jsonify({"ok": ok, "message": msg})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/network/wifi/scan")
@admin_required
def api_network_wifi_scan():
    device = request.args.get("device")
    try:
        networks = wifi_scan(device or None)
        return jsonify({"networks": networks})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/admin/network/wifi/connect", methods=["POST"])
@admin_required
def api_network_wifi_connect():
    data = request.get_json(silent=True) or {}
    try:
        ok, msg = wifi_connect(
            ssid=data.get("ssid", ""),
            password=data.get("password"),
            device=data.get("device"),
        )
        return jsonify({"ok": ok, "message": msg})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    scan_engine.start()
    app.run(host="127.0.0.1", port=8080, debug=False, threaded=True)

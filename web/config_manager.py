"""Gestion de la configuration Station Blanche."""

import hashlib
import json
import os
import secrets

CONFIG_DIR = "/etc/station-blanche"
CONFIG_FILE = f"{CONFIG_DIR}/config.json"
SECRET_FILE = f"{CONFIG_DIR}/secret.key"
DEFAULT_WALLPAPER = "/opt/station-blanche/web/static/img/wallpaper.svg"

DEFAULT_CONFIG = {
    "admin_user": "admin",
    "admin_password_hash": "",  # défini à l'installation (admin)
    "kiosk_enabled": True,
    "wallpaper": DEFAULT_WALLPAPER,
}


def _hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    if "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return _hash_password(password, salt) == stored


def ensure_config():
    os.makedirs(CONFIG_DIR, mode=0o750, exist_ok=True)
    if not os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
        os.chmod(SECRET_FILE, 0o600)

    if not os.path.exists(CONFIG_FILE):
        cfg = DEFAULT_CONFIG.copy()
        cfg["admin_password_hash"] = _hash_password("admin")
        save_config(cfg)
    os.chmod(CONFIG_FILE, 0o600)


def load_config() -> dict:
    ensure_config()
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def get_secret_key() -> str:
    ensure_config()
    with open(SECRET_FILE, encoding="utf-8") as f:
        return f.read().strip()


def verify_admin(username: str, password: str) -> bool:
    cfg = load_config()
    if username != cfg.get("admin_user", "admin"):
        return False
    return _verify_password(password, cfg.get("admin_password_hash", ""))


def change_admin_password(new_password: str):
    cfg = load_config()
    cfg["admin_password_hash"] = _hash_password(new_password)
    save_config(cfg)

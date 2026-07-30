# Station Blanche — Peppermint OS

Poste isolé dédié à l'analyse antivirus des médias amovibles, avec **interface web** en mode kiosk (pas de terminal graphique).

## Principe

1. **Installer Peppermint OS normalement** (ISO officiel).
2. **Lancer le script d'installation** qui contacte ce dépôt GitHub public et configure la station.
3. Au **redémarrage** : auto-login de l'utilisateur `station` → Firefox en **mode kiosk** sur la page d'accueil web.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/rainuia340/station-blanche/main/install.sh | sudo bash
```

Puis redémarrer :

```bash
sudo reboot
```

## Interface web

| Page | URL | Description |
|------|-----|-------------|
| Accueil | `http://127.0.0.1:8080/` | 2 liens : Scan USB et Administration |
| Scan | `/scan` | Détection automatique USB + analyse ClamAV en temps réel |
| Admin | `/admin` | Connexion requise (admin / admin par défaut) |

### Fonctions admin

- **MAJ Station Blanche** — met à jour depuis GitHub (`install.sh --update`)
- **MAJ Signatures ClamAV** — lance `freshclam`
- **Fond d'écran** — presets (bleu, vert, violet) ou import d'image
- **Changer le mot de passe admin**
- **Mode kiosk** — activer ou quitter le mode plein écran Firefox
- **Journal des analyses** — consulter l'historique des scans
- **Désinstallation** — supprime Station Blanche et restaure Peppermint normal (redémarrage auto)

### Moteurs antivirus (3 gratuits)

| Moteur | Description |
|--------|-------------|
| **ClamAV** | Antivirus open source (référence Linux) |
| **Linux Malware Detect (LMD)** | Signatures complémentaires, quarantaine auto |
| **F-Prot** | Antivirus gratuit usage personnel |

> **Note** : NOD32 (ESET) et Avast ne proposent pas de scanner en ligne de commande gratuit pour Linux. Les trois moteurs ci-dessus sont installés automatiquement lors de l'installation (réseau requis pour maldet et F-Prot).

Chaque scan exécute **les 3 moteurs en séquence**. Le rapport indique le résultat par moteur et un verdict global.

### Logs de scan

Chaque analyse génère un fichier log au format :

```
YYYYMMDD-HHMMSS-N°Série.log
```

Exemple : `20260730-143052-A1B2C3D4.log`

- **Sur la station** : `/var/log/antivirscan/`
- **Sur la clé USB** : copie dans le dossier `STATION_BLANCHE/` à la racine du média

## Mise à jour

```bash
curl -fsSL https://raw.githubusercontent.com/rainuia340/station-blanche/main/install.sh | sudo bash -s -- --update
```

Ou depuis l'interface admin, bouton « MAJ Station Blanche ».

## Identifiants

| Compte | Mot de passe | Usage |
|--------|-------------|-------|
| `admin` (web) | `admin` | Interface d'administration |
| `station` (système) | *(aucun)* | Auto-login kiosk uniquement |

> Changez le mot de passe admin dès la première connexion.

## Structure du projet

```
station-blanche/
├── install.sh                     # Bootstrap (contacte GitHub)
├── web/
│   ├── app.py                     # Serveur Flask
│   ├── scan_engine.py             # Détection USB + ClamAV
│   ├── config_manager.py          # Config admin / kiosk
│   ├── templates/                 # Pages HTML
│   └── static/                    # CSS, JS, images
├── scripts/
│   ├── configure-web.sh           # Service systemd
│   ├── configure-autostart.sh     # Auto-login + kiosk Firefox
│   ├── configure-users.sh         # Utilisateur station
│   ├── configure-scanners.sh      # ClamAV + LMD + F-Prot
│   ├── update-signatures.sh       # MAJ signatures tous moteurs
│   ├── configure-hardening.sh     # Durcissement ANSSI
│   ├── start-kiosk.sh             # Lance Firefox kiosk
│   ├── apply-wallpaper.sh         # Fond d'écran XFCE
│   ├── enable-kiosk.sh            # Réactive Firefox kiosk
│   ├── disable-kiosk.sh           # Quitte le mode kiosk
│   └── uninstall.sh               # Désinstalle et restaure Peppermint
├── systemd/station-blanche-web.service
└── config/firefox-kiosk.desktop
```

## Fichiers utiles

| Chemin | Description |
|--------|-------------|
| `/var/log/antivirscan/` | Journaux des analyses |
| `/var/lib/antivirscan/quarantine/` | Fichiers infectés |
| `/etc/station-blanche/config.json` | Configuration (mot de passe admin hashé) |
| `/opt/station-blanche/` | Dépôt local |

## Recommandations

- Maintenir la station **hors réseau** en usage normal.
- Connecter Internet uniquement pour les mises à jour (via l'admin web).
- Ne brancher qu'**une seule** clé USB à la fois.

## Licence

Inspiré de [Crypt-0n/Station-blanche](https://github.com/Crypt-0n/Station-blanche).

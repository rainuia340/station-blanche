"""Registre des moteurs antivirus."""

from scanners.clamav import ClamAVScanner
from scanners.fprot import FProtScanner
from scanners.maldet import MaldetScanner

ALL_SCANNERS = [
    ClamAVScanner(),
    MaldetScanner(),
    FProtScanner(),
]


def available_scanners():
    return [s for s in ALL_SCANNERS if s.is_available()]


def scanners_status() -> list[dict]:
    return [
        {"name": s.name, "display_name": s.display_name, "available": s.is_available()}
        for s in ALL_SCANNERS
    ]

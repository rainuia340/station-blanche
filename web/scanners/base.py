"""Interface commune pour les moteurs antivirus."""

import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ScannerResult:
    name: str
    display_name: str
    exit_code: int
    output: str
    infected: bool = False
    error: bool = False
    skipped: bool = False
    skip_reason: str = ""
    cancelled: bool = False

    @property
    def status_label(self) -> str:
        if self.cancelled:
            return "ANNULE"
        if self.skipped:
            return f"NON DISPONIBLE ({self.skip_reason})"
        if self.error:
            return "ERREUR"
        if self.infected:
            return "INFECTE"
        return "SAIN"


def run_subprocess(
    cmd,
    *,
    shell: bool = False,
    cancel_check: Optional[Callable[[], bool]] = None,
    register_proc: Optional[Callable] = None,
) -> tuple[int, str, str, bool]:
    """Exécute une commande et retourne (code, stdout, stderr, cancelled)."""
    proc = subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if register_proc:
        register_proc(proc)
    try:
        while proc.poll() is None:
            if cancel_check and cancel_check():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                return -1, "", "", True
            time.sleep(0.25)
        stdout, stderr = proc.communicate()
        return proc.returncode, stdout or "", stderr or "", False
    finally:
        if register_proc:
            register_proc(None)


class BaseScanner:
    name = "base"
    display_name = "Base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def scan(
        self,
        paths: list[str],
        cancel_check: Optional[Callable[[], bool]] = None,
        register_proc: Optional[Callable] = None,
    ) -> ScannerResult:
        raise NotImplementedError

    def update_signatures(self) -> tuple[bool, str]:
        return False, "Mise à jour non supportée"

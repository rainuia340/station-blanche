"""Scanner F-Prot Antivirus (gratuit usage personnel Linux)."""

import os
import subprocess

from scanners.base import BaseScanner, ScannerResult

FPROT_BIN = "/opt/f-prot/fpscan"
FPROT_ALT = "/usr/local/f-prot/fpscan"


class FProtScanner(BaseScanner):
    name = "fprot"
    display_name = "F-Prot Antivirus"

    def _bin(self) -> str | None:
        for path in (FPROT_BIN, FPROT_ALT):
            if os.path.isfile(path):
                return path
        return None

    def is_available(self) -> bool:
        return self._bin() is not None

    def scan(self, paths: list[str]) -> ScannerResult:
        bin_path = self._bin()
        if not bin_path:
            return ScannerResult(
                self.name, self.display_name, -1, "", skipped=True, skip_reason="non installé"
            )

        output_parts = []
        infected = False
        error = False
        last_code = 0

        for path in paths:
            try:
                # -r récursif, -u rapport détaillé
                proc = subprocess.run(
                    [bin_path, "-r", "-u", path],
                    capture_output=True, text=True, timeout=3600,
                )
                block = f"--- f-prot {path} ---\n{proc.stdout}{proc.stderr}"
                output_parts.append(block)
                last_code = proc.returncode
                # F-Prot : 0 = propre, 6 = infection(s), 3 = erreur
                if proc.returncode == 6 or "INFECTED" in proc.stdout.upper():
                    infected = True
                elif proc.returncode not in (0, 6):
                    error = True
            except Exception as exc:
                output_parts.append(f"Erreur F-Prot sur {path}: {exc}")
                error = True

        return ScannerResult(
            self.name, self.display_name, last_code, "\n".join(output_parts),
            infected=infected, error=error and not infected,
        )

    def update_signatures(self) -> tuple[bool, str]:
        bin_path = self._bin()
        if not bin_path:
            return False, "F-Prot non installé"
        updater = os.path.join(os.path.dirname(bin_path), "fp-update")
        if not os.path.isfile(updater):
            return False, "Utilitaire fp-update introuvable"
        try:
            proc = subprocess.run(
                [updater], capture_output=True, text=True, timeout=300
            )
            return proc.returncode == 0, proc.stdout + proc.stderr
        except Exception as exc:
            return False, str(exc)

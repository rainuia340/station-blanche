"""Scanner F-Prot Antivirus (gratuit usage personnel Linux)."""

import os

from scanners.base import BaseScanner, ScannerResult, run_subprocess

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

    def scan(self, paths, cancel_check=None, register_proc=None) -> ScannerResult:
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
            if cancel_check and cancel_check():
                return ScannerResult(
                    self.name, self.display_name, -1, "\n".join(output_parts), cancelled=True
                )
            try:
                code, stdout, stderr, cancelled = run_subprocess(
                    [bin_path, "-r", "-u", path],
                    cancel_check=cancel_check,
                    register_proc=register_proc,
                )
                if cancelled:
                    return ScannerResult(
                        self.name, self.display_name, -1, "\n".join(output_parts), cancelled=True
                    )
                block = f"--- f-prot {path} ---\n{stdout}{stderr}"
                output_parts.append(block)
                last_code = code
                if code == 6 or "INFECTED" in stdout.upper():
                    infected = True
                elif code not in (0, 6):
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
            code, stdout, stderr, _ = run_subprocess([updater])
            return code == 0, stdout + stderr
        except Exception as exc:
            return False, str(exc)

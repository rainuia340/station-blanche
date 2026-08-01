"""Scanner Linux Malware Detect (LMD / maldet)."""

import os

from scanners.base import BaseScanner, ScannerResult, run_subprocess


class MaldetScanner(BaseScanner):
    name = "maldet"
    display_name = "Linux Malware Detect (LMD)"

    def is_available(self) -> bool:
        return os.path.isfile("/usr/local/sbin/maldet")

    def scan(self, paths, cancel_check=None, register_proc=None) -> ScannerResult:
        if not self.is_available():
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
                    ["/usr/local/sbin/maldet", "-a", path],
                    cancel_check=cancel_check,
                    register_proc=register_proc,
                )
                if cancelled:
                    return ScannerResult(
                        self.name, self.display_name, -1, "\n".join(output_parts), cancelled=True
                    )
                block = f"--- maldet -a {path} ---\n{stdout}{stderr}"
                output_parts.append(block)
                last_code = code
                if code == 1:
                    infected = True
                elif code not in (0, 1):
                    error = True
            except Exception as exc:
                output_parts.append(f"Erreur maldet sur {path}: {exc}")
                error = True

        return ScannerResult(
            self.name, self.display_name, last_code, "\n".join(output_parts),
            infected=infected, error=error and not infected,
        )

    def update_signatures(self) -> tuple[bool, str]:
        try:
            code, stdout, stderr, _ = run_subprocess(["/usr/local/sbin/maldet", "-u"])
            return code == 0, stdout + stderr
        except Exception as exc:
            return False, str(exc)

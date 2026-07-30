"""Interface commune pour les moteurs antivirus."""

from dataclasses import dataclass


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

    @property
    def status_label(self) -> str:
        if self.skipped:
            return f"NON DISPONIBLE ({self.skip_reason})"
        if self.error:
            return "ERREUR"
        if self.infected:
            return "INFECTE"
        return "SAIN"


class BaseScanner:
    name = "base"
    display_name = "Base"

    def is_available(self) -> bool:
        raise NotImplementedError

    def scan(self, paths: list[str]) -> ScannerResult:
        raise NotImplementedError

    def update_signatures(self) -> tuple[bool, str]:
        return False, "Mise à jour non supportée"

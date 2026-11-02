"""Política de autorização de ferramentas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.settings import AuthLevel, Settings


DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-rf\b", re.I),
    re.compile(r"\bformat\b", re.I),
    re.compile(r"\bdel\s+/[sf]\b", re.I),
    re.compile(r"\bRemove-Item\b.*-Recurse\b.*-Force\b", re.I),
    re.compile(r"\bshutdown\b", re.I),
    re.compile(r"\breg\s+delete\b", re.I),
    re.compile(r"\bpowershell\b.*-EncodedCommand\b", re.I),
    re.compile(r"\bcmd\s*/c\b", re.I),
]


@dataclass
class AuthorizationResult:
    allowed: bool
    requires_confirmation: bool
    level: AuthLevel
    reason: str = ""


class SecurityPolicy:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pending: dict[str, dict[str, Any]] = {}

    def classify(self, tool_name: str, args: dict[str, Any], declared_level: AuthLevel) -> AuthorizationResult:
        if self.settings.automation.emergency_stop:
            return AuthorizationResult(
                allowed=False,
                requires_confirmation=False,
                level=declared_level,
                reason="Parada de emergência ativa.",
            )

        # Bloqueia shell arbitrário
        if tool_name in {"run_shell", "execute_command", "powershell", "cmd"}:
            if self.settings.security.block_shell_passthrough:
                return AuthorizationResult(
                    False,
                    False,
                    AuthLevel.CRITICAL,
                    "Execução arbitrária de shell é bloqueada por segurança.",
                )

        serialized = f"{tool_name} {args}"
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(serialized):
                return AuthorizationResult(
                    False,
                    False,
                    AuthLevel.CRITICAL,
                    f"Padrão perigoso detectado: {pattern.pattern}",
                )

        path_keys = ("path", "source", "destination", "file", "folder", "directory")
        for key in path_keys:
            if key in args and args[key]:
                ok, reason = self.validate_path(str(args[key]))
                if not ok:
                    return AuthorizationResult(False, False, AuthLevel.CRITICAL, reason)

        if declared_level <= self.settings.automation.auto_confirm_level:
            return AuthorizationResult(True, False, declared_level, "Ação simples autorizada.")

        if declared_level >= AuthLevel.CRITICAL:
            return AuthorizationResult(
                True,
                True,
                declared_level,
                "Ação crítica: confirmação explícita obrigatória.",
            )

        return AuthorizationResult(
            True,
            True,
            declared_level,
            "Ação que modifica dados: confirmação necessária.",
        )

    def validate_path(self, path_str: str) -> tuple[bool, str]:
        try:
            path = Path(path_str).expanduser().resolve()
        except Exception as exc:
            return False, f"Caminho inválido: {exc}"

        forbidden = [
            Path("C:/Windows").resolve(),
            Path("C:/Program Files").resolve(),
            Path("C:/Program Files (x86)").resolve(),
        ]
        for base in forbidden:
            try:
                path.relative_to(base)
                return False, f"Acesso bloqueado a área do sistema: {base}"
            except ValueError:
                pass

        allowed_roots = [Path(p).expanduser().resolve() for p in self.settings.automation.allowed_roots]
        if not allowed_roots:
            return True, ""
        for root in allowed_roots:
            try:
                path.relative_to(root)
                return True, ""
            except ValueError:
                continue
        # Permitir caminhos relativos ao usuário se a raiz incluir Users e o path estiver sob Users
        users = Path("C:/Users").resolve()
        try:
            path.relative_to(users)
            return True, ""
        except ValueError:
            return False, f"Caminho fora das raízes permitidas: {path}"

    def register_pending(self, token: str, payload: dict[str, Any]) -> None:
        self._pending[token] = payload

    def pop_pending(self, token: str) -> dict[str, Any] | None:
        return self._pending.pop(token, None)

    def set_emergency_stop(self, active: bool) -> None:
        self.settings.automation.emergency_stop = active
        self.settings.save()

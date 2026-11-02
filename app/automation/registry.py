"""Registro de ferramentas com níveis de autorização."""

from __future__ import annotations

import inspect
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.config.settings import AuthLevel, Settings
from app.core.logging_setup import get_logger
from app.memory.store import MemoryStore
from app.security.policy import SecurityPolicy

logger = get_logger("automation")


@dataclass
class ToolSpec:
    name: str
    description: str
    level: AuthLevel
    handler: Callable[..., Any]
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    level: AuthLevel = AuthLevel.SIMPLE


class ToolRegistry:
    def __init__(
        self,
        settings: Settings,
        policy: SecurityPolicy,
        memory: MemoryStore,
    ) -> None:
        self.settings = settings
        self.policy = policy
        self.memory = memory
        self._tools: dict[str, ToolSpec] = {}
        self._running = False

    def register(
        self,
        name: str,
        description: str,
        level: AuthLevel,
        handler: Callable[..., Any],
        parameters: dict[str, str] | None = None,
    ) -> None:
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            level=level,
            handler=handler,
            parameters=parameters or {},
        )

    def catalog_text(self) -> str:
        lines = []
        for tool in self._tools.values():
            params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items()) or "sem parâmetros"
            lines.append(
                f"- {tool.name} (nível {int(tool.level)}): {tool.description} | args={{ {params} }}"
            )
        return "\n".join(lines)

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return sorted(self._tools)

    async def execute(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        *,
        confirmed: bool = False,
        confirmation_token: str | None = None,
    ) -> ToolResult:
        args = args or {}
        if not self.settings.automation.enabled:
            return ToolResult(False, "Automação desabilitada nas configurações.")

        if self.policy.settings.automation.emergency_stop:
            return ToolResult(False, "Parada de emergência ativa. Nenhuma ação será executada.")

        tool = self._tools.get(name)
        if not tool:
            return ToolResult(False, f"Ferramenta desconhecida: {name}")

        if confirmation_token and not confirmed:
            pending = self.policy.pop_pending(confirmation_token)
            if not pending:
                return ToolResult(False, "Token de confirmação inválido ou expirado.")
            name = pending["name"]
            args = pending["args"]
            tool = self._tools[name]
            confirmed = True

        auth = self.policy.classify(name, args, tool.level)
        if not auth.allowed:
            self.memory.log_action(name, args, int(tool.level), "blocked", auth.reason)
            return ToolResult(False, auth.reason, level=tool.level)

        if auth.requires_confirmation and not confirmed:
            token = str(uuid.uuid4())
            self.policy.register_pending(token, {"name": name, "args": args})
            self.memory.log_action(name, args, int(tool.level), "awaiting_confirmation", auth.reason)
            return ToolResult(
                ok=False,
                message=auth.reason,
                requires_confirmation=True,
                confirmation_token=token,
                level=tool.level,
                data={"tool": name, "args": args},
            )

        timeout = self.settings.automation.action_timeout_seconds
        started = time.monotonic()
        self._running = True
        try:
            result = tool.handler(**args) if args else tool.handler()
            if inspect.isawaitable(result):
                result = await result
            elapsed = time.monotonic() - started
            if elapsed > timeout:
                msg = f"Ação excedeu timeout de {timeout}s."
                self.memory.log_action(name, args, int(tool.level), "timeout", msg)
                return ToolResult(False, msg, level=tool.level)
            message = result if isinstance(result, str) else str(result)
            self.memory.log_action(name, args, int(tool.level), "ok", message)
            return ToolResult(True, message, level=tool.level)
        except TypeError as exc:
            msg = f"Argumentos inválidos para {name}: {exc}"
            self.memory.log_action(name, args, int(tool.level), "error", msg)
            return ToolResult(False, msg, level=tool.level)
        except Exception as exc:
            msg = f"Falha ao executar {name}: {exc}"
            logger.exception(msg)
            self.memory.log_action(name, args, int(tool.level), "error", msg)
            return ToolResult(False, msg, level=tool.level)
        finally:
            self._running = False

    def emergency_stop(self) -> None:
        self.policy.set_emergency_stop(True)
        logger.warning("EMERGENCY STOP ativado")

"""Núcleo orquestrador do H.E.R.B."""

from __future__ import annotations

import asyncio
import re
import threading
from typing import Any

from app.automation.registry import ToolRegistry
from app.automation.tools import register_default_tools
from app.audio.pipeline import AudioPipeline
from app.config.personality import load_personality
from app.config.settings import Settings, get_settings
from app.core.events import EventBus, EventType
from app.core.logging_setup import get_logger, setup_logging
from app.intelligence.conversation import ConversationManager
from app.intelligence.ollama_client import OllamaClient, OllamaError
from app.memory.store import MemoryStore
from app.security.policy import SecurityPolicy
from app.vision.screen import ScreenAnalyzer

logger = get_logger("core")

SCREEN_INTENT = re.compile(
    r"(tela|screenshot|erro na tela|o que estou vendo|analis[ea] (isso|esse|essa))",
    re.I,
)


class HerbCore:
    """Fachada única usada pela interface."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        setup_logging(self.settings.log_level)
        self.bus = EventBus()
        self.memory = MemoryStore(self.settings.memory.db_path)
        self.ollama = OllamaClient(
            host=self.settings.ollama.host,
            timeout=self.settings.ollama.timeout_seconds,
            keep_alive=self.settings.ollama.keep_alive,
        )
        self.personality = load_personality()
        self.conversation = ConversationManager(
            self.settings,
            self.memory,
            self.ollama,
            self.personality,
        )
        self.policy = SecurityPolicy(self.settings)
        self.tools = ToolRegistry(self.settings, self.policy, self.memory)
        register_default_tools(self.tools)
        self.vision = ScreenAnalyzer(self.settings)
        self.audio = AudioPipeline(self.settings, self.bus)
        self.audio.set_transcription_handler(self._on_voice_text)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._pending_confirmations: dict[str, dict[str, Any]] = {}
        self._started = False

    def start_background_loop(self) -> None:
        if self._loop_thread and self._loop_thread.is_alive():
            return

        def runner() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(target=runner, name="herb-asyncio", daemon=True)
        self._loop_thread.start()
        # espera loop ficar pronto
        while self._loop is None:
            pass

    def run_coro(self, coro):
        self.start_background_loop()
        assert self._loop is not None
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def startup(self) -> dict[str, Any]:
        status: dict[str, Any] = {"ok": True, "warnings": []}
        healthy = await self.ollama.health()
        if not healthy:
            status["ok"] = False
            status["warnings"].append(
                "Ollama não respondeu em "
                f"{self.settings.ollama.host}. Inicie o Ollama e verifique a porta."
            )
        else:
            models = await self.ollama.list_models()
            status["models"] = models
            if not self.settings.ollama.primary_model and models:
                self.settings.ollama.primary_model = models[0]
                self.settings.save()
            if not models:
                status["warnings"].append(
                    "Nenhum modelo Ollama instalado. Recomendados para Ryzen 3 3200G / 16 GB: "
                    "llama3.2:3b, qwen2.5:3b, phi3:mini, gemma2:2b."
                )

        if self.settings.audio.enabled:
            try:
                self.audio.start()
            except Exception as exc:
                status["warnings"].append(f"Áudio não iniciado: {exc}")

        self._started = True
        self.bus.emit_simple(EventType.READY, status=status)
        self.bus.emit_simple(
            EventType.MESSAGE_ASSISTANT,
            text=f"{self.personality.name} online. Pronto quando você estiver.",
        )
        return status

    def startup_sync(self) -> dict[str, Any]:
        fut = self.run_coro(self.startup())
        return fut.result(timeout=60)

    async def shutdown(self) -> None:
        self.audio.stop()
        try:
            if self.settings.ollama.primary_model:
                await self.ollama.unload(self.settings.ollama.primary_model)
        finally:
            await self.ollama.aclose()
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self.bus.emit_simple(EventType.SHUTDOWN)
        logger.info("H.E.R.B. encerrado.")

    def shutdown_sync(self) -> None:
        fut = self.run_coro(self.shutdown())
        try:
            fut.result(timeout=15)
        except Exception:
            logger.exception("Erro no shutdown")

    async def handle_user_message(self, text: str, *, source: str = "text") -> str:
        text = (text or "").strip()
        if not text:
            return ""

        self.bus.emit_simple(EventType.MESSAGE_USER, text=text, source=source)
        self.bus.emit_simple(EventType.PROCESSING, active=True)

        try:
            # Comandos locais rápidos
            local = await self._handle_local_commands(text)
            if local is not None:
                self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=local)
                if source in {"voice", "hotkey"}:
                    await self.audio.speak(local)
                return local

            extra_context = None
            images = None
            if self.vision.looks_like_screen_request(text) or SCREEN_INTENT.search(text):
                self.bus.emit_simple(EventType.STATUS, text="Analisando a tela...")
                ctx = await asyncio.to_thread(self.vision.analyze, True)
                extra_context = self.vision.build_context_prompt(ctx)
                self.bus.emit_simple(EventType.SCREEN_CONTEXT, preview=ctx.text[:500], notes=ctx.notes)
                if (
                    self.settings.vision.use_multimodal
                    and self.settings.ollama.multimodal_model
                    and ctx.image_b64
                ):
                    images = [ctx.image_b64]

            result = await self.conversation.ask(
                text,
                extra_context=extra_context,
                tools_catalog=self.tools.catalog_text(),
                images_b64=images,
            )
            reply = result["text"]
            tool_call = result.get("tool_call")

            if tool_call:
                tool_name = tool_call["tool"]
                args = tool_call.get("args") or {}
                speak = tool_call.get("speak") or reply
                self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=speak)
                if self.settings.audio.tts_enabled:
                    await self.audio.speak(speak)
                tool_result = await self.tools.execute(tool_name, args)
                if tool_result.requires_confirmation:
                    token = tool_result.confirmation_token or ""
                    self._pending_confirmations[token] = {
                        "tool": tool_name,
                        "args": args,
                        "level": int(tool_result.level),
                    }
                    confirm_msg = (
                        f"Preciso da sua confirmação para '{tool_name}' "
                        f"(nível {int(tool_result.level)}). "
                        f"Args: {args}. Token: {token}"
                    )
                    self.bus.emit_simple(
                        EventType.CONFIRMATION_REQUIRED,
                        token=token,
                        tool=tool_name,
                        args=args,
                        message=confirm_msg,
                    )
                    self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=confirm_msg)
                    return confirm_msg

                follow = tool_result.message
                self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=follow)
                self.memory.add_message(self.conversation.conversation_id, "assistant", follow)
                if self.settings.audio.tts_enabled:
                    await self.audio.speak(follow)
                return follow

            self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=reply)
            if self.settings.audio.tts_enabled and source in {"voice", "hotkey", "text"}:
                # Fala respostas também do chat texto (configurável via tts_enabled)
                if source != "text" or self.settings.audio.tts_enabled:
                    # Para texto, só fala se explicitamente desejado — default: fala só voz/hotkey
                    if source in {"voice", "hotkey"}:
                        await self.audio.speak(reply)
            return reply

        except OllamaError as exc:
            msg = f"Não consegui falar com o Ollama: {exc}"
            logger.error(msg)
            self.bus.emit_simple(EventType.ERROR, message=msg)
            self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=msg)
            return msg
        except Exception as exc:
            msg = f"Erro inesperado ao processar mensagem: {exc}"
            logger.exception(msg)
            self.bus.emit_simple(EventType.ERROR, message=msg)
            self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=msg)
            return msg
        finally:
            self.bus.emit_simple(EventType.PROCESSING, active=False)

    def handle_user_message_sync(self, text: str, source: str = "text") -> str:
        fut = self.run_coro(self.handle_user_message(text, source=source))
        return fut.result(timeout=self.settings.ollama.timeout_seconds + 30)

    async def confirm_action(self, token: str, approved: bool) -> str:
        pending = self._pending_confirmations.pop(token, None)
        if not pending:
            # tenta policy
            pending = self.policy.pop_pending(token)
            if pending:
                pending = {"tool": pending["name"], "args": pending["args"]}
        if not pending:
            return "Não há ação pendente com esse token."
        if not approved:
            self.memory.log_action(pending["tool"], pending.get("args", {}), pending.get("level", 2), "denied", "Usuário negou")
            msg = "Ok, cancelei a ação."
            self.bus.emit_simple(EventType.CONFIRMATION_RESULT, token=token, approved=False)
            self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=msg)
            return msg
        result = await self.tools.execute(
            pending["tool"],
            pending.get("args", {}),
            confirmed=True,
            confirmation_token=token,
        )
        msg = result.message
        self.bus.emit_simple(EventType.CONFIRMATION_RESULT, token=token, approved=True, message=msg)
        self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text=msg)
        return msg

    def emergency_stop(self) -> None:
        self.tools.emergency_stop()
        self.audio.interrupt_speech()
        self.bus.emit_simple(EventType.EMERGENCY_STOP)
        self.bus.emit_simple(EventType.MESSAGE_ASSISTANT, text="Parada de emergência ativada. Automações bloqueadas.")

    def clear_emergency_stop(self) -> None:
        self.policy.set_emergency_stop(False)
        self.bus.emit_simple(EventType.STATUS, text="Parada de emergência desativada.")

    async def _handle_local_commands(self, text: str) -> str | None:
        lowered = text.strip().lower()
        if lowered in {"limpar memória", "apagar histórico", "clear memory"}:
            self.memory.clear_conversation(self.conversation.conversation_id)
            return "Histórico desta conversa apagado."
        if lowered in {"nova conversa", "new chat"}:
            self.conversation.new_conversation()
            return "Nova conversa iniciada."
        if lowered.startswith("confirmar ") or lowered.startswith("confirm "):
            token = text.split(maxsplit=1)[1].strip()
            return await self.confirm_action(token, True)
        if lowered.startswith("cancelar ") or lowered.startswith("deny "):
            token = text.split(maxsplit=1)[1].strip()
            return await self.confirm_action(token, False)
        if lowered in {"parada de emergência", "emergency stop", "stop emergency"}:
            self.emergency_stop()
            return "Parada de emergência ativada."
        if lowered in {"liberar emergência", "clear emergency"}:
            self.clear_emergency_stop()
            return "Emergência liberada."
        if lowered in {"status do sistema", "system status", "como está meu computador", "como esta meu computador"}:
            result = await self.tools.execute("system_info", {})
            # Personalidade leve
            return (
                "Dei uma olhada no ambiente.\n" + result.message
                if result.ok
                else result.message
            )
        if lowered.startswith("lembrar:"):
            note = text.split(":", 1)[1].strip()
            self.memory.add_note(note, tags=["user"])
            return "Anotado na memória local."
        return None

    def _on_voice_text(self, text: str, meta: dict[str, Any]) -> None:
        logger.info("Voz reconhecida: %s | meta=%s", text, meta)
        self.handle_user_message_sync(text, source="voice")

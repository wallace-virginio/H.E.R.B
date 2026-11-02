"""Cliente HTTP real para Ollama (local)."""

from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from app.core.logging_setup import get_logger

logger = get_logger("ollama")


class OllamaError(Exception):
    """Erro de comunicação/operação com Ollama."""


class OllamaClient:
    def __init__(
        self,
        host: str = "http://127.0.0.1:11434",
        timeout: float = 120.0,
        keep_alive: str = "5m",
    ) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._client = httpx.AsyncClient(base_url=self.host, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except httpx.HTTPError as exc:
            logger.warning("Ollama indisponível: %s", exc)
            return False

    async def list_models(self) -> list[str]:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models") or []
            return [m.get("name", "") for m in models if m.get("name")]
        except httpx.HTTPError as exc:
            raise OllamaError(f"Falha ao listar modelos: {exc}") from exc

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
        images: list[str] | None = None,
    ) -> str:
        if not model:
            raise OllamaError(
                "Nenhum modelo Ollama configurado. "
                "Execute `ollama pull <modelo>` e selecione um modelo nas configurações."
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if images:
            # Anexa imagens à última mensagem do usuário (API multimodal Ollama)
            msgs = [dict(m) for m in messages]
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i].get("role") == "user":
                    msgs[i]["images"] = images
                    break
            payload["messages"] = msgs

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            content = (data.get("message") or {}).get("content", "")
            if not content:
                raise OllamaError("Ollama retornou resposta vazia.")
            return content.strip()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise OllamaError(f"Erro HTTP Ollama ({exc.response.status_code}): {detail}") from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Falha de rede com Ollama: {exc}") from exc

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        if not model:
            raise OllamaError("Nenhum modelo Ollama configurado.")

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    import json

                    chunk = json.loads(line)
                    if chunk.get("done"):
                        break
                    piece = (chunk.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
        except httpx.HTTPError as exc:
            raise OllamaError(f"Falha no stream Ollama: {exc}") from exc

    async def unload(self, model: str) -> None:
        """Libera modelo da memória (keep_alive=0)."""
        try:
            await self._client.post(
                "/api/generate",
                json={"model": model, "keep_alive": 0, "prompt": ""},
            )
        except httpx.HTTPError as exc:
            logger.warning("Não foi possível descarregar modelo %s: %s", model, exc)

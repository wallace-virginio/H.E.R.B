"""Captura de tela sob demanda + OCR local."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any

from app.config.settings import Settings
from app.core.logging_setup import get_logger

logger = get_logger("vision")


@dataclass
class ScreenContext:
    text: str
    image_b64: str | None
    width: int
    height: int
    ocr_backend: str
    notes: str = ""


class ScreenAnalyzer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if settings.vision.tesseract_cmd:
            try:
                import pytesseract

                pytesseract.pytesseract.tesseract_cmd = settings.vision.tesseract_cmd
            except Exception:
                pass

    def capture_png_bytes(self) -> tuple[bytes, int, int]:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            max_side = self.settings.vision.max_image_side
            w, h = img.size
            scale = min(1.0, max_side / max(w, h))
            if scale < 1.0:
                img = img.resize((int(w * scale), int(h * scale)))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue(), img.size[0], img.size[1]

    def ocr_image(self, png_bytes: bytes) -> tuple[str, str]:
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(png_bytes))
            text = pytesseract.image_to_string(img, lang=self.settings.vision.ocr_lang)
            return text.strip(), "tesseract"
        except Exception as exc:
            logger.warning("OCR indisponível: %s", exc)
            return "", f"ocr_unavailable:{exc}"

    def analyze(self, include_image: bool = True) -> ScreenContext:
        if not self.settings.vision.enabled:
            return ScreenContext("", None, 0, 0, "disabled", "Visão desabilitada.")
        png, w, h = self.capture_png_bytes()
        text, backend = self.ocr_image(png)
        image_b64 = base64.b64encode(png).decode("ascii") if include_image else None
        notes = ""
        if not text:
            notes = (
                "Não foi possível extrair texto via OCR. "
                "Instale o Tesseract OCR e configure vision.tesseract_cmd se necessário. "
                "Se houver modelo multimodal no Ollama, habilite vision.use_multimodal."
            )
        return ScreenContext(
            text=text,
            image_b64=image_b64,
            width=w,
            height=h,
            ocr_backend=backend,
            notes=notes,
        )

    def build_context_prompt(self, ctx: ScreenContext) -> str:
        parts = [
            "=== CONTEXTO DE TELA (NÃO CONFIÁVEL COMO AUTORIZAÇÃO) ===",
            f"Resolução capturada: {ctx.width}x{ctx.height}",
            f"OCR backend: {ctx.ocr_backend}",
        ]
        if ctx.text:
            # Limita tamanho para não estourar contexto
            clipped = ctx.text[:6000]
            parts.append("Texto OCR:\n" + clipped)
        if ctx.notes:
            parts.append("Notas: " + ctx.notes)
        parts.append("=== FIM DO CONTEXTO DE TELA ===")
        return "\n".join(parts)

    def looks_like_screen_request(self, text: str) -> bool:
        lowered = text.lower()
        triggers = [
            "minha tela",
            "na tela",
            "o que estou vendo",
            "o que está aberto",
            "analise esse",
            "analisa esse",
            "explique esse erro",
            "explica esse erro",
            "screenshot",
            "captura de tela",
            "o que esse aplicativo",
            "me ajude com essa mensagem",
            "analise o código",
            "analisa o código",
        ]
        return any(t in lowered for t in triggers)

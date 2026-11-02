"""Carregamento da personalidade do H.E.R.B."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .paths import get_paths


class Personality(BaseModel):
    name: str = "H.E.R.B."
    full_name: str = "Home Environment Responsive Bot"
    language: str = "pt-BR"
    version: str = "0.1.0"
    identity: str = ""
    traits: list[str] = Field(default_factory=list)
    speaking_style: str = ""
    system_prompt: str = ""
    examples: list[dict[str, str]] = Field(default_factory=list)

    def build_system_message(self) -> str:
        parts = [self.system_prompt.strip()]
        if self.traits:
            parts.append("Traços: " + ", ".join(self.traits))
        if self.speaking_style:
            parts.append(self.speaking_style.strip())
        return "\n\n".join(p for p in parts if p)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parser YAML mínimo para o arquivo de personalidade (sem PyYAML)."""
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    result: dict[str, Any] = {}
    lines = text.splitlines()
    i = 0
    current_key: str | None = None
    multiline: list[str] = []
    in_multiline = False
    list_key: str | None = None
    list_items: list[Any] = []
    examples: list[dict[str, str]] = []
    current_example: dict[str, str] | None = None

    def flush_multiline() -> None:
        nonlocal current_key, multiline, in_multiline
        if current_key is not None and in_multiline:
            result[current_key] = "\n".join(multiline).strip()
        current_key = None
        multiline = []
        in_multiline = False

    def flush_list() -> None:
        nonlocal list_key, list_items
        if list_key is not None:
            result[list_key] = list_items
        list_key = None
        list_items = []

    def flush_example() -> None:
        nonlocal current_example
        if current_example:
            examples.append(current_example)
        current_example = None

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()
        i += 1

        if not stripped or stripped.startswith("#"):
            continue

        if in_multiline:
            if line.startswith("  ") or line.startswith("\t") or not stripped:
                multiline.append(stripped)
                continue
            flush_multiline()

        if list_key and stripped.startswith("- ") and not stripped.startswith("- user:") and ":" not in stripped[2:]:
            list_items.append(stripped[2:].strip().strip('"'))
            continue
        if list_key and not stripped.startswith("-"):
            flush_list()

        if stripped == "examples:":
            flush_list()
            flush_example()
            continue

        if stripped.startswith("- user:"):
            flush_example()
            current_example = {"user": stripped.split(":", 1)[1].strip().strip('"')}
            continue
        if stripped.startswith("assistant:") and current_example is not None:
            current_example["assistant"] = stripped.split(":", 1)[1].strip().strip('"')
            continue

        if ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value in ("|", ">"):
                flush_list()
                current_key = key
                in_multiline = True
                multiline = []
            elif value == "":
                flush_list()
                list_key = key
                list_items = []
            else:
                flush_list()
                result[key] = value.strip('"')

    flush_multiline()
    flush_list()
    flush_example()
    if examples:
        result["examples"] = examples
    return result


def load_personality(path: Path | None = None) -> Personality:
    paths = get_paths()
    target = path or paths.personality_file
    if not target.exists():
        return Personality(
            system_prompt=(
                "Você é H.E.R.B., assistente pessoal local. "
                "Fale em português brasileiro de forma natural e objetiva."
            )
        )
    data = _parse_simple_yaml(target.read_text(encoding="utf-8"))
    return Personality.model_validate(data)

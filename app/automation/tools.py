"""Ferramentas padrão de automação Windows."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
from pathlib import Path

import psutil

from app.config.settings import AuthLevel
from app.core.logging_setup import get_logger

from .registry import ToolRegistry

logger = get_logger("tools")


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(
        "open_app",
        "Abre um aplicativo conhecido (calculadora, notepad, explorer, browser).",
        AuthLevel.SIMPLE,
        open_app,
        {"name": "nome do app"},
    )
    registry.register(
        "open_path",
        "Abre uma pasta ou arquivo no Explorer.",
        AuthLevel.SIMPLE,
        open_path,
        {"path": "caminho absoluto"},
    )
    registry.register(
        "open_url",
        "Abre uma URL no navegador padrão.",
        AuthLevel.SIMPLE,
        open_url,
        {"url": "https://..."},
    )
    registry.register(
        "system_info",
        "Retorna informações básicas do sistema (CPU, RAM, disco).",
        AuthLevel.SIMPLE,
        system_info,
        {},
    )
    registry.register(
        "search_files",
        "Pesquisa arquivos por nome em um diretório.",
        AuthLevel.SIMPLE,
        search_files,
        {"directory": "pasta base", "pattern": "parte do nome", "limit": "máximo de resultados"},
    )
    registry.register(
        "create_file",
        "Cria um arquivo de texto com conteúdo.",
        AuthLevel.MODIFY,
        create_file,
        {"path": "caminho", "content": "texto"},
    )
    registry.register(
        "create_directory",
        "Cria um diretório.",
        AuthLevel.MODIFY,
        create_directory,
        {"path": "caminho"},
    )
    registry.register(
        "move_path",
        "Move arquivo ou pasta.",
        AuthLevel.MODIFY,
        move_path,
        {"source": "origem", "destination": "destino"},
    )
    registry.register(
        "type_text",
        "Digita texto na janela ativa (PyAutoGUI).",
        AuthLevel.MODIFY,
        type_text,
        {"text": "texto a digitar"},
    )
    registry.register(
        "delete_path",
        "Exclui arquivo ou pasta (ação crítica).",
        AuthLevel.CRITICAL,
        delete_path,
        {"path": "caminho"},
    )


KNOWN_APPS = {
    "calculadora": "calc.exe",
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "bloco de notas": "notepad.exe",
    "explorer": "explorer.exe",
    "explorador": "explorer.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "paint": "mspaint.exe",
    "browser": None,
    "navegador": None,
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "msedge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
}


def open_app(name: str) -> str:
    key = name.strip().lower()
    target = KNOWN_APPS.get(key, name)
    if target is None or key in {"browser", "navegador"}:
        webbrowser.open("https://www.google.com")
        return "Navegador aberto."
    path = Path(target)
    if path.exists():
        os.startfile(str(path))  # noqa: S606
        return f"Abrindo {path.name}."
    # Tenta via PATH / shell
    try:
        subprocess.Popen([target], shell=False)  # noqa: S603
        return f"Abrindo {target}."
    except Exception:
        subprocess.Popen(f'start "" "{target}"', shell=True)  # noqa: S602
        return f"Solicitado início de {target}."


def open_path(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Caminho não encontrado: {p}")
    os.startfile(str(p))  # noqa: S606
    return f"Aberto: {p}"


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Abrindo {url}"


def system_info() -> str:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    cpu = psutil.cpu_percent(interval=0.3)
    return (
        f"Sistema: {platform.system()} {platform.release()} ({platform.machine()})\n"
        f"CPU: {cpu:.0f}% | Núcleos lógicos: {psutil.cpu_count()}\n"
        f"RAM: {vm.percent:.0f}% usada ({vm.used // (1024**2)} / {vm.total // (1024**2)} MB)\n"
        f"Disco C: {disk.percent:.0f}% usado ({disk.used // (1024**3)} / {disk.total // (1024**3)} GB)"
    )


def search_files(directory: str, pattern: str, limit: int = 20) -> str:
    base = Path(directory).expanduser()
    if not base.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {base}")
    limit = int(limit)
    matches: list[str] = []
    needle = pattern.lower()
    for root, _dirs, files in os.walk(base):
        for name in files:
            if needle in name.lower():
                matches.append(str(Path(root) / name))
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break
    if not matches:
        return "Nenhum arquivo encontrado."
    return "Encontrados:\n" + "\n".join(matches)


def create_file(path: str, content: str = "") -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"Arquivo criado: {p}"


def create_directory(path: str) -> str:
    p = Path(path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return f"Diretório criado: {p}"


def move_path(source: str, destination: str) -> str:
    src = Path(source).expanduser()
    dst = Path(destination).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"Origem não encontrada: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"Movido: {src} → {dst}"


def type_text(text: str) -> str:
    try:
        import pyautogui
    except ImportError as exc:
        raise RuntimeError("PyAutoGUI não instalado.") from exc
    pyautogui.typewrite(text, interval=0.02)
    return "Texto digitado na janela ativa."


def delete_path(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Não encontrado: {p}")
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    return f"Excluído: {p}"

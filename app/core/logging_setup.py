"""Configuração de logging do H.E.R.B."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config.paths import get_paths


def setup_logging(level: str = "INFO") -> logging.Logger:
    paths = get_paths()
    paths.logs.mkdir(parents=True, exist_ok=True)
    log_file = paths.logs / "herb.log"

    root = logging.getLogger("herb")
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.propagate = False

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return root


def get_logger(name: str) -> logging.Logger:
    if not name.startswith("herb"):
        name = f"herb.{name}"
    return logging.getLogger(name)

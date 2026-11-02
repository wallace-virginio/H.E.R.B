#!/usr/bin/env python3
"""Ponto de entrada do H.E.R.B."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Garante import do pacote app quando executado diretamente
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _crash_dialog(message: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "H.E.R.B. — Erro fatal", message)
        app.quit()
    except Exception:
        print(message, file=sys.stderr)
        input("Pressione Enter para sair...")


def main() -> int:
    try:
        from app.config.paths import get_paths
        from app.core.logging_setup import setup_logging
        from app.interface.main_window import run_interface

        paths = get_paths()
        paths.ensure()
        setup_logging("INFO")
        return run_interface()
    except KeyboardInterrupt:
        return 0
    except Exception:
        tb = traceback.format_exc()
        log_path = ROOT / "logs" / "crash.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(tb, encoding="utf-8")
        except Exception:
            pass
        _crash_dialog(
            "O H.E.R.B. encontrou um erro e não pode continuar.\n\n"
            f"{tb}\n\nDetalhes também em logs/crash.log"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

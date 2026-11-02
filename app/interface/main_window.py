"""Janela flutuante principal do H.E.R.B."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from app.config.paths import get_paths
from app.config.settings import get_settings, reload_settings
from app.core.app_core import HerbCore
from app.core.events import EventType, HerbEvent
from app.core.logging_setup import get_logger
from app.interface.onboarding import OnboardingDialog

logger = get_logger("ui")


class CoreBridge(QObject):
    """Sinais Qt para eventos vindos de outras threads."""

    user_message = Signal(str)
    assistant_message = Signal(str)
    status = Signal(str)
    error = Signal(str)
    listening = Signal(bool)
    processing = Signal(bool)
    speaking = Signal(bool)
    confirmation = Signal(str, str, dict)
    ready = Signal(dict)


class HerbWindow(QWidget):
    def __init__(self, core: HerbCore) -> None:
        super().__init__()
        self.core = core
        self.settings = core.settings
        self.bridge = CoreBridge()
        self._drag_pos = None
        self._opacity = self.settings.interface.opacity

        self.setObjectName("HerbRoot")
        self.setWindowTitle("H.E.R.B.")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | (Qt.WindowType.WindowStaysOnTopHint if self.settings.interface.always_on_top else Qt.WindowType.Widget)
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.resize(self.settings.interface.width, self.settings.interface.height)
        self.setWindowOpacity(self._opacity)

        self._build_ui()
        self._apply_styles()
        self._setup_tray()
        self._connect_bridge()
        self._subscribe_events()
        self._setup_hotkey()

        QTimer.singleShot(100, self._bootstrap)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QHBoxLayout()
        self.title = QLabel("H.E.R.B.")
        self.title.setObjectName("TitleLabel")
        self.status_label = QLabel("Inicializando...")
        self.status_label.setObjectName("StatusLabel")
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.status_label)
        root.addLayout(header)

        indicators = QHBoxLayout()
        self.mic_ind = QLabel("MIC")
        self.mic_ind.setObjectName("Indicator")
        self.proc_ind = QLabel("PROC")
        self.proc_ind.setObjectName("Indicator")
        self.speak_ind = QLabel("TTS")
        self.speak_ind.setObjectName("Indicator")
        for w in (self.mic_ind, self.proc_ind, self.speak_ind):
            w.setProperty("active", False)
            indicators.addWidget(w)
        indicators.addStretch()
        root.addLayout(indicators)

        self.chat = QListWidget()
        self.chat.setObjectName("ChatList")
        root.addWidget(self.chat, stretch=1)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setObjectName("InputField")
        self.input.setPlaceholderText("Fale com o H.E.R.B. ou digite aqui...")
        self.input.returnPressed.connect(self._send_text)
        self.send_btn = QPushButton("Enviar")
        self.send_btn.clicked.connect(self._send_text)
        row.addWidget(self.input, stretch=1)
        row.addWidget(self.send_btn)
        root.addLayout(row)

        controls = QHBoxLayout()
        self.mic_btn = QPushButton("Microfone")
        self.mic_btn.setObjectName("MicButton")
        self.mic_btn.setProperty("listening", True)
        self.mic_btn.clicked.connect(self._toggle_mic)
        self.tray_btn = QPushButton("Bandeja")
        self.tray_btn.clicked.connect(self.hide_to_tray)
        self.stop_btn = QPushButton("STOP")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.clicked.connect(self._emergency)
        self.close_btn = QPushButton("Encerrar")
        self.close_btn.clicked.connect(self._quit_app)
        for b in (self.mic_btn, self.tray_btn, self.stop_btn, self.close_btn):
            controls.addWidget(b)
        root.addLayout(controls)

    def _apply_styles(self) -> None:
        qss = get_paths().assets / "styles" / "herb.qss"
        if qss.exists():
            self.setStyleSheet(qss.read_text(encoding="utf-8"))

    def _make_icon(self) -> QIcon:
        pix = QPixmap(64, 64)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(20, 140, 200))
        painter.setPen(QColor(100, 220, 255))
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor(230, 248, 255))
        font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "H")
        painter.end()
        return QIcon(pix)

    def _setup_tray(self) -> None:
        self.tray = QSystemTrayIcon(self._make_icon(), self)
        self.tray.setToolTip("H.E.R.B.")
        menu = QMenu()
        show_action = QAction("Mostrar", self)
        show_action.triggered.connect(self.show_from_tray)
        hide_action = QAction("Minimizar", self)
        hide_action.triggered.connect(self.hide_to_tray)
        quit_action = QAction("Encerrar", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addAction(hide_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _connect_bridge(self) -> None:
        self.bridge.user_message.connect(lambda t: self._add_chat("Você", t))
        self.bridge.assistant_message.connect(lambda t: self._add_chat("HERB", t))
        self.bridge.status.connect(self._set_status)
        self.bridge.error.connect(self._show_error)
        self.bridge.listening.connect(lambda a: self._set_indicator(self.mic_ind, a))
        self.bridge.processing.connect(lambda a: self._set_indicator(self.proc_ind, a))
        self.bridge.speaking.connect(lambda a: self._set_indicator(self.speak_ind, a))
        self.bridge.confirmation.connect(self._on_confirmation)
        self.bridge.ready.connect(self._on_ready)

    def _subscribe_events(self) -> None:
        bus = self.core.bus

        def on_event(event: HerbEvent) -> None:
            p = event.payload
            if event.type == EventType.MESSAGE_USER:
                self.bridge.user_message.emit(p.get("text", ""))
            elif event.type == EventType.MESSAGE_ASSISTANT:
                self.bridge.assistant_message.emit(p.get("text", ""))
            elif event.type == EventType.STATUS:
                self.bridge.status.emit(p.get("text", ""))
            elif event.type == EventType.ERROR:
                self.bridge.error.emit(p.get("message", "Erro"))
            elif event.type == EventType.LISTENING:
                self.bridge.listening.emit(bool(p.get("active")))
            elif event.type == EventType.PROCESSING:
                self.bridge.processing.emit(bool(p.get("active")))
            elif event.type == EventType.SPEAKING:
                self.bridge.speaking.emit(bool(p.get("active")))
            elif event.type == EventType.CONFIRMATION_REQUIRED:
                self.bridge.confirmation.emit(
                    p.get("token", ""),
                    p.get("message", ""),
                    {"tool": p.get("tool"), "args": p.get("args")},
                )
            elif event.type == EventType.READY:
                self.bridge.ready.emit(p.get("status", {}))
            elif event.type == EventType.MIC_TOGGLED:
                enabled = bool(p.get("enabled"))
                self.mic_btn.setProperty("listening", enabled)
                self.mic_btn.setText("Microfone" if enabled else "Mic OFF")
                self.mic_btn.style().unpolish(self.mic_btn)
                self.mic_btn.style().polish(self.mic_btn)

        for et in EventType:
            bus.subscribe(et, on_event)

    def _setup_hotkey(self) -> None:
        try:
            import keyboard

            hotkey = self.settings.interface.global_hotkey
            keyboard.add_hotkey(hotkey, self._hotkey_triggered)
            logger.info("Atalho global registrado: %s", hotkey)
        except Exception as exc:
            logger.warning("Não foi possível registrar atalho global: %s", exc)
            self._set_status(f"Atalho global indisponível: {exc}")

    def _hotkey_triggered(self) -> None:
        # keyboard callback em outra thread
        QTimer.singleShot(0, self._on_hotkey)

    @Slot()
    def _on_hotkey(self) -> None:
        self.show_from_tray()
        self.core.audio.trigger_listen_once()
        self._set_status("Atalho: escutando...")
        self.core.audio.interrupt_speech()

    def _bootstrap(self) -> None:
        try:
            models: list[str] = []
            fut = self.core.run_coro(self.core.ollama.list_models())
            try:
                models = fut.result(timeout=5)
            except Exception:
                models = []
            OnboardingDialog.maybe_run(self.settings, models, self)
            reload_settings()
            self.core.settings = get_settings()
            status = self.core.startup_sync()
            if not status.get("ok"):
                self._show_error("; ".join(status.get("warnings") or ["Falha na inicialização"]))
            elif status.get("warnings"):
                self._set_status(" | ".join(status["warnings"])[:120])
            else:
                self._set_status("Online")
        except Exception as exc:
            logger.exception("Bootstrap falhou")
            QMessageBox.critical(
                self,
                "H.E.R.B.",
                f"Falha na inicialização:\n{exc}\n\nO aplicativo permanecerá aberto para diagnóstico.",
            )
            self._set_status("Erro na inicialização")

    def _add_chat(self, who: str, text: str) -> None:
        if not text:
            return
        item = QListWidgetItem(f"{who}: {text}")
        self.chat.addItem(item)
        self.chat.scrollToBottom()

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _set_indicator(self, label: QLabel, active: bool) -> None:
        label.setProperty("active", active)
        label.style().unpolish(label)
        label.style().polish(label)

    def _show_error(self, message: str) -> None:
        self._set_status("Erro")
        self._add_chat("Sistema", message)

    @Slot()
    def _send_text(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self._set_status("Processando...")
        # Não bloqueia UI
        self.core.run_coro(self.core.handle_user_message(text, source="text"))

    @Slot()
    def _toggle_mic(self) -> None:
        enabled = self.core.audio.toggle_mic()
        self._set_status("Microfone ligado" if enabled else "Microfone desligado")

    @Slot()
    def _emergency(self) -> None:
        self.core.emergency_stop()
        QMessageBox.warning(self, "STOP", "Parada de emergência ativada.")

    def _on_confirmation(self, token: str, message: str, data: dict) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Confirmação necessária")
        box.setText(message)
        box.setInformativeText("Deseja autorizar esta ação?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        result = box.exec()
        approved = result == QMessageBox.StandardButton.Yes
        self.core.run_coro(self.core.confirm_action(token, approved))

    def _on_ready(self, status: dict) -> None:
        if status.get("ok"):
            self._set_status("Online")
        else:
            self._set_status("Degradado")

    def hide_to_tray(self) -> None:
        self.hide()
        self.tray.showMessage("H.E.R.B.", "Rodando em segundo plano.", QSystemTrayIcon.MessageIcon.Information, 2000)

    def show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide_to_tray()
            else:
                self.show_from_tray()

    def _quit_app(self) -> None:
        try:
            self.core.shutdown_sync()
        finally:
            QApplication.instance().quit()

    # Arrastar janela sem moldura
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_pos = None


def run_interface() -> int:
    settings = get_settings()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("H.E.R.B.")

    core = HerbCore(settings)
    window = HerbWindow(core)
    if settings.interface.start_minimized_to_tray:
        window.hide_to_tray()
    else:
        window.show()
    return app.exec()

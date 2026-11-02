"""Assistente de primeira execução."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.audio.devices import list_input_devices, list_output_devices
from app.config.settings import Settings


class OnboardingDialog(QDialog):
    def __init__(self, settings: Settings, models: list[str], parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("H.E.R.B. — Configuração inicial")
        self.setModal(True)
        self.resize(480, 420)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Bem-vindo. Vamos configurar o básico para o H.E.R.B. funcionar localmente.\n"
            "Nenhuma API paga é necessária."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.model_box = QComboBox()
        if models:
            self.model_box.addItems(models)
            if settings.ollama.primary_model in models:
                self.model_box.setCurrentText(settings.ollama.primary_model)
        else:
            self.model_box.addItem("(nenhum modelo detectado)")
            self.model_box.setEnabled(False)

        self.wake_edit = QLineEdit(settings.audio.wake_word)
        self.kokoro_edit = QLineEdit(settings.audio.kokoro_path)
        self.kokoro_edit.setPlaceholderText(r"Caminho do Kokoro (opcional)")

        self.input_box = QComboBox()
        self.input_box.addItem("Padrão do sistema", None)
        for device in list_input_devices():
            self.input_box.addItem(f"[{device.index}] {device.name}", device.index)

        self.output_box = QComboBox()
        self.output_box.addItem("Padrão do sistema", None)
        for device in list_output_devices():
            self.output_box.addItem(f"[{device.index}] {device.name}", device.index)

        form.addRow("Modelo Ollama", self.model_box)
        form.addRow("Wake word", self.wake_edit)
        form.addRow("Kokoro path", self.kokoro_edit)
        form.addRow("Microfone", self.input_box)
        form.addRow("Saída de áudio", self.output_box)
        layout.addLayout(form)

        tips = QLabel(
            "Dicas de modelos leves para Ryzen 3 3200G / 16 GB RAM:\n"
            "• ollama pull llama3.2:3b\n"
            "• ollama pull qwen2.5:3b\n"
            "• ollama pull phi3:mini"
        )
        tips.setWordWrap(True)
        layout.addWidget(tips)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if not models:
            QMessageBox.warning(
                self,
                "Ollama sem modelos",
                "Nenhum modelo encontrado. Instale um modelo com `ollama pull llama3.2:3b` "
                "e execute novamente. Você ainda pode salvar as outras configurações.",
            )

    def _save(self) -> None:
        model = self.model_box.currentText()
        if model and not model.startswith("("):
            self.settings.ollama.primary_model = model
        self.settings.audio.wake_word = self.wake_edit.text().strip() or "HERB"
        self.settings.audio.kokoro_path = self.kokoro_edit.text().strip()
        self.settings.audio.input_device = self.input_box.currentData()
        self.settings.audio.output_device = self.output_box.currentData()
        self.settings.first_run_completed = True
        self.settings.interface.show_onboarding = False
        self.settings.save()
        self.accept()

    @staticmethod
    def maybe_run(settings: Settings, models: list[str], parent=None) -> Settings:
        if settings.first_run_completed and not settings.interface.show_onboarding:
            return settings
        dialog = OnboardingDialog(settings, models, parent)
        dialog.exec()
        return settings

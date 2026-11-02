# Changelog

## [0.1.0] — 2026-11-02

### Added
- Projeto H.E.R.B. inicial funcional para Windows 11.
- Núcleo orquestrador com EventBus, asyncio e fachada única para a UI.
- Cliente Ollama real (listagem de modelos, chat, unload/keep_alive).
- Memória SQLite: conversas, preferências, logs de ação e notas.
- Personalidade em `app/config/personality.yaml`.
- Interface flutuante PySide6 (transparência, indicadores, bandeja, STOP).
- Atalho global `CTRL+ALT+SPACE`.
- Pipeline de voz: sounddevice + VAD + Faster-Whisper + Kokoro/SAPI.
- Wake word textual `HERB` e ativação por hotkey.
- Reconhecimento de locutor local (baseline) + script de cadastro.
- Visão sob demanda: MSS + OCR Tesseract + gancho multimodal.
- Automação Windows com Tool Registry e confirmações por nível.
- Scripts `setup.bat`, `start_herb.bat`, `stop_herb.bat`, `check_environment.bat`.
- Testes pytest para settings, memória, Ollama (mock), segurança, tools e conversas.
- Documentação de voz, visão, ferramentas e status.

### Security
- Bloqueio de shell arbitrário.
- Validação de caminhos e padrões perigosos.
- Conteúdo de tela tratado como não confiável.
- Parada de emergência.

### Notes
- Otimizado para CPU (sem CUDA). Modelos grandes não são incluídos no ZIP.

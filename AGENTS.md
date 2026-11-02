# AGENTS.md — guia para agentes/IA trabalhando no H.E.R.B.

## Princípios

- Privacidade e execução local primeiro. Sem APIs pagas obrigatórias.
- A UI não fala com Ollama/automações diretamente — use `HerbCore`.
- Não simule integrações de áudio/LLM. Se algo faltar, documente em `docs/STATUS.md`.
- Não execute shell arbitrário via LLM.

## Layout

- `app/core` — orquestração
- `app/intelligence` — Ollama + conversas
- `app/audio` — STT/TTS/VAD/wake/speaker
- `app/vision` — captura/OCR
- `app/automation` — ferramentas
- `app/security` — políticas
- `app/memory` — SQLite
- `app/interface` — PySide6
- `app/config` — settings + personalidade

## Como testar

```bat
.venv\Scripts\activate
pytest -q
```

## Ao adicionar features

1. Preferir módulos pequenos e testáveis
2. Registrar ferramentas com nível de risco correto
3. Atualizar `CHANGELOG.md` e `docs/STATUS.md`
4. Manter português brasileiro na UX

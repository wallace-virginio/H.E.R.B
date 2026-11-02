# Status das funcionalidades — v0.1.0

## Implementado

- Estrutura modular completa
- Interface flutuante PySide6 + bandeja
- Chat texto real via Ollama
- Personalidade configurável (`personality.yaml`)
- Memória SQLite (conversas, preferências, ações, notas)
- Configuração JSON + `.env`
- Scripts setup/start/stop/check
- Tool Registry com níveis 1/2/3
- Política de segurança (paths, shell, padrões perigosos)
- Captura de tela sob demanda + OCR
- Pipeline de áudio (mic, VAD, STT, TTS, anti-eco)
- Atalho global CTRL+ALT+SPACE
- Wake word textual HERB
- Cadastro/comparação de locutor (baseline MFCC/FFT)
- Onboarding de primeiro uso
- Testes automatizados com mocks

## Parcial

- Kokoro: integração real com fallback SAPI se não configurado
- openWakeWord: estrutura pronta; modelo customizado HERB não incluso
- Silero VAD: tenta carregar; fallback energia
- Multimodal Ollama: suportado se modelo configurado
- PyWinAuto: dependência presente; ferramentas avançadas de UI ainda mínimas
- Digitar texto (PyAutoGUI): implementado, sensível ao foco da janela

## Pendente / futuro

- Treino de modelo openWakeWord dedicado "HERB"
- Embeddings + RAG vetorial
- UI de configurações completa dentro do app
- Mais automações PyWinAuto por aplicativo
- Embalagem instalador MSI/EXE

# H.E.R.B. — Home Environment Responsive Bot

Assistente pessoal local para Windows 11, inspirado no J.A.R.V.I.S., com foco em **privacidade**, **offline** e **hardware acessível** (CPU-first).

Versão: **0.1.0**

## O que funciona nesta versão

1. Interface flutuante (estilo overlay) + bandeja do sistema  
2. Chat por texto com modelos reais do **Ollama**  
3. Personalidade configurável + histórico SQLite  
4. Voz: microfone → Faster-Whisper → resposta → Kokoro/SAPI  
5. Wake word textual **HERB** + atalho **CTRL+ALT+SPACE**  
6. Análise de tela sob demanda (OCR)  
7. Automação Windows com confirmações por nível de risco  

Detalhes honestos: [`docs/STATUS.md`](docs/STATUS.md)

## Hardware alvo

- Ryzen 3 3200G / 16 GB RAM / RX 580 (sem CUDA)  
- Modelos recomendados:
  - `llama3.2:3b`
  - `qwen2.5:3b`
  - `phi3:mini`
  - `gemma2:2b`

```bat
ollama pull llama3.2:3b
```

## Instalação rápida

Pré-requisitos:

- Python **3.12**
- [Ollama](https://ollama.com) instalado e rodando
- (Opcional) Kokoro TTS local
- (Opcional) [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) com idiomas `por`+`eng`

```bat
cd C:\Herb
setup.bat
start_herb.bat
```

Diagnóstico:

```bat
check_environment.bat
```

Encerrar:

```bat
stop_herb.bat
```

## Primeiro uso

Ao abrir pela primeira vez, o onboarding permite:

- selecionar modelo Ollama detectado
- definir wake word
- apontar pasta do Kokoro
- escolher dispositivos de áudio

## Configuração

Arquivo principal: `data/config.json` (gerado no setup)  
Overrides opcionais: `.env` (veja `.env.example`)  
Personalidade: `app/config/personality.yaml`

## Voz / Kokoro / Wake word / Locutor

Veja [`docs/VOICE.md`](docs/VOICE.md)

Cadastro de voz:

```bat
.venv\Scripts\activate
python scripts\enroll_speaker.py --seconds 4 --speaker owner
```

## Análise de tela

Diga, por exemplo: `HERB, o que está na minha tela?`  
Documentação: [`docs/VISION.md`](docs/VISION.md)

## Novas ferramentas

Documentação: [`docs/TOOLS.md`](docs/TOOLS.md)

## Testes

```bat
.venv\Scripts\activate
pytest -q
```

## Estrutura

```
HERB/
├── app/                 # código modular
├── assets/              # estilos/ícones
├── data/                # config, memória, speakers
├── docs/                # documentação
├── tests/               # pytest
├── scripts/             # utilitários
├── main.py
├── setup.bat
├── start_herb.bat
├── stop_herb.bat
└── check_environment.bat
```

## Segurança

- Sem shell arbitrário via LLM  
- Confirmação para ações nível 2+  
- STOP de emergência na UI  
- Texto da tela tratado como não confiável  

## Licença de uso

Projeto pessoal/local. Dependências seguem suas respectivas licenças.

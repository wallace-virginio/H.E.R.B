# Voz no H.E.R.B.

## Pipeline

1. Captura (`sounddevice`)
2. VAD (Silero se disponível; senão energia RMS)
3. Wake word (`HERB`) — match textual via Faster-Whisper; openWakeWord preparado
4. STT (Faster-Whisper CPU INT8)
5. LLM (Ollama)
6. TTS (Kokoro se configurado; fallback SAPI Windows)
7. Reprodução (`sounddevice`)

## Kokoro

1. Baixe/clone o Kokoro TTS em um diretório local.
2. Em `data/config.json`, defina `audio.kokoro_path` para essa pasta.
3. Se usar `kokoro-onnx`, coloque `kokoro-v1.0.onnx` e `voices.bin` no caminho.
4. Reinicie o H.E.R.B.

Sem Kokoro, o sistema usa a voz SAPI local (ainda offline).

## Wake word

- Padrão: `HERB`
- Ativação também por `CTRL + ALT + SPACE`
- openWakeWord está integrado estruturalmente; modelo customizado "HERB" ainda não é distribuído
- Enquanto isso, a detecção usa STT curto + match textual (aliases: herb/herbe)

Para desativar: `audio.wake_word_enabled = false`

## Cadastro de voz (locutor)

```bat
.venv\Scripts\activate
python scripts\enroll_speaker.py --seconds 4 --speaker owner
```

Repita 3–5 vezes. Arquivos ficam em `data/speakers/`.

**Importante:** reconhecimento de locutor NÃO autoriza ações críticas sozinho.

## Barge-in / anti-eco

- `audio.mute_mic_while_speaking = true` evita capturar a própria TTS
- `audio.barge_in_enabled = true` permite interromper com o atalho global

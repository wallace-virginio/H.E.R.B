# Visão e contexto de tela

A captura **não** é contínua. Só ocorre quando o usuário pede (ex.: "o que está na minha tela?").

## Fluxo

1. MSS captura o monitor principal
2. Imagem é redimensionada (`vision.max_image_side`)
3. OCR local via Tesseract (`pytesseract`)
4. Texto OCR entra no prompt como **contexto não confiável**
5. Opcional: envia imagem ao modelo multimodal do Ollama se `vision.use_multimodal=true` e `ollama.multimodal_model` estiver definido

## Tesseract no Windows

1. Instale: https://github.com/UB-Mannheim/tesseract/wiki
2. Inclua pacotes de idioma `por` e `eng`
3. Configure `vision.tesseract_cmd`, por exemplo:
   `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`

## Modelos multimodais sugeridos (leves)

- `llava:7b` (pesado para 16 GB — use com cautela)
- Preferível manter OCR + LLM texto em hardware Ryzen 3 3200G

## Segurança

Texto lido da tela **nunca** é tratado como autorização para executar ferramentas.

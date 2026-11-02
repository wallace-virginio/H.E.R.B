@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
  echo Ambiente virtual nao encontrado. Execute setup.bat primeiro.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo Verificando Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Ollama nao esta no PATH. O chat pode falhar ate o servico iniciar.
) else (
  rem Tenta garantir que o servico responda
  ollama list >nul 2>&1
)

echo Iniciando H.E.R.B...
python main.py
if errorlevel 1 (
  echo.
  echo H.E.R.B. encerrou com erro. Veja logs\herb.log ou logs\crash.log
  pause
)
endlocal

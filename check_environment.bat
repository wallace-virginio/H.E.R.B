@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo   H.E.R.B. Environment Check
echo ============================================
echo.

set "ERR=0"

where py >nul 2>&1 && set "PY=py -3.12"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [FALHA] Python nao encontrado
  set "ERR=1"
) else (
  echo [OK] Python launcher
  %PY% --version
)

if exist ".venv\Scripts\python.exe" (
  echo [OK] Ambiente virtual .venv
  call ".venv\Scripts\activate.bat"
  python -c "import PySide6, httpx, pydantic, sounddevice; print('[OK] Dependencias principais')" 2>nul || (
    echo [FALHA] Dependencias Python incompletas — rode setup.bat
    set "ERR=1"
  )
  python -c "import faster_whisper; print('[OK] faster-whisper')" 2>nul || echo [AVISO] faster-whisper ausente
) else (
  echo [AVISO] .venv nao existe — rode setup.bat
)

where ollama >nul 2>&1
if errorlevel 1 (
  echo [FALHA] Ollama nao encontrado no PATH
  set "ERR=1"
) else (
  echo [OK] Ollama no PATH
  ollama list
)

echo.
echo Dispositivos de audio / modelos:
if exist ".venv\Scripts\python.exe" (
  python scripts\check_env.py
)

echo.
if "%ERR%"=="0" (
  echo Resultado: ambiente aparentemente ok.
) else (
  echo Resultado: ha problemas a corrigir.
)
pause
endlocal

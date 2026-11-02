@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo   H.E.R.B. Setup
echo ============================================
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PY=py -3.12"
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    set "PY=python"
  ) else (
    echo [ERRO] Python nao encontrado no PATH.
    echo Instale Python 3.12: https://www.python.org/downloads/
    echo Marque "Add python.exe to PATH" na instalacao.
    pause
    exit /b 1
  )
)

echo [1/6] Verificando Python...
%PY% -c "import sys; assert sys.version_info[:2] >= (3,12), f'Precisa Python 3.12+, encontrado {sys.version}'"
if errorlevel 1 (
  echo [ERRO] Python 3.12+ e obrigatorio.
  pause
  exit /b 1
)
%PY% --version

echo [2/6] Criando ambiente virtual...
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
)
call ".venv\Scripts\activate.bat"

echo [3/6] Atualizando pip e instalando dependencias...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERRO] Falha ao instalar dependencias.
  pause
  exit /b 1
)

echo [4/6] Criando diretorios...
if not exist "data\memory" mkdir "data\memory"
if not exist "data\speakers" mkdir "data\speakers"
if not exist "data\cache" mkdir "data\cache"
if not exist "logs" mkdir "logs"

echo [5/6] Gerando config inicial...
python -c "from app.config.settings import Settings; from app.config.paths import get_paths; p=get_paths(); p.ensure(); s=Settings.load(); s.save(); print('config:', p.config_file)"

echo [6/6] Verificando Ollama...
where ollama >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Ollama nao encontrado no PATH. Instale em https://ollama.com e reinicie o terminal.
) else (
  ollama list
)

echo.
echo Setup concluido. Execute start_herb.bat para iniciar.
pause
endlocal

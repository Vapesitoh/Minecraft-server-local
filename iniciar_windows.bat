@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] Creando entorno virtual...
  where py >nul 2>nul
  if errorlevel 1 (
    python -m venv .venv
  ) else (
    py -3 -m venv .venv
  )
  if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Instala Python 3.10 o superior y marca Add Python to PATH.
    pause
    exit /b 1
  )
)
echo [2/2] Instalando/verificando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: No se pudieron instalar las dependencias.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause

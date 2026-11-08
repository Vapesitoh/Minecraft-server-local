@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR instalando dependencias.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --windowed --collect-all qtawesome --name BlockServerGUI --add-data "assets;assets" --icon "assets\block_icon.ico" app.py
if errorlevel 1 (
  echo ERROR compilando EXE.
  pause
  exit /b 1
)
echo Archivo generado: dist\BlockServerGUI.exe
pause

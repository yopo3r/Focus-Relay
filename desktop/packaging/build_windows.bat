@echo off
rem Genera el instalador de Windows (Focus Relay-Setup.exe). Requisitos: Python 3.10+ e Inno Setup 6 (https://jrsoftware.org/isinfo.php)
cd /d "%~dp0.."
python -m pip install --upgrade pip pyinstaller -r requirements.txt || exit /b 1
pyinstaller --noconfirm focus_relay.spec || exit /b 1
where iscc >nul 2>nul && (iscc packaging\installer.iss) || echo Inno Setup no esta instalado: la app portable quedo en dist\FocusRelay\
echo Listo.

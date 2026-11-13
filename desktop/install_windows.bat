@echo off
rem Graphical installer for Focus Relay (source code). Needs Python 3.9+ ("Add python.exe to PATH" checked).
rem Instalador grafico de Focus Relay: abre un asistente con idioma, opciones y barra de progreso.
cd /d "%~dp0"
set "PYCMD="
where pythonw >nul 2>nul && python -c "import tkinter" >nul 2>nul && set "PYCMD=pythonw"
if not defined PYCMD where pyw >nul 2>nul && py -3 -c "import tkinter" >nul 2>nul && set "PYCMD=pyw -3"
if not defined PYCMD (
  powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $es=(Get-UICulture).TwoLetterISOLanguageName -eq 'es'; $m= if($es){'Focus Relay necesita Python 3.9 o superior (con tkinter). Se abrira la pagina de descarga: instalalo marcando \"Add python.exe to PATH\" y vuelve a ejecutar este instalador.'}else{'Focus Relay needs Python 3.9 or newer (with tkinter). The download page will open: install it with \"Add python.exe to PATH\" checked and run this installer again.'}; [System.Windows.Forms.MessageBox]::Show($m,'Focus Relay',0,48) | Out-Null; Start-Process 'https://www.python.org/downloads/'"
  exit /b 1
)
start "" %PYCMD% "%~dp0packaging\installer_gui.py"

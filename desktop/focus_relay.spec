# -*- mode: python ; coding: utf-8 -*-
# Empaqueta Focus Relay como programa independiente (no hace falta instalar Python ni dependencias).
#   cd desktop && pip install pyinstaller -r requirements.txt && pyinstaller focus_relay.spec
# Resultado: dist/FocusRelay/ (Windows: FocusRelay.exe · Linux: FocusRelay). Hay que compilar en cada sistema.
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

WIN = sys.platform.startswith("win")
datas = [("assets", "assets"), ("locales", "locales"), ("strings_web.json", "."), ("themes_data.json", ".")]
hidden = ["autostart.install_autostart", "PIL._tkinter_finder", "_miniaudio"]
if WIN:
    hidden += ["pystray._win32"]
    datas += collect_data_files("tzdata")
else:                                   # en Linux el ícono usa el backend xorg (no hace falta python3-gi en el equipo)
    hidden += ["pystray._xorg", "pystray._gtk", "pystray._appindicator"] + collect_submodules("Xlib") + ["six"]

a = Analysis(["main.py"], pathex=["."], datas=datas, hiddenimports=hidden,
             excludes=["pytest", "unittest.mock", "numpy", "scipy"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FocusRelay", console=False,
          icon="assets/icon.ico" if WIN else None)
coll = COLLECT(exe, a.binaries, a.datas, name="FocusRelay")

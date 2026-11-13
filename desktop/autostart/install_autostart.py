"""Instala Focus Relay Desktop para que arranque solo al iniciar sesión.

Windows -> coloca un lanzador .vbs (sin consola visible) en la carpeta
           de Inicio del usuario.
Linux   -> coloca un archivo .desktop en ~/.config/autostart/.

Ejecutar con el mismo Python/entorno donde ya instalaste
requirements.txt:

    python autostart/install_autostart.py

Para desinstalar el arranque automático, usa --remove.
"""
import os
import platform
import shutil
import sys

FROZEN = bool(getattr(sys, "frozen", False))          # empaquetada con PyInstaller (.exe / binario)
APP_DIR = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PY = os.path.join(APP_DIR, "main.py")


def _command(background=False, windows=False):
    """Línea de comando que arranca la app: el ejecutable empaquetado, o Python + main.py."""
    if FROZEN:
        parts = [sys.executable]
    else:
        py = _windows_python() if windows else sys.executable      # mismo Python/venv de las dependencias
        parts = [py, MAIN_PY]
    if background:
        parts.append("--background")
    return parts


def _windows_startup_dir():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("No se encontró la variable de entorno APPDATA.")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def _windows_python():
    # Prioriza pythonw.exe (sin consola). Si no existe, usa python.exe normal.
    candidate = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return candidate if os.path.exists(candidate) else sys.executable


def install_windows():
    startup_dir = _windows_startup_dir()
    os.makedirs(startup_dir, exist_ok=True)
    launcher_path = os.path.join(startup_dir, "focus_relay_desktop.vbs")
    cmd = " ".join('""' + p + '""' for p in _command(True, windows=True))
    content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'WshShell.Run "{cmd}", 0, False\n'
    ).format(cmd=cmd)
    # Windows Script Host lee los .vbs en la página de códigos ANSI, no en UTF-8: con rutas con tildes
    # (p. ej. C:\\Users\\Cáceres) UTF-8 las corrompe y el autoinicio falla en silencio.
    with open(launcher_path, "w", encoding="mbcs" if os.name == "nt" else "utf-8", errors="replace") as f:
        f.write(content)
    print("Instalado:", launcher_path)


def remove_windows():
    launcher_path = os.path.join(_windows_startup_dir(), "focus_relay_desktop.vbs")
    if os.path.exists(launcher_path):
        os.remove(launcher_path)
        print("Eliminado:", launcher_path)
    else:
        print("No había nada instalado.")


def _linux_autostart_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "autostart")


def install_linux():
    autostart_dir = _linux_autostart_dir()
    os.makedirs(autostart_dir, exist_ok=True)
    desktop_path = os.path.join(autostart_dir, "focus-relay-desktop.desktop")
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Focus Relay Desktop\n"
        "Exec={cmd}\n"
        "Icon=focus-relay\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Terminal=false\n"
    ).format(cmd=" ".join('"' + p + '"' for p in _command(True)))
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.chmod(desktop_path, 0o755)
    print("Instalado:", desktop_path)


def install_launcher_linux():
    """Entrada en el menú de aplicaciones (con ícono) y en ~/.local/share/icons."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    apps = os.path.join(base, "applications")
    icons = os.path.join(base, "icons", "hicolor", "256x256", "apps")
    os.makedirs(apps, exist_ok=True)
    os.makedirs(icons, exist_ok=True)
    icon_src = os.path.join(APP_DIR, "assets", "icon-256.png")
    icon_dst = os.path.join(icons, "focus-relay.png")
    if os.path.exists(icon_src):
        shutil.copyfile(icon_src, icon_dst)
    path = os.path.join(apps, "focus-relay.desktop")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "[Desktop Entry]\nType=Application\nName=Focus Relay\n"
            "Comment=Temporizador de estudio con ESP-01S\n"
            'Exec=' + " ".join('"' + p + '"' for p in _command()) + '\nIcon=focus-relay\nTerminal=false\n'
            "Categories=Utility;Education;\nStartupWMClass=focus-relay\n"
        )
    os.chmod(path, 0o755)
    print("Instalado en el menú de aplicaciones:", path)


def remove_linux():
    desktop_path = os.path.join(_linux_autostart_dir(), "focus-relay-desktop.desktop")
    if os.path.exists(desktop_path):
        os.remove(desktop_path)
        print("Eliminado:", desktop_path)
    else:
        print("No había nada instalado.")


def is_enabled():
    """True si la app ya está configurada para iniciar con el sistema."""
    try:
        if platform.system() == "Windows":
            return os.path.exists(os.path.join(_windows_startup_dir(), "focus_relay_desktop.vbs"))
        if platform.system() == "Linux":
            return os.path.exists(os.path.join(_linux_autostart_dir(), "focus-relay-desktop.desktop"))
    except Exception:
        pass
    return False


def set_enabled(on):
    """Activa o quita el inicio con el sistema (lo usa el interruptor de Ajustes). Devuelve True si quedó como se pidió."""
    try:
        system = platform.system()
        if system == "Windows":
            install_windows() if on else remove_windows()
        elif system == "Linux":
            if on:
                install_linux()
            else:
                remove_linux()
        else:
            return False
        return is_enabled() == bool(on)
    except Exception:
        return False


def main():
    remove = "--remove" in sys.argv
    system = platform.system()
    if system == "Windows":
        remove_windows() if remove else install_windows()
    elif system == "Linux":
        if "--menu" in sys.argv:
            install_launcher_linux()
        else:
            remove_linux() if remove else install_linux()
    else:
        print(f"Sistema operativo no soportado por este instalador: {system}")
        sys.exit(1)


if __name__ == "__main__":
    main()

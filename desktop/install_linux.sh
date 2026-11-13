#!/usr/bin/env bash
# One-click installer (Linux Mint/Ubuntu/Debian) for the source code / Instalador de un clic para el código fuente.
# Installs what is needed, creates its own environment and adds "Focus Relay" to the application menu.
# Messages follow the system language (es, en, fr, pt, de, it, nl, ru, ja, ko, zh); force one with FR_LANG=fr ./install_linux.sh
set -e
cd "$(dirname "$0")"
# Idioma: FR_LANG, o el del sistema (LC_ALL / LC_MESSAGES / LANG); si no hay traducción, inglés.
LANG_CODE="${FR_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}}"; LANG_CODE="${LANG_CODE:0:2}"
say() {
  case "$LANG_CODE:$1" in
    es:SUDO) echo "Se pedirá tu contraseña para instalar paquetes del sistema (bandeja, notificaciones, ventanas)." ;;
    fr:SUDO) echo "Votre mot de passe sera demandé pour installer les paquets système (zone de notification, notifications, fenêtres)." ;;
    pt:SUDO) echo "Será pedida a sua senha para instalar pacotes do sistema (bandeja, notificações, janelas)." ;;
    de:SUDO) echo "Dein Passwort wird abgefragt, um Systempakete zu installieren (Tray, Benachrichtigungen, Fenster)." ;;
    it:SUDO) echo "Ti verrà chiesta la password per installare i pacchetti di sistema (area di notifica, notifiche, finestre)." ;;
    nl:SUDO) echo "Je wachtwoord wordt gevraagd om systeempakketten te installeren (systeemvak, meldingen, vensters)." ;;
    ru:SUDO) echo "Потребуется пароль для установки системных пакетов (трей, уведомления, окна)." ;;
    ja:SUDO) echo "システムパッケージ（トレイ、通知、ウィンドウ）をインストールするため、パスワードの入力が必要です。" ;;
    ko:SUDO) echo "시스템 패키지(트레이, 알림, 창)를 설치하려면 비밀번호가 필요합니다." ;;
    zh:SUDO) echo "安装系统组件（托盘、通知、窗口）需要输入您的密码。" ;;
    *:SUDO) echo "You will be asked for your password to install system packages (tray, notifications, windows)." ;;
    es:DEPS) echo "Instalando las dependencias de Python (puede tardar un minuto)…" ;;
    fr:DEPS) echo "Installation des dépendances Python (cela peut prendre une minute)…" ;;
    pt:DEPS) echo "Instalando as dependências do Python (pode levar um minuto)…" ;;
    de:DEPS) echo "Python-Abhängigkeiten werden installiert (das kann eine Minute dauern)…" ;;
    it:DEPS) echo "Installazione delle dipendenze Python (può richiedere un minuto)…" ;;
    nl:DEPS) echo "Python-afhankelijkheden worden geïnstalleerd (dit kan een minuut duren)…" ;;
    ru:DEPS) echo "Установка зависимостей Python (это может занять минуту)…" ;;
    ja:DEPS) echo "Python の依存パッケージをインストールしています（1分ほどかかります）…" ;;
    ko:DEPS) echo "Python 종속성을 설치하는 중입니다(1분 정도 걸릴 수 있습니다)…" ;;
    zh:DEPS) echo "正在安装 Python 依赖（可能需要一分钟）…" ;;
    *:DEPS) echo "Installing Python dependencies (this can take a minute)…" ;;
    es:DONE) echo "Listo: busca «Focus Relay» en el menú de aplicaciones." ;;
    fr:DONE) echo "Terminé : cherchez « Focus Relay » dans le menu des applications." ;;
    pt:DONE) echo "Pronto: procure «Focus Relay» no menu de aplicativos." ;;
    de:DONE) echo "Fertig: Suche „Focus Relay“ im Anwendungsmenü." ;;
    it:DONE) echo "Fatto: cerca «Focus Relay» nel menu delle applicazioni." ;;
    nl:DONE) echo "Klaar: zoek “Focus Relay” in het toepassingsmenu." ;;
    ru:DONE) echo "Готово: найдите «Focus Relay» в меню приложений." ;;
    ja:DONE) echo "完了：アプリケーションメニューで「Focus Relay」を探してください。" ;;
    ko:DONE) echo "완료: 응용 프로그램 메뉴에서 'Focus Relay'를 찾아보세요." ;;
    zh:DONE) echo "完成：请在应用程序菜单中查找“Focus Relay”。" ;;
    *:DONE) echo "Done: look for “Focus Relay” in the application menu." ;;
  esac
}

if command -v apt-get >/dev/null; then
  say SUDO
  sudo apt-get install -y python3 python3-venv python3-pip python3-tk python3-gi \
    gir1.2-ayatanaappindicator3-0.1 libnotify-bin
fi
[ -d .venv ] || python3 -m venv --system-site-packages .venv
say DEPS
.venv/bin/python -m pip install --upgrade pip -r requirements.txt
.venv/bin/python autostart/install_autostart.py --menu
echo
say DONE

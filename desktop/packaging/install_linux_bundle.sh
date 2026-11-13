#!/usr/bin/env bash
# Instala Focus Relay (programa empaquetado) para el usuario actual: copia a ~/.local/opt y crea el acceso del menú.
# Uso:  ./instalar.sh          (para quitar:  ./instalar.sh --quitar)
# Los mensajes siguen el idioma del sistema (es, en, fr, pt, de, it, nl, ru, ja, ko, zh); se puede forzar con FR_LANG=fr.
set -euo pipefail
# Idioma: FR_LANG, o el del sistema (LC_ALL / LC_MESSAGES / LANG); si no hay traducción, inglés.
LANG_CODE="${FR_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}}"; LANG_CODE="${LANG_CODE:0:2}"
say() {
  case "$LANG_CODE:$1" in
    es:REMOVED) echo "Focus Relay quitado (tus datos en ~/.config/FocusRelayDesktop se conservan)." ;;
    fr:REMOVED) echo "Focus Relay supprimé (vos données dans ~/.config/FocusRelayDesktop sont conservées)." ;;
    pt:REMOVED) echo "Focus Relay removido (seus dados em ~/.config/FocusRelayDesktop foram mantidos)." ;;
    de:REMOVED) echo "Focus Relay entfernt (deine Daten in ~/.config/FocusRelayDesktop bleiben erhalten)." ;;
    it:REMOVED) echo "Focus Relay rimosso (i tuoi dati in ~/.config/FocusRelayDesktop vengono conservati)." ;;
    nl:REMOVED) echo "Focus Relay verwijderd (je gegevens in ~/.config/FocusRelayDesktop blijven bewaard)." ;;
    ru:REMOVED) echo "Focus Relay удалён (ваши данные в ~/.config/FocusRelayDesktop сохранены)." ;;
    ja:REMOVED) echo "Focus Relay を削除しました（~/.config/FocusRelayDesktop のデータは残ります）。" ;;
    ko:REMOVED) echo "Focus Relay를 제거했습니다(~/.config/FocusRelayDesktop의 데이터는 유지됩니다)." ;;
    zh:REMOVED) echo "已卸载 Focus Relay（~/.config/FocusRelayDesktop 中的数据已保留）。" ;;
    *:REMOVED) echo "Focus Relay removed (your data in ~/.config/FocusRelayDesktop is kept)." ;;
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
    es:NOTIF) echo "Para ver notificaciones se recomienda tener libnotify-bin (en Mint/Ubuntu ya viene)." ;;
    fr:NOTIF) echo "Pour les notifications, libnotify-bin est recommandé (déjà inclus sur Mint/Ubuntu)." ;;
    pt:NOTIF) echo "Para ver notificações, recomenda-se o libnotify-bin (já vem no Mint/Ubuntu)." ;;
    de:NOTIF) echo "Für Benachrichtigungen wird libnotify-bin empfohlen (unter Mint/Ubuntu bereits enthalten)." ;;
    it:NOTIF) echo "Per le notifiche si consiglia libnotify-bin (già incluso in Mint/Ubuntu)." ;;
    nl:NOTIF) echo "Voor meldingen wordt libnotify-bin aanbevolen (zit al in Mint/Ubuntu)." ;;
    ru:NOTIF) echo "Для уведомлений рекомендуется libnotify-bin (в Mint/Ubuntu уже установлен)." ;;
    ja:NOTIF) echo "通知を表示するには libnotify-bin を推奨します（Mint/Ubuntu には標準で入っています）。" ;;
    ko:NOTIF) echo "알림을 보려면 libnotify-bin을 권장합니다(Mint/Ubuntu에는 기본 포함)." ;;
    zh:NOTIF) echo "建议安装 libnotify-bin 以显示通知（Mint/Ubuntu 已自带）。" ;;
    *:NOTIF) echo "For notifications, libnotify-bin is recommended (already included on Mint/Ubuntu)." ;;
  esac
}
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/opt/focus-relay"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
if [ "${1:-}" = "--quitar" ]; then
  rm -rf "$DEST" "$APPS/focus-relay.desktop" "$ICONS/focus-relay.png" "$HOME/.config/autostart/focus-relay-desktop.desktop"
  say REMOVED; exit 0
fi
mkdir -p "$DEST" "$APPS" "$ICONS"
cp -a "$SRC"/. "$DEST"/
cp "$SRC/focus-relay.png" "$ICONS/focus-relay.png"
cat > "$APPS/focus-relay.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Focus Relay
Comment=Temporizador de estudio
Exec="$DEST/FocusRelay"
Icon=focus-relay
Terminal=false
Categories=Utility;Education;
StartupWMClass=FocusRelay
DESK
chmod +x "$APPS/focus-relay.desktop" "$DEST/FocusRelay"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
say DONE
say NOTIF

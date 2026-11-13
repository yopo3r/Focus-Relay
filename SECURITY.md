# Seguridad y privacidad

- La app **no tiene telemetría ni cuentas**. Los datos viven en la carpeta de configuración del usuario.
- Conexiones de red: tu ESP-01S (HTTP en red local, sin cifrar), el calendario `https` que suscribas si activas la música, `ice5.somafm.com` y, solo si pulsas «Buscar actualizaciones», `api.github.com`.
- El enlace de un calendario suscrito se guarda en `config.json` (permisos 600 en Linux/macOS). Trátalo como una contraseña. Los respaldos no lo incluyen.
- El bloqueo de apps solo cierra procesos de tu lista y nunca la propia app ni procesos críticos del sistema.

## Reportar una vulnerabilidad
Abre un *Security advisory* privado en la pestaña **Security** del repositorio (o un issue sin detalles sensibles pidiendo contacto).

# Política de privacidad / Privacy policy — Focus Relay

**Versión de esta política:** 1.0 · **Fecha:** 2026-11-13 · **Aplica a:** Focus Relay 3.27.0 y la extensión 4.1.0

## En breve
Focus Relay **no recoge, envía ni almacena tus datos fuera de tu equipo**. No tiene cuentas, telemetría, analítica, publicidad ni rastreadores. El autor no recibe ningún dato tuyo y no opera ningún servidor para la app.

## Qué se guarda (solo en tu equipo)
En la carpeta de datos de la app (`%APPDATA%\FocusRelayDesktop` en Windows, `~/.config/FocusRelayDesktop` en Linux; permisos restringidos al usuario en Linux/macOS): ajustes y nombre (opcional), actividades y frases, historial de sesiones, tareas, piezas de recompensa, copia del calendario que importes y eventos manuales. La extensión guarda solo su estado y el puerto de la app en el almacenamiento del navegador.

## Conexiones de red (todas iniciadas por ti o necesarias para la función que activas)
| Destino | Cuándo | Qué ve el tercero |
|---|---|---|
| Tu ESP-01S (red local, HTTP sin cifrar) | Si usas el dispositivo | Hora, duraciones, estado y registro de sesiones (solo en tu red) |
| `ice5.somafm.com` | Si activas la música de radio | Tu dirección IP |
| Enlace de calendario que suscribas (https) | Si lo configuras | Tu IP, ante quien aloje el enlace |
| `api.github.com` | Solo si pulsas «Buscar actualizaciones» | Tu IP; no se envía ningún dato tuyo |
| `127.0.0.1:8765` (puente local) | Siempre, solo dentro de tu equipo | Nada sale del equipo |

Esos terceros tratan tus datos según sus propias políticas; el autor no tiene acceso.

## Bloqueo de apps y sitios
La app lee los nombres de procesos en ejecución para cerrar los de tu lista; la extensión consulta el dominio de la pestaña para bloquear los de tu lista. Se usa en el momento, localmente; no se guarda ni se envía.

## Tus derechos y cómo ejercerlos (acceso, rectificación, supresión, oposición, portabilidad, bloqueo)
Como todo queda en tu equipo, los ejerces tú directamente:
- **Acceso y portabilidad:** Ajustes → Datos → exportar respaldo (.zip) y exportar CSV; o abre la carpeta de datos.
- **Rectificación:** edita ajustes, tareas, actividades y eventos en la app.
- **Supresión:** borra el historial desde la pestaña Historial, o **Ajustes → Acerca de → «Borrar todos mis datos…»**.
- **Oposición / bloqueo:** desactiva la música, quita el enlace del calendario, usa el modo «Solo en la app» o no actives el bloqueo.

## Seguridad
Datos en archivos locales con permisos restringidos (Linux/macOS), escritura atómica, puente local solo en 127.0.0.1 con validación de `Host` y sin CORS. El enlace de calendario nunca va en respaldos ni en registros. Limitación conocida: la comunicación con el ESP-01S es HTTP sin cifrar dentro de tu red local.

## Menores
La app no recoge datos de nadie, incluidos menores. Si un menor la usa, sus datos siguen solo en su equipo.

## Soporte y reportes públicos
Los *issues* de GitHub son públicos: no pegues datos personales, rutas con tu nombre, enlaces de calendario ni el contenido de `hang.log` sin revisarlo.

## Cambios
Esta política se actualizará en el repositorio y quedará reflejada en «Acerca de → Privacidad». Contacto: abre un issue en https://github.com/yopo3r/Focus-Relay (sin datos sensibles).

---
*English summary:* Focus Relay collects nothing and sends nothing to the author. All data stays on your device. Optional network calls (radio stream, calendar link, update check, your own ESP-01S) are listed above. You can export (Settings → Data), edit, or erase everything (Settings → About → "Delete all my data…").

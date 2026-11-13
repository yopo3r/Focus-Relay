# Focus Relay · extensión del navegador

Extensión mínima: **bloquea sitios distractores mientras la app Focus Relay tiene una sesión activa**. Todo lo demás
(lista de sitios, pausas, modo estricto, música, trofeos, temas) vive en la app de escritorio, que es la central de control.

## Instalar
1. Abre la app de escritorio (ver `../desktop/README.md`).
2. En Chrome o Edge: Extensiones → activa *Modo desarrollador* → *Cargar descomprimida* → elige esta carpeta.

## Cómo funciona
- Cada ~6 s la extensión le pregunta a la app (`127.0.0.1:8765/estado`, solo este equipo) si hay que bloquear y qué sitios.
  Si la app está cerrada o no hay sesión de trabajo, no se bloquea nada.
- Popup: estado, reloj y un botón **«Bloquear {sitio}»** que agrega el sitio de la pestaña actual a la lista de la app
  (solo agrega; quitar sitios se hace en la app y no se puede durante una sesión).
- Página de bloqueo: reloj y tarea en curso; al terminar la sesión vuelve sola al sitio.
- El ícono muestra un punto (●) mientras el bloqueo está activo.
- **Opciones**: solo el puerto de la app (por defecto 8765; debe coincidir con *Ajustes → Avanzado* en la app).

## Actualizar desde versiones anteriores
La primera vez que la extensión encuentra la app, le pasa la lista de sitios y excepciones que tenía guardada y limpia
el resto de sus datos antiguos (colección, música, temas, IP del ESP). El ESP-01S se configura ahora solo desde la app.

## Permisos
`declarativeNetRequest` y acceso a http(s) (para redirigir los sitios bloqueados), `storage`, `alarms` y `activeTab`
(leer el sitio de la pestaña solo cuando abres el popup). No envía nada a internet: solo habla con la app en este equipo.


## Novedades 4.1.0

- Idioma (11 idiomas) y tema (claro, oscuro o automático según el navegador) en Opciones.
- Pestañas **Cómo funciona** y **Acerca de** en Opciones.

## Firefox
Misma extensión, empaquetada con `manifest.firefox.json` (Manifest V3, Firefox 140 o superior).

- Generar los paquetes: `python tools/build_extension.py` → `dist/focus-relay-firefox-<versión>.zip` y `dist/focus-relay-chrome-<versión>.zip`.
- Probarla sin firmar: `about:debugging#/runtime/this-firefox` → «Cargar complemento temporal…» → elegir el `manifest.json` de una carpeta con el contenido del zip de Firefox (se descarga al cerrar el navegador). Para uso permanente hay que publicarla o firmarla en addons.mozilla.org.
- Firefox no concede al instalar el acceso a los sitios web: el popup y las Opciones muestran un botón «Dar permiso» (o actívalo en `about:addons` → Focus Relay → Permisos). Sin él no se puede bloquear.
- Si cambias el código, mantén iguales las versiones de `manifest.json` y `manifest.firefox.json` (el script lo comprueba).

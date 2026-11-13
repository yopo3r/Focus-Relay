# Changelog

## 3.27.0 — extensión 4.1.0

- **The mascot can say goodbye when the app closes** (Settings → Mascot, "Say goodbye when the app closes"; on by default). It waves with its happy face and, if its text is on, says a farewell (sometimes with your name), and the app closes about 2.4 s later. Translated into all 11 languages.

## 3.26.1 — extensión 4.1.0

- **Optional simple confirmation when quitting the app during a session** (Settings → Behavior, "Ask for confirmation when quitting the app during a session"; on by default). Applies when strict mode is off and a session is running (strict mode keeps its code); the mascot shows its wary face while you decide. Translated into all 11 languages.

## 3.26.0 — extensión 4.1.0

- **Fix: the mascot now shows its wary face when you try to quit the app mid-session** from the tray icon (strict mode's quit code dialog); before, only the early-stop dialogs triggered it.
- **New option "Codes are case-sensitive (mixed upper and lower case)"** (Settings → Behavior, strict mode). Random codes (turn off strict mode, finish early, quit the app) then mix upper- and lower-case letters, always at least one of each, using only letters whose two forms look clearly different (no K/k, S/s, V/v…), and must be typed with the exact case. Off by default; can't be changed while a session is running. Translated into all 11 languages.

## 3.25.1 — extensión 4.1.0

- **Fix: the first speech bubble flashed in the opposite corner for an instant.** The initial greeting is requested before the mascot's position is known, and the bubble window was mapped before the window system had received its geometry, so on first show it appeared at (0, 0) and then jumped. The geometry is now flushed (`update_idletasks`) before the bubble is shown; the position self-check also waits 1.5 s after a bubble appears.

## 3.25.0 — extensión 4.1.0

- **Fix (Linux Mint): mascot and its text vanished after the PC suspended and resumed.** After waking, the screen can briefly report a wrong size, which left the mascot at a clamped, off-place position until it was hidden/shown from Settings. Now the position is always recomputed from the saved one when the screen size changes (transient tiny screens are ignored), windows are rebuilt a few seconds after resume, and suspension is also detected through the monotonic clock (which doesn't count sleep), session unlock, screen changes, a stalled animation loop and (Windows) windows the OS reports as not visible. Each rebuild prints a `[Focus Relay] mascota: se recrean las ventanas (motivo)` line.
- **Privacy / data-protection (Chile, Ley 21.719):** new **Settings → About → "Delete all my data…"** (right of erasure; removes settings, history, tasks, rewards, calendar, caches and `hang.log`, then closes the app); data folder now `0700` on Linux/macOS; new `PRIVACY.md` (versioned policy with rights and network connections) and `docs/CUMPLIMIENTO-DATOS-CL.md` (technical compliance review); `SECURITY.md` corrected (calendar sync is independent of music); privacy warning in the bug-report template.

## 3.24.1 — extensión 4.1.0

- **Fix: weekday circles looked pixelated** (streak days in Settings and the automatic-task day chips). Tk doesn't anti-alias its ovals, so they're now drawn smoothly with Pillow (4x supersampled), falling back to the plain oval if Pillow isn't available.

## 3.24.0 — extensión 4.1.0

- **Configurable streak days** (Settings → General → "Streak days"). Pick the weekdays you work; unmarked days neither add to nor break your streak (and still count if you study on them). E.g. weekdays only: a weekend without the app keeps the streak. Applies everywhere the streak is used (panel, achievements, share images, mascot growth, best streak). Default: all 7 days, so nothing changes unless you opt in. Translated into all 11 languages.

## 3.23.3 — extensión 4.1.0

- **Windows touchscreen / trackpad scrolling.** Tk on Windows does not always receive wheel events from touch or precision touchpads, so scrollable areas (settings, calendar list…) now also scroll by dragging a finger/pointer over them (8 px threshold so clicks are unaffected; inputs, sliders and scrollbars are excluded), by `<TouchpadScroll>` where Tk supports it, and with PageUp/PageDown.

## 3.23.2 — extensión 4.1.0

- **Fix: four arms when poking the mascot while it studies.** In focus mood the hands already hold the book, so the extra raised arm is no longer drawn.
- **Fix: mascot text missing after the PC wakes from sleep.** If the internal clock jumps (suspend/resume) the mascot windows are recreated; the bubble is also remapped when it is shown.
- **Speech bubble hardening** (it still vanished occasionally): on every tick the bubble's mapped state and position are verified; if the system hid or moved it, it is restored, with `-topmost` re-asserted. Self-repairs print a `[Focus Relay] mascota: ...` line to the console (`FOCUS_RELAY_DEBUG=1` prints more), to help find the cause.
- **Fix (Windows): stray border around the logo in the title header** — removed the extra outline drawn over the icon.
- **Fix (Windows): trackpad scrolling.** Precision touchpads send small wheel deltas that were rounded to zero, and the wheel binding was lost when the pointer moved over child widgets. Deltas are now accumulated and the wheel works anywhere over the scrollable area (also in the calendar list).

## 3.23.1 — extensión 4.1.0

- **Fix: the mascot vanished after changing theme or language** (`bad window path name ".!toplevel"`). Rebuilding the Panel closes every top-level window, including the mascot's; it now notices that its window is gone and recreates it on the next tick (with the new theme colours, without greeting again).

## 3.23.0 — extensión 4.1.0

- **Mascot greets you when the app opens** (once per launch): a morning / afternoon / evening greeting, and sometimes one with your name ("Your name" setting), with a happy face and a waving hand. Translated into all 11 languages.

## 3.22.2 — extensión 4.1.0

- **Freeze watchdog**: if the window stops responding for 8 s, the app writes the stack of every thread to `hang.log` in the data folder (Settings → About → Open folder). If it ever freezes again, that file shows exactly where it got stuck.
- Offline banner (radio cannot play): its text is only updated when it changes and it no longer re-wraps itself on every resize event — the likeliest suspect for a layout loop that froze the window, the mascot and the tray menu while a session was running.

## 3.22.1 — extensión 4.1.0

- **Fix: the app could freeze offline** (connected to a network with no internet, e.g. a session running while changing the music). The connectivity check resolved a host name via DNS — which can hang for tens of seconds — and ran inside the background poll loop. Now:
  - `has_internet()` probes public IPs in parallel without DNS and returns within ~1.5 s;
  - the periodic online check runs in the music thread, never in the poll loop (blocking enforcement, trophies, tray);
  - connecting to a radio has a hard 8 s deadline (urllib's timeout does not cover DNS);
  - if the connection drops right while connecting, the Panel shows the offline banner.

## 3.22.0 — extensión 4.1.0

- **Mascot invites you to start a session**: when idle, Brote sometimes suggests starting one and shows an eager face (big shiny eyes, open smile, waving hand, sparkles).
- **Mascot growth is easier to see**: the leaves and flower now appear after 2, 4 and 7 days in a row with focus (before 3, 7, 14), and the Mascot settings show your current streak and the stages.
- **Focus-mode book redesigned again**: the book is held in front of the face showing its back cover (spine, title label, page edge) and the side arms are hidden, so Brote has just two hands.
- **Settings → General**: the secondary behaviour options (confetti, low-power mode, adaptation, minimise) moved into a collapsible **More options** section.
- **GitHub repository** (https://github.com/yopo3r/Focus-Relay): new card in About with *Open on GitHub*, *Check for updates* (on demand only; compares with the latest release), *Report a bug* and *Suggest an improvement*. README, CONTRIBUTING, SECURITY, the extension manifests and the issue templates now point to it; privacy statement updated (11 languages).

## 3.21.2 — extensión 4.1.0

- Mascot: the focus-mode book is now an open book held with both hands (two tilted pages with lines of text, spine, cover edge and a red bookmark ribbon).

## 3.21.1 — extensión 4.1.0

- **Mascot no longer disappears by itself**: a watchdog re-shows the window if the system hides it, and on Windows it re-asserts "always on top" every few seconds (full-screen video or other top-most windows could push it behind).
- **Click always shows a message**: the bubble window is re-shown if it was hidden by the system or never mapped (e.g. the very first message), and the click-vs-drag threshold is more tolerant (8 px) so a slightly shaky click is not taken as a drag.
- New setting: **text size** of the mascot's speech bubble (8–22 pt).

## 3.21.0 — extensión 4.1.0

- **Performance on slow computers**:
  - The mascot animates at ~5 fps at rest (fast only for party/poke) and spaces its frames further apart if drawing is slow on that machine.
  - The process scan of the blocker no longer asks Windows for every process's executable path (the slowest part) and runs only at its own interval; with the Panel open it is no longer forced to run twice a second.
  - In app mode the background poll runs once a second while the Panel is open (the Panel already reads the clock directly).
  - `load_config()` is cached by file modification time (it is called many times per second).
  - The clock ring is rendered at 3× instead of 4× and in 0.5° steps.
- New **Low-power mode** (Settings → General): fewer mascot frames and less frequent checks.

## 3.20.0 — extensión 4.1.0

- **Settings → General is lighter**: the mascot options moved to a new **Mascot & messages** section, together with Phrases and Your name. General keeps start-up, mode, behaviour and labels.
- **Double-click (double-tap) the mascot to open the Panel.**

## 3.19.0 — extensión 4.1.0

- **Mascot bubble in its own window**: the mascot window now has a fixed size and the speech bubble is a separate window above it (below if there is no room), so nothing resizes when the text appears or disappears — this removes the flash of text on Linux.
- **Graphical Windows installer** (`install_windows.bat` → `packaging/installer_gui.py`): a wizard with language picker (11 languages), options (desktop shortcut, start with the system, open Tasks at startup, open when finished), progress bar and log; shows a message box if Python is missing.
- **Linux installers in 11 languages** (`install_linux.sh`, `packaging/install_linux_bundle.sh`): messages follow the system language, or `FR_LANG=fr`.
- The compiled Windows installer (Inno Setup) now offers 9 languages.

## 3.18.0 — extensión 4.1.0

- **Mascot is wary**: while you go through the early-stop confirmations Brote gives you a side-eye (half-closed eyes, flat mouth, a drop of sweat) and says something doubtful.
- **Open Tasks at startup** (opt-in, Settings → Startup): when the app starts with the system it opens the Panel on the Tasks page so you can plan the day first.
- Mascot: selectable body colour (7 palettes, `mascot_color`, swatches in Settings); hiding the bubble now clears it before resizing the window to avoid a one-frame ghost.
- Mascot: fixed the constant flicker after the bubble expired (re-packing the hidden bubble toggled the window height every frame) and a leaked window when a Tk error occurred during animation.
- Mascot: the speech bubble now stays visible longer (scaled to the message length) and can be turned off in Settings (`mascot_text`).
- Mascot: fixed it appearing in two places at once on Linux (first placement used a not-yet-set size; geometry is now applied once, complete `WxH+X+Y`, only when it changes).

## 3.17.0 — extensión 4.1.0

- **Aviso de bloqueo en ventana**: al bloquear una app aparece una ventanita (abajo a la derecha, se cierra sola) en vez de una notificación; avisa tanto del cierre próximo (modo aviso) como de que ya se cerró.
- **Bloqueo durante el Cronómetro**: nueva opción en Bloqueo («Bloquear también durante el Cronómetro»). Con ella activa, la lista de apps y sitios queda bloqueada para editar mientras corre el cronómetro.
- **Cerrar la app en modo estricto**: con una sesión en marcha (también Cronómetro) y modo estricto activo, «Salir» y cerrar la app piden escribir un código largo.
- **«Para ti» en vivo**: Ayuda se actualiza al terminar sesiones o cambiar la meta, sin reiniciar la app.
- **Puerto protegido en sesión**: durante una sesión no se puede cambiar el puerto ni apagar la conexión con la extensión, ni en la app (Avanzado) ni en las Opciones de la extensión (que también usa el último estado conocido si la app no responde; además, el servicio de fondo restituye el puerto si se cambia en plena sesión desde una página de opciones que ya estaba abierta).
- **Premios**: un Temporizador o una fase de trabajo del Pomodoro solo dan pieza si duran 5 min o más (también con dispositivo).
- **Panel**: selector de etiqueta o tarea para las próximas sesiones, bajo el reloj.
- **Bandeja dinámica y traducida**: «Pausar bloqueo» solo aparece con el bloqueo actuando; «Iniciar sesión» solo sin sesión; el menú se actualiza con el estado.
- **Modo estricto**: opción de pedir además un código aleatorio al terminar antes de tiempo (no editable durante sesiones).
- **Auditoría de calidad**: archivos renombrados al inglés (`help_gui`, `achievements_gui`, `install_*`, carpeta del firmware, imágenes); el Pomodoro ya no «recupera» fases ficticias tras suspender el equipo; racha y resumen semanal ignoran descansos; CSV protegido contra inyección de fórmulas; restaurar respaldos bloqueado en sesión y con lectura acotada; escritura de config con candado; tareas con campos faltantes no rompen; sitios con acentos (IDN → punycode) en app y extensión; la extensión serializa sus consultas (evita colisión de reglas) y consulta al abrir/cambiar pestaña (Chrome limita las alarmas a 30 s); puente con tiempo de espera por conexión.
- Documentación para GitHub: README en inglés y español, CONTRIBUTING, plantillas de issue y PR, README del firmware, CI con comprobaciones de la extensión.
- **Extensión para Firefox** (MV3, Firefox 140+): `extension/manifest.firefox.json` y `tools/build_extension.py` generan los paquetes de Chrome y Firefox; botón «Dar permiso» cuando Firefox no concede el acceso a los sitios.
- **Mascota «Brote»** (opcional): una criatura con un retoño que flota sobre tus demás ventanas, **sin bordes, arrastrable a cualquier lugar de la pantalla, redimensionable** (rueda del mouse, clic derecho o Ajustes › Comportamiento) y con opción de **mantenerse siempre al frente**, también cuando abres el navegador. Anima en reposo, enfoque y descanso, celebra al terminar sesiones, duerme de madrugada y crece con tu racha (brote → hojas → flor). Mensajes en 11 idiomas con tus frases personalizadas; clic para saludarla. Se muestra u oculta también desde la bandeja. En Windows y macOS el fondo es transparente; en Linux es un recuadro del color de la app, y en Wayland puro algunos escritorios ignoran «siempre al frente».
- **Historial unificado**: al cambiar entre «solo app» y «con dispositivo» ya no se pierden sesiones. El historial muestra juntas las sesiones de la app y las del dispositivo (ordenadas por fecha); las del dispositivo se guardan en una caché local al conectarse y siguen visibles sin conexión. Etiquetar va a la fuente correcta, «Borrar historial» limpia todo y los logros cuentan ambas.
- **Mascota más robusta (Windows y Linux)**: dibujo sin parpadeo (doble búfer), la ventana ya no aparece en la esquina (0, 0) antes de colocarse, un fallo al crearla no deja ventanas vacías ni reintenta cada segundo, un error de dibujo no la congela, y en Linux se vuelve a subir cada segundo porque X11 tapa las ventanas sin bordes.
- «Tu nombre» pasó a la columna derecha de Ajustes › General, bajo las frases motivacionales.
- «Datos» ahora está dentro de Ajustes › Avanzado.
- Panel: los trofeos usan texto de respaldo si el emoji no se puede dibujar; `--diagnose` informa del estado del emoji.
- Ventana propia para configurar los sitios bloqueados (como la de apps), bloqueada durante sesiones.
- Extensión 4.1.0: idioma, tema (claro/oscuro/automático según el navegador) y pestañas «Cómo funciona» y «Acerca de».

## 3.16.0 · extensión 4.0.0
- **La app es la central de control; la extensión queda mínima (4.0.0)**: solo bloquea sitios cuando la app lo indica. Se quitaron de la extensión la música, los trofeos, los temas, las notificaciones, el ESP directo y las opciones de bloqueo; la app envía qué bloquear, y las pausas y el modo estricto siguen siendo los de la app.
- Novedades de la extensión: botón **«Bloquear este sitio»** en el popup (solo agrega), página de bloqueo con la tarea en curso que vuelve sola al sitio al terminar, punto ● en el ícono mientras bloquea e importación única de la lista antigua. Nuevo ícono: el de la app.
- **Sitios web** en *Ajustes → Bloqueo* (lista y excepciones); la sincronización de trofeos con la extensión se retiró al no haber colección en el navegador.
- **El bloqueo de apps y de sitios no se puede modificar durante una sesión** (Temporizador o Pomodoro en marcha, incluido el descanso).
- **Bandeja**: «● Sesión activa · modo» en el menú y el tooltip, ícono con el color del modo en marcha y opción «Detener música».
- Logo de la app en el encabezado de las ventanas.
- **Aviso visual de música sin internet**: banner en el Panel cuando la radio elegida no puede sonar, con «Usar ruido marrón» y «Reintentar»; vuelve sola al reconectar.

## 3.15.0
- **La extensión (3.6.0) distingue la fuente**: el popup, las opciones y los avisos dicen «Conectado a la app de escritorio» o «al dispositivo físico» según corresponda (ya no afirma siempre que es el reloj físico). Con la app como fuente no muestra el aviso de «detenida desde los botones del dispositivo».
- **Trofeos sincronizados** entre la app y la extensión: las piezas se unen en ambos sentidos (`GET/POST /trofeos` del puente local, sin repetir ids; cada ~30 s). Con la app como fuente las piezas llegan por esta vía, así no se duplican. El POST exige una cabecera propia y valida cada pieza.

## 3.14.0
- **Puerto del puente configurable** (por defecto 8765): en la app, *Ajustes → Avanzado* (se aplica al instante; si el puerto está ocupado conserva el anterior); en la extensión (3.5.0), *Opciones → Avanzado*. Ambos deben coincidir.
- **Inicio automático** con el sistema: ahora tiene su propia tarjeta «Inicio» arriba en *Ajustes → General*.
- El interruptor del puente con la extensión se movió a *Avanzado*.

## 3.13.0
- **Sincronización con la extensión del navegador**: la app sirve su estado en `127.0.0.1:8765/estado` (solo lectura, solo desde este equipo, sin CORS y validando el Host). Si la extensión no encuentra el ESP-01S, consulta la app: al iniciar una sesión en la app se activan el bloqueo de sitios y la música del navegador. Extensión 3.4.0.
- Interruptor «Permitir que la extensión del navegador siga esta app» en Ajustes (activado por defecto).

## 3.12.0
- **Instalación como aplicación normal**: programa independiente para Windows (instalador `.exe`) y Linux (`.tar.gz` + `instalar.sh`) sin instalar Python ni dependencias; se compilan con PyInstaller (`desktop/focus_relay.spec`, `desktop/packaging/`) y con el workflow `Release` de GitHub.
- Instaladores de un clic desde el código fuente: `Instalar_Windows.bat` e `instalar_linux.sh` (instalan dependencias, crean el acceso con ícono).
- Interruptor **«Iniciar Focus Relay con el sistema»** en Ajustes; el inicio automático funciona también en el programa empaquetado.
- En el binario de Linux, los programas del sistema (notify-send, xdg-open) se lanzan con el entorno original.

## 3.11.1
- El diagnóstico (`--diagnose`) ahora comprueba `pystray` (sin él no hay ícono) e indica cómo instalarlo; pistas específicas para XFCE.

## 3.11.0
- **Adaptación a tu uso** (local, con reglas simples y explicables; no cambia nada hasta tener 10 sesiones de enfoque):
  duración sugerida según lo que sueles completar, mejores horas para las sesiones sugeridas del calendario,
  ajuste de la meta diaria (bajarla, subirla o crearla), duración típica por tarea al iniciarla desde Tareas,
  aviso si te saltas los descansos y aviso de cansancio cuando hoy ya pasaste tu punto habitual.
- Nueva tarjeta **«Para ti»** en Ayuda con lo aprendido y consejos personalizados (cada uno dice las cifras en que se basa),
  con botón para aplicar la meta sugerida.
- Interruptor «Adaptar sugerencias a mi uso» en Ajustes (activado por defecto).

## Desktop 3.10.3
- **Tema Turquesa claro:** el encabezado usa un degradado verde azulado más profundo con letras blancas (contraste mínimo 4,8:1).

## Desktop 3.10.2
- **Minimizar al iniciar cualquier sesión (opcional):** nueva casilla en Ajustes › General, desactivada por defecto e independiente de la de tareas. Al pulsar Iniciar o +5 min la app se minimiza y llega una notificación con el modo y la duración (p. ej. «Sesión iniciada: Temporizador · 25 min»). Si la sesión no llega a arrancar, no se minimiza.

## Desktop 3.10.1
- **Nombre de cada premio al pasar el mouse:** las piezas de colección (en el Panel y en la pestaña de Premios) muestran su nombre —Zorro, Cohete, Guitarra…— en un globito. Los 30 nombres están traducidos a los 11 idiomas.

## Desktop 3.10.0
- **Reloj del Panel sin pixelado:** el anillo se dibuja con Pillow a 4× de resolución y se reduce (bordes suaves); sin Pillow vuelve al dibujo anterior.
- **Modo estricto más firme:** con un Temporizador o Pomodoro en marcha (incluido el descanso) no se puede cambiar el número de confirmaciones ni desactivar el modo (los controles se deshabilitan). Para desactivarlo fuera de una sesión hay que escribir un código aleatorio distinto cada vez (p. ej. `K7QM-4TXD`; no se puede pegar, Enter acepta y Esc cancela).
- **Minimizar al iniciar una tarea:** nueva opción en Ajustes › General (desactivada por defecto). Al pulsar ▶ en una tarea la app se minimiza y llega una notificación con la tarea y su duración.
- **Enter y Esc en los tiempos:** en los campos de duración de Ajustes, Enter aplica el cambio y Esc lo cancela (vuelve al valor guardado); el editor del reloj del Panel también recibe el foco de forma más fiable.
- **Tema Rosa claro:** el encabezado usa un degradado frambuesa con letras blancas (contraste mínimo 4,6:1).

## Desktop 3.9.3
- **Notificaciones en Linux:** `pystray` no sabe mostrar notificaciones en Linux (solo en Windows y macOS), por eso no aparecía ninguna. Ahora se usa el servicio de notificaciones del escritorio (`notify-send` o, si falta, `gdbus`), que en Linux Mint ya vienen instalados. El ícono de la bandeja queda como último recurso.
- **Ícono de bandeja:** si el escritorio no tiene el soporte AppIndicator activo (applet «System Tray» / «XApp Status Applet» desactivado), se salta ese método y se prueba el siguiente en vez de dejar un ícono invisible.
- **Diagnóstico:** `python3 main.py --diagnose` muestra qué falta (paquetes, servicio de notificaciones, soporte de bandeja), envía una notificación de prueba y sugiere el comando de instalación.
- Un fallo al mostrar un aviso ya no puede detener el hilo que controla el bloqueo.

## Desktop 3.9.2
- **Estadísticas más tranquilas:** la vista por defecto muestra solo lo esencial: período, 3 cifras (tiempo enfocado, sesiones y días activos), el gráfico y una línea con la racha y los logros. Las otras 5 cifras (completadas, promedio, sesión más larga, mejor día y tareas) y el desglose por modo y etiqueta quedan tras «Más detalles». La cuadrícula de logros salió de esta pestaña (sigue completa en Logros, a un clic).

## Desktop 3.9.1
- **El trofeo junto al confeti:** al terminar una sesión, la tarjeta de felicitación muestra la pieza ganada (en su mosaico de color) y los logros que esa sesión desbloqueó. Si la pieza tarda un instante en calcularse, el confeti la espera hasta 2 s; si no hubo trofeo, sale la tarjeta de siempre.

## Desktop 3.9.0
- **Tema «Rosa»:** paleta rosada suave con apariencia clara y oscura (también disponible en la extensión). Se elige en Ajustes › Apariencia.
- **Modo estricto:** en Ajustes › General se activa y se elige de 1 a 100 confirmaciones. Con la sesión en marcha, terminarla antes de tiempo (o cambiar de modo) pide confirmar esa cantidad de veces seguidas; cerrar o cancelar en cualquier paso mantiene la sesión. Sustituye al aviso simple, no ofrece «no volver a preguntar» y aflojarlo durante una sesión exige las mismas confirmaciones. Protege el Temporizador y el trabajo del Pomodoro (no los descansos ni el cronómetro).
- **Interfaz más minimalista:** los textos explicativos de Ajustes, Música, Premios, Historial y Tareas automáticas pasaron al botón «i» de cada tarjeta (plegados por defecto); se quitó el párrafo introductorio de Ajustes y la pestaña Ayuda muestra solo los títulos hasta que los tocas.

## Desktop 3.8.0
- **Sonido suave de aviso:** al terminar un Temporizador, un bloque de trabajo o un descanso del Pomodoro suena una campanilla breve y agradable (sintetizada en tu computador, sin archivos de audio). Cada situación tiene su melodía: arpegio ascendente al terminar, notas que bajan al empezar el descanso y dos notas luminosas al volver a trabajar. Se activa, se ajusta su volumen y se prueba en Ajustes › Música; funciona también con el dispositivo ESP-01S.
- **Imágenes para compartir:** ya no se puede editar el texto; cada imagen usa una frase al azar de una lista predefinida (ahora 10 frases por idioma).
- **Nueva pestaña «Ayuda»:** 7 ideas para sacarle el máximo provecho a la app y 8 consejos para estudiar y trabajar, en los 11 idiomas.

## Desktop 3.7.0
- **Reloj más exacto (modo «Solo en la app»):** el número se redibuja justo al cambiar cada segundo en vez de cada 250 ms, así que ya no se «queda» unas milésimas de más y luego se adelanta. Con dispositivo, el ESP-01S se consulta por red y puede haber ~0,3 s de variación inherente.
- **El descanso del Pomodoro se edita en el propio reloj** (chip «☕ Descanso N min ✎» bajo el anillo), igual que el tiempo de trabajo.
- **Trofeos reparados:** en modo app las piezas se calculan desde el historial (una por sesión terminada: Temporizador, fase de trabajo del Pomodoro o cronómetro de 15 min o más), sin pérdidas ni duplicados. Aviso en pantalla al ganar una pieza o desbloquear un logro.
- **Pestaña Logros rediseñada:** resumen y cuatro secciones limpias —Rachas, Tiempo de enfoque, Tareas completadas y Largo de sesiones— con líneas de metas. Toca una meta alcanzada para compartirla. La colección de piezas queda debajo.
- Los trofeos aparecen en el Panel (últimas piezas y próximo logro). La configuración de música pasó a Ajustes › Música.

## Desktop 3.6.0
- **6 idiomas nuevos:** alemán, italiano, neerlandés, ruso, japonés y coreano (ahora 11 en total). Los textos nuevos viven en `desktop/locales/<código>.json`; si falta una clave se muestra en inglés. La pantalla OLED del dispositivo solo tiene fuentes para es/en/fr/pt/zh y en los demás idiomas muestra inglés.
- Fechas y meses por idioma (genitivo en ruso, formato año-mes-día en ja/ko/zh), fuentes específicas de japonés y coreano en las imágenes para compartir.
- El selector de idioma es ahora una lista desplegable. El OLED del ESP-01S solo tiene fuentes de es/en/fr/pt/zh: con los idiomas nuevos muestra inglés.
- Prueba automática que exige que cada idioma tenga todas las claves y los mismos `{marcadores}`.

## Desktop 3.5.1
- **Seguridad:** las direcciones del ESP-01S solo aceptan `http`/`https` (se rechazan `file://` y otros esquemas).
- **Bloqueo de apps:** nunca cierra la propia app, sus procesos padre ni procesos críticos del sistema aunque se agreguen a la lista.
- **Una sola instancia:** una segunda copia avisa y se cierra (antes dos copias escribían los mismos archivos).
- **Datos:** `config.json`/`data.json` con tipos equivocados (editados a mano o dañados) se corrigen al cargar en vez de romper la app.
- **Autoinicio:** en Linux usa el mismo Python/venv de la instalación; en Windows ya no corrompe rutas con tildes.
- Importar un `.ics` es atómico; limpieza de código muerto y de avisos de análisis estático.
- Avisos legales de terceros actualizados a los temas que realmente se distribuyen.

## Desktop 3.5.0
- Ajustes en subpestañas, respaldo/restauración (.zip), metas diaria/semanal, aviso previo, sesiones iniciadas desde una tarea,
  versión de esquema de configuración y pruebas automáticas.

## Desktop 3.4.0
- Agenda (próximos 14 días), frase motivacional destacada, cambio de modo inmediato, tamaño de texto ajustable.

## Anteriores
- Modo «Solo en la app», tareas y estadísticas, imágenes para compartir, temas consolidados, confeti, tutorial,
  «Acerca de» y declaración de privacidad.

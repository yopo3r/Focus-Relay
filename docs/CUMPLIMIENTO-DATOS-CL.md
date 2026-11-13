# Revisión de cumplimiento — Ley 19.628 y Ley 21.719 (Chile)

> **No es asesoría jurídica ni una certificación.** Es una revisión técnica del código frente a la ley, hecha el 2026-11-13. Para tener seguridad jurídica plena, valida las conclusiones con un abogado especialista.

## 1. Marco
- **Ley 21.719** (publicada 13-dic-2024) reforma la Ley 19.628. Su vigencia legal es el **1-dic-2026**; hay un proyecto en trámite (boletín 18.623-07, aprobado por el Senado el 28-oct-2026) que la traslada al **15-oct-2027**; al 2026-11-13 no es ley. Conviene diseñar ya para el nuevo régimen.
- Obligaciones principales: principios (licitud, finalidad, proporcionalidad, calidad, responsabilidad, seguridad, transparencia, confidencialidad), bases de licitud (consentimiento u otras), deber de información (art. 14 ter), medidas de seguridad (14 quinquies), reporte de brechas (14 sexies), derechos ARCO + portabilidad y bloqueo, privacidad por diseño y por defecto.
- Art. 1: la ley no se aplica al tratamiento que efectúan las personas naturales **en relación con sus actividades personales**.

## 2. Rol del autor
Focus Relay se ejecuta íntegramente en el equipo de la persona usuaria. **El autor no recibe, accede ni almacena datos personales de los usuarios** (sin cuentas, telemetría ni servidor). Por ello, el autor **no determina fines y medios de un tratamiento de datos de terceros**: no sería «responsable de datos» respecto de los datos locales. La persona usuaria trata sus propios datos en su ámbito personal (excepción del art. 1). Esta conclusión se sostiene mientras la app no incorpore ningún envío de datos al autor.

> Punto de atención: si alguien usa la app en un contexto institucional (p. ej. una empresa o colegio la instala y exige su uso a terceros), esa institución sería quien debe cumplir.

## 3. Hallazgos del código
| Aspecto | Resultado |
|---|---|
| Telemetría / analítica / cuentas | No existen (verificado: solo `urllib` hacia ESP local, `ice5.somafm.com`, enlace de calendario del usuario y `api.github.com` si el usuario pulsa «Buscar actualizaciones»). |
| Extensión | Solo habla con `127.0.0.1`; guarda estado y puerto en `storage.local`; sin scripts de contenido ni envío externo. Permisos amplios de hosts solo para bloquear sitios (`declarativeNetRequest`). |
| Puente local | `127.0.0.1`, valida `Host` (anti DNS-rebinding), sin cabeceras CORS, POST exige cabecera propia. |
| Transparencia | Declaración de privacidad en la app (11 idiomas) y ahora `PRIVACY.md` (con versión y fecha, estilo art. 14 ter). |
| Derechos | Acceso/portabilidad: respaldo .zip y CSV. Rectificación: edición en la app. Supresión: borrar historial y, **nuevo**, «Borrar todos mis datos…». Oposición: se puede desactivar cada función de red. |
| Seguridad | Archivos atómicos; `config.json` 600; **nuevo:** carpeta de datos 700 (Linux/macOS); enlace de calendario excluido de respaldos. En Windows se hereda la ACL del perfil del usuario. |
| Brechas | Sin servidor ni base de datos central, no hay brecha del autor que reportar. |
| Datos sensibles / menores | No se recogen. La app no pide datos de salud, biométricos ni de menores. |

## 4. Riesgos residuales y recomendaciones
1. **ESP-01S por HTTP sin cifrar** (red local): limitación de hardware; documentada. Recomendación: usar una red doméstica de confianza.
2. **GitHub públicos:** advertencia agregada a la plantilla de bugs; no publicar `hang.log`/rutas con nombre de usuario.
3. **Informe `hang.log`:** contiene pilas de ejecución y rutas; queda local. Se borra con «Borrar todos mis datos…».
4. **Si algún día se agrega** sincronización en la nube, reporte automático de errores, cuentas o analítica: pasarías a ser responsable de datos; necesitarás base de licitud (consentimiento), política completa, canal para ejercer derechos (plazo 30 días corridos), registro de brechas y evaluar transferencias internacionales.
5. Mantener `PRIVACY.md` y el texto in-app sincronizados al cambiar versiones.

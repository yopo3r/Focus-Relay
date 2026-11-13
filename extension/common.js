// Comunicación con la app de escritorio (127.0.0.1, solo este equipo). La app decide qué y cuándo bloquear.
const DEFAULT_PORT = 8765;
async function appBase() {
  let port = DEFAULT_PORT;
  try {
    const s = await chrome.storage.local.get({ appPort: DEFAULT_PORT });
    const n = parseInt(s.appPort, 10);
    if (n >= 1024 && n <= 65535) port = n;
  } catch (e) {}
  return 'http://127.0.0.1:' + port;
}
// Estado de la sesión + «web» ({bloquear, dominios, permitidos}), o null si la app no responde.
async function getState(timeout = 1500) {
  try {
    const r = await fetch((await appBase()) + '/estado', { cache: 'no-store', signal: AbortSignal.timeout(timeout) });
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}
async function postApp(path, body) {
  try {
    const r = await fetch((await appBase()) + path, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Focus-Relay': '1' },
      body: JSON.stringify(body), signal: AbortSignal.timeout(2000)
    });
    return r.ok ? await r.json() : null;
  } catch (e) { return null; }
}
function fmt(v) {
  v = Math.max(0, Number(v) || 0);
  return String(Math.floor(v / 60)).padStart(2, '0') + ':' + String(v % 60).padStart(2, '0');
}
function modeName(e) {                                   // requiere i18n.js
  if (!e) return '';
  if (e.modo === 'P') return t(e.fase === 'D' ? 'mPomD' : 'mPomW');
  return t(e.modo === 'T' ? 'mTemp' : 'mCrono');
}

// Firefox (Manifest V3) no concede al instalar el acceso a los sitios: hay que pedirlo con un clic.
const HOST_ORIGINS = { origins: ['http://*/*', 'https://*/*'] };
async function hasHostAccess() {
  try { return !chrome.permissions || await chrome.permissions.contains(HOST_ORIGINS); } catch (e) { return true; }
}
// Muestra el aviso con el botón si falta el permiso (en Chrome ya está concedido y no aparece nunca).
async function setupPermissionBanner(box, btn, msg) {
  const ok = await hasHostAccess();
  box.hidden = ok;
  if (ok) return;
  msg.textContent = t('pPermiso');
  btn.textContent = t('pPermisoBtn');
  btn.onclick = async () => {                      // debe ejecutarse dentro del clic (gesto del usuario)
    try { if (await chrome.permissions.request(HOST_ORIGINS)) { box.hidden = true; chrome.runtime.sendMessage('poll'); } } catch (e) {}
  };
}

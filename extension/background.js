if (typeof importScripts === 'function') importScripts('common.js');   // Chrome (service worker); Firefox carga los scripts desde el manifiesto
const RULE_BASE = 1000;
function domain(v) {
  let d = String(v || '').trim().toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split(/[/?#]/)[0].split(':')[0].replace(/\.$/, '');
  try { if (d) d = new URL('http://' + d).hostname; } catch (e) { return ''; }   // dominios con acentos (IDN) -> punycode, como los ve el navegador
  return d;
}

async function clearRules() {
  const old = await chrome.declarativeNetRequest.getDynamicRules();
  if (old.length) await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: old.map(r => r.id) });
}
async function applyRules(domains, allowlist = []) {
  const old = await chrome.declarativeNetRequest.getDynamicRules();
  const allowed = new Set(allowlist.map(domain));
  const addRules = domains.map(domain).filter(d => d && !allowed.has(d)).map((d, i) => ({
    id: RULE_BASE + i, priority: 1,
    action: { type: 'redirect', redirect: { extensionPath: '/blocked.html?site=' + encodeURIComponent(d) } },
    condition: {
      regexFilter: '^https?://([^/]+\\.)?' + d.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '(?::[0-9]+)?(/|$)',
      resourceTypes: ['main_frame']
    }
  }));
  await chrome.declarativeNetRequest.updateDynamicRules({ removeRuleIds: old.map(r => r.id), addRules });
}

// Versiones anteriores guardaban aquí sus propias listas: se pasan una vez a la app y se limpia lo que ya no se usa.
async function migrateLegacy() {
  const old = await chrome.storage.local.get(['domains', 'allowlist', 'migrated']);
  if (old.migrated) return;
  if ((old.domains && old.domains.length) || (old.allowlist && old.allowlist.length)) {
    const res = await postApp('/sitios', { importar: old.domains || [], permitidos: old.allowlist || [] });
    if (!res) return;                                   // la app no está abierta: se reintenta en el próximo ciclo
  }
  await chrome.storage.local.remove(['domains', 'allowlist', 'rewards', 'seenSessions', 'lastCancelId', 'lastCompletionToken',
    'lastExecution', 'lastMusicKey', 'musicByMode', 'musicAutoStart', 'musicAutoStop', 'musicVolume', 'musicPlaying',
    'musicCurrent', 'categories', 'espUrl', 'blockMode', 'suspendUntil', 'notifyEarlyStop', 'notifyDisconnect',
    'deviceWasOnline', 'stateSource', 'lastTrophySync', 'theme', 'palette', 'customThemes']);
  await chrome.storage.local.set({ migrated: true });
}

// Una sola consulta a la vez: dos actualizaciones simultáneas de reglas chocarían por los mismos ids.
let _polling = null;
function poll() {
  if (!_polling) _polling = pollOnce().catch(() => {}).finally(() => { _polling = null; });
  return _polling;
}
// Chrome limita las alarmas de extensiones empaquetadas a 30 s: se consulta también al abrir o cambiar de pestaña
// (como mucho cada 3 s) para que el bloqueo web empiece y termine casi a la vez que la sesión.
let _lastKick = 0;
function kick() { if (Date.now() - _lastKick > 3000) { _lastKick = Date.now(); poll(); } }
chrome.tabs.onUpdated.addListener((_id, info) => { if (info.status === 'loading') kick(); });
chrome.tabs.onActivated.addListener(kick);

async function pollOnce() {
  const st = await getState();
  const cur = await chrome.storage.local.get({ appPort: DEFAULT_PORT });
  await chrome.storage.local.set({ lastState: st, lastPoll: Date.now(),
    portLock: st && st.ejecutando ? cur.appPort : null });      // puerto con el que se conectó durante la sesión
  const web = st && st.web;
  if (web && web.bloquear) await applyRules(web.dominios || [], web.permitidos || []);
  else await clearRules();                              // sin app o sin sesión: nada se bloquea
  await chrome.action.setBadgeText({ text: web && web.bloquear ? '●' : '' });
  await chrome.action.setBadgeBackgroundColor({ color: '#5b5bd6' });
  if (st) await migrateLegacy();
}

function schedule() { chrome.alarms.create('poll', { periodInMinutes: 0.1 }); }
chrome.runtime.onInstalled.addListener(() => { schedule(); poll(); });
chrome.runtime.onStartup.addListener(() => { schedule(); poll(); });
chrome.alarms.onAlarm.addListener(a => { if (a.name === 'poll') poll(); });
chrome.runtime.onMessage.addListener((m, _s, send) => { if (m === 'poll') { poll().then(() => send(true)); return true; } });

// Defensa extra: si durante una sesión alguien cambia el puerto (p. ej. desde una página de opciones que ya estaba
// abierta), se restituye el que funcionaba, para no soltar el bloqueo.
chrome.storage.onChanged.addListener(async (ch, area) => {
  if (area !== 'local' || !ch.appPort) return;
  const { portLock, lastPoll } = await chrome.storage.local.get(['portLock', 'lastPoll']);
  if (portLock && Date.now() - (lastPoll || 0) < 90000 && ch.appPort.newValue !== portLock) {
    await chrome.storage.local.set({ appPort: portLock });
  }
});

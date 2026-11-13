const $ = id => document.getElementById(id);

function fillSelects(p) {
  const lang = $('lang'), theme = $('theme');
  lang.innerHTML = '';
  lang.add(new Option(t('oAuto'), 'auto'));
  for (const code in LANGS) lang.add(new Option(LANGS[code], code));
  lang.value = p.lang;
  theme.innerHTML = '';
  [['auto', 'oTemaAuto'], ['light', 'oClaro'], ['dark', 'oOscuro']].forEach(([v, k]) => theme.add(new Option(t(k), v)));
  theme.value = p.theme;
  $('ver').textContent = t('aVersion', { v: chrome.runtime.getManifest().version });
}

// Con una sesión en marcha no se puede cambiar el puerto (desconectaría el bloqueo). Si la app no responde se usa
// el último estado conocido (hasta 90 s), para que tampoco sirva cambiar el puerto a uno equivocado.
async function sessionRunning() {
  const st = await getState(1200);
  if (st) return !!st.ejecutando;
  const { lastState, lastPoll } = await chrome.storage.local.get(['lastState', 'lastPoll']);
  return !!(lastState && lastState.ejecutando && Date.now() - (lastPoll || 0) < 90000);
}
async function syncLock() {
  const locked = await sessionRunning();
  $('port').disabled = locked;
  $('save').disabled = locked;
  $('lock').textContent = locked ? t('oBloqueado') : '';
  return locked;
}

async function init() {
  setupPermissionBanner($('perm'), $('permBtn'), $('permMsg'));
  const p = await applyPrefs();
  fillSelects(p);
  $('port').value = (await chrome.storage.local.get({ appPort: DEFAULT_PORT })).appPort;
  syncLock();
}
setInterval(syncLock, 1500);
chrome.storage.onChanged.addListener((c, a) => { if (a === 'local' && c.appPort) $('port').value = c.appPort.newValue; });

document.querySelectorAll('.tab').forEach(b => b.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.pane').forEach(p => { p.hidden = p.id !== 'pane-' + b.dataset.tab; });
});
// Idioma y tema se aplican al instante.
$('lang').onchange = async () => { await chrome.storage.local.set({ lang: $('lang').value }); init(); };
$('theme').onchange = async () => { await chrome.storage.local.set({ theme: $('theme').value }); applyPrefs(); };
$('save').onclick = async () => {
  if (await syncLock()) return;
  const n = parseInt($('port').value, 10);
  const port = n >= 1024 && n <= 65535 ? n : DEFAULT_PORT;
  $('port').value = port;
  await chrome.storage.local.set({ appPort: port });
  $('msg').textContent = (await getState(1500)) ? t('oOk') : t('oNo');
  chrome.runtime.sendMessage('poll');
};
init();

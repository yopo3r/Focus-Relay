const $ = id => document.getElementById(id);
let host = '';

function render(st) {
  const on = !!st;
  const web = (st && st.web) || {};
  $('dot').className = 'dot' + (on ? ' on' : '');
  $('clock').textContent = st ? fmt(st.segundos) : '--:--';
  if (!on) {
    $('status').textContent = t('pAppCerrada');
    $('detail').textContent = t('pAppCerradaDetalle');
  } else if (web.bloquear) {
    $('status').textContent = t('pEnfoque');
    $('detail').textContent = (st.actividad ? st.actividad + ' · ' : '') + modeName(st);
  } else if (web.pausado) {
    $('status').textContent = t('pPausa');
    $('detail').textContent = t('pPausaDetalle');
  } else {
    $('status').textContent = st.ejecutando ? t('pSinBloqueo') : t('pEspera');
    $('detail').textContent = st.ejecutando ? modeName(st) : t('pIniciaSesion');
  }
  const blocked = !!(on && host && (web.dominios || []).some(d => host === d || host.endsWith('.' + d)));
  $('block').hidden = !(on && host);
  $('block').disabled = blocked;
  $('block').textContent = blocked ? t('pYaBloqueado', { site: host }) : t('pBloquear', { site: host });
}

async function refresh() { render(await getState(1200)); }

async function currentHost() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const u = new URL(tab.url);
    if (!/^https?:$/.test(u.protocol)) return '';
    return u.hostname.replace(/^www\./, '');
  } catch (e) { return ''; }
}

$('block').onclick = async () => {
  const res = await postApp('/sitios', { dominio: host });
  $('note').textContent = res ? t(res.added ? 'pListo' : 'pYaEstaba') : t('pFallo');
  await chrome.runtime.sendMessage('poll');
  refresh();
};
$('options').onclick = e => { e.preventDefault(); chrome.runtime.openOptionsPage(); };
(async () => { await applyPrefs(); setupPermissionBanner($('perm'), $('permBtn'), $('permMsg')); host = await currentHost(); refresh(); setInterval(refresh, 1000); })();

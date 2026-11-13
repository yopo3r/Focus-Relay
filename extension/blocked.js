const $ = id => document.getElementById(id);
const site = new URLSearchParams(location.search).get('site') || '';
$('site').textContent = site;
$('back').onclick = () => { if (history.length > 1) history.back(); else location.href = 'about:blank'; };
async function tick() {
  const st = await getState(1200);
  if (!st) return;
  $('clock').textContent = fmt(st.segundos);
  $('task').textContent = st.actividad || '';
  if (!(st.web && st.web.bloquear) && site) location.href = 'https://' + site;     // terminó la sesión: vuelve al sitio
}
applyPrefs().then(() => { tick(); setInterval(tick, 1000); });

const $ = selector => document.querySelector(selector);
const fragment = new URLSearchParams(location.hash.slice(1));
const incoming = fragment.get('session');
if (incoming) { sessionStorage.setItem('astra-session', incoming); history.replaceState(null, '', location.pathname); }
const secret = sessionStorage.getItem('astra-session') || '';
let busy = false;
const pages = { overview: 'Overview', setup: 'Guided setup', connections: 'Connections', tasks: 'Tasks & reminders', assistant: 'Ask Astra', tools: 'Local tools', help: 'Help & guides' };
function go(page) {
  if (!pages[page]) return;
  document.querySelectorAll('.page').forEach(el => el.classList.toggle('active', el.id === page));
  document.querySelectorAll('.nav').forEach(el => el.classList.toggle('active', el.dataset.page === page));
  $('#breadcrumb').textContent = 'Workspace / ' + pages[page];
  if (page === 'tasks' && secret) loadTasks().catch(showError);
  window.scrollTo({ top: 0, behavior: 'instant' });
}
async function api(path, body) {
  const response = await fetch(path, { method: body ? 'POST' : 'GET', headers: { Authorization: 'Bearer ' + secret, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed');
  return value;
}
function showError(error) { $('#operation').classList.remove('hidden'); $('#operation-title').textContent = 'Needs attention'; $('#operation-output').textContent = error.message; }
function element(tag, text, className) { const el = document.createElement(tag); el.textContent = text; if (className) el.className = className; return el; }
function toolRow(name, present, yes = 'Installed', no = 'Not installed') { const row = element('div', '', 'tool-row'); row.append(element('span', name), element('span', present ? yes : no, 'badge' + (present ? ' good' : ''))); return row; }
async function refresh() {
  const state = await api('/api/status');
  const value = state.settings;
  for (const [key, val] of Object.entries(value)) {
    if (key === 'provider_api_key') continue;
    document.querySelectorAll(`[name="${key}"]`).forEach(input => { if (input.type === 'checkbox') input.checked = val; else input.value = Array.isArray(val) ? val.join(', ') : val; });
  }
  $('#readiness').replaceChildren(toolRow('Your identity', !!value.owner_phone && !!value.owner_name, 'Saved', 'Not set'), toolRow('Runtime setup', value.runtime_configured, 'Configured', 'Not configured'), toolRow('OpenClaw', state.tools.openclaw), toolRow('OmniRoute', state.tools.omniroute));
  $('#essential-tools').replaceChildren(toolRow('node', state.tools.node), toolRow('OpenClaw (private)', state.private_core.openclaw), toolRow('OmniRoute (private)', state.private_core.omniroute));
  $('#setup-progress').textContent = value.runtime_configured ? 'Runtime configured · check health to verify' : value.owner_phone ? 'Identity saved · continue setup' : 'Begin with your identity';
}
async function run(action, params = {}) {
  if (busy) return showError(new Error('An operation is already running. Please wait for its result.'));
  busy = true;
  $('#operation').classList.remove('hidden'); $('#operation-title').textContent = 'Working · ' + action; $('#operation-output').textContent = action === 'google.login' ? 'Complete sign-in and consent in the browser. This operation can take several minutes.' : 'Waiting for an actual operation result…';
  document.querySelectorAll('[data-action],form button').forEach(button => button.disabled = true);
  try {
    const job = await api('/api/actions', { action, params });
    let result;
    do { await new Promise(resolve => setTimeout(resolve, 800)); result = await api('/api/jobs/' + job.id); } while (result.state === 'running');
    if (result.state === 'failed') throw new Error(result.error);
    $('#operation-title').textContent = 'Result · ' + action;
    $('#operation-output').textContent = typeof result.result === 'string' ? result.result : JSON.stringify(result.result, null, 2);
    if (action === 'ask') $('#answer').textContent = result.result.text;
    if (action === 'whatsapp.link') {
      const qr = result.result.qrDataUrl;
      $('#qr').replaceChildren();
      if (typeof qr === 'string' && /^data:image\/(png|svg\+xml);base64,/.test(qr)) { const image = document.createElement('img'); image.src = qr; image.alt = 'Private WhatsApp linking QR'; $('#qr').append(image); $('#operation-output').textContent = 'Scan the private QR above, then click Check link.'; }
    }
    if (action === 'whatsapp.wait' && result.result.connected === true) $('#qr').replaceChildren();
    if (action.startsWith('tasks.')) await loadTasks();
    if (action === 'settings.save' || action === 'runtime.apply' || action.startsWith('instagram.')) await refresh();
    return result.result;
  } catch (error) { showError(error); }
  finally { busy = false; document.querySelectorAll('[data-action],form button').forEach(button => button.disabled = false); }
}
async function guide(name) { try { const value = await api('/api/help?name=' + encodeURIComponent(name)); go('help'); $('#guide-content').textContent = value.text; } catch (error) { showError(error); } }
async function loadTasks() {
  const rows = await api('/api/tasks');
  const list = $('#task-list'); list.replaceChildren(); list.className = rows.length ? '' : 'empty';
  if (!rows.length) { list.textContent = 'No reminders yet. Add one when you need it.'; return; }
  for (const task of rows.slice().reverse()) {
    const row = element('div', '', 'task-row');
    row.append(element('strong', task.title), element('code', task.id), document.createTextNode(' '), element('span', task.status, 'badge' + (task.status === 'active' ? ' good' : ' warning')), element('p', `${task.schedule.kind}: ${task.schedule.value} · ${task.schedule.timezone} · ${task.assignee}`, 'fine'));
    if (task.status === 'active') {
      const buttons = element('div', '', 'buttons');
      for (const [action, label] of [['complete', 'Complete'], ['cancel', 'Cancel'], ['postpone', 'Postpone']]) {
        const button = element('button', label, 'secondary small');
        button.onclick = () => { const params = { id: task.id }; if (action === 'postpone') { params.at = prompt('New time (for example 20m or an ISO timestamp):'); if (!params.at) return; } run('tasks.' + action, params); };
        buttons.append(button);
      }
      row.append(buttons);
    }
    if (['uncertain', 'provisioning'].includes(task.status)) {
      const button = element('button', 'Reconcile existing scheduler job', 'secondary small');
      button.onclick = () => run('tasks.reconcile', { id: task.id }); row.append(button);
    }
    list.append(row);
  }
}
document.addEventListener('click', event => {
  const target = event.target.closest('button,a'); if (!target) return;
  if (target.dataset.page || target.dataset.go) go(target.dataset.page || target.dataset.go);
  if (target.dataset.guide) guide(target.dataset.guide);
  if (target.dataset.action) run(target.dataset.action, target.dataset.platform ? { platform: target.dataset.platform, reviewed: target.dataset.action === 'guard.resume' } : {});
});
$('#refresh').onclick = () => refresh().catch(showError);
$('#tasks-refresh').onclick = () => loadTasks().catch(showError);
$('#dismiss-operation').onclick = () => { if (!busy) $('#operation').classList.add('hidden'); };
$('#settings-form').onsubmit = event => { event.preventDefault(); const form = event.target; const data = Object.fromEntries(new FormData(form)); for (const key of ['delegates', 'fallback_models']) data[key] = data[key].split(',').map(x => x.trim()).filter(Boolean); for (const key of ['away_enabled', 'voice_autoplay', 'public_chat_enabled']) data[key] = form.elements[key].checked; data.away_quiet_minutes = Number(data.away_quiet_minutes); run('settings.save', data).then(result => { if (result) form.elements.provider_api_key.value = ''; }); };
for (const [form, field] of [['google-form', 'google_email'], ['instagram-form', 'instagram_username']]) $( '#' + form).onsubmit = event => { event.preventDefault(); run('settings.save', { [field]: event.target.elements[field].value }); };
$('#google-client').onchange = async event => { try { const file = event.target.files[0]; if (!file) return; if (file.size > 1024 * 1024) throw new Error('Choose the small Desktop OAuth JSON file.'); await run('google.import', { client: JSON.parse(await file.text()) }); } catch (error) { showError(error); } finally { event.target.value = ''; } };
$('#task-form').onsubmit = event => { event.preventDefault(); const value = Object.fromEntries(new FormData(event.target)); run('tasks.create', { title: value.title, assignee: value.assignee, [value.kind]: value.when }); };
$('#ask-form').onsubmit = event => { event.preventDefault(); run('ask', { prompt: event.target.elements.prompt.value }); };
$('#phone-form').onsubmit = event => { event.preventDefault(); run('phone.screen', { serial: event.target.elements.serial.value }); };
$('#persona-form').onsubmit = event => { event.preventDefault(); run('persona.collect', { before: event.target.elements.before.value }); };
$('#calendar-form').onsubmit = event => { event.preventDefault(); run('calendar.export', Object.fromEntries(new FormData(event.target))); };
if (!secret) $('#auth-warning').classList.remove('hidden'); else refresh().catch(showError);

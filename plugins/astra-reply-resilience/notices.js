import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { config, ownerTarget } from './identity.js';

const execute = promisify(execFile);
export function technical(text) {
  return typeof text === 'string' && /^(?:⚠️\s*)?(?:Agent (?:failed|couldn't)|No reply was generated|Request timed out|Error:|Traceback|LLM_COMPLETION_|OutboundDeliveryError|My model declined|That task reached|Audio delivery is blocked|I couldn't finish|I'm here, but the model)/i.test(text.trim());
}
export function errorCode(error) {
  if (/^[A-Z_]{3,64}$/.test(error?.code ?? '')) return error.code;
  if (/content_filter|content policy/i.test(error?.message ?? error ?? '')) return 'MODEL_FILTERED';
  if (/timeout|timed out|abort/i.test(error?.message ?? error ?? '')) return 'REPLY_TIMEOUT';
  return 'REPLY_FAILED';
}
export function createNotices(shared, guard, { now = Date.now, send, load, persist } = {}) {
  const cfg = config(), directory = join(cfg.stateDir, 'notices');
  let timer;
  function state() {
    if (shared.notices) return shared.notices;
    let data;
    try { data = load ? load() : JSON.parse(readFileSync(join(directory, 'state.json'), 'utf8')); }
    catch (error) { if (load || error.code !== 'ENOENT') shared.noticesFailed = true; }
    if (data && (!Array.isArray(data.pending) || !data.seen)) shared.noticesFailed = true;
    return shared.notices = data && !shared.noticesFailed ? data : { pending: [], seen: {}, lastAttempt: 0, sent: 0 };
  }
  function save() {
    if (shared.noticesFailed) return;
    try {
      if (persist) persist(state());
      else { mkdirSync(directory, { recursive: true, mode: 0o700 });
        const path = join(directory, `state.${process.pid}.tmp`);
        writeFileSync(path, JSON.stringify(state()), { mode: 0o600 }); renameSync(path, join(directory, 'state.json')); }
    } catch { shared.noticesFailed = true; }
  }
  function schedule() {
    if (timer || shared.noticesSending || shared.noticesFailed || !ownerTarget() || !state().pending.length || !guard.platformCheck('whatsapp').allowed) return;
    timer = setTimeout(() => { timer = undefined; void flush(); }, Math.max(0, state().lastAttempt + 60000 - now())); timer.unref?.();
  }
  function report({ sender = '', messageId = '', code = 'REPLY_FAILED' } = {}) {
    const data = state();
    if (shared.noticesFailed) return;
    const safe = /^[A-Z_]{3,64}$/.test(code) ? code : 'REPLY_FAILED';
    const id = createHash('sha256').update(`${sender}:${messageId || Math.floor(now() / 600000)}:${safe}`).digest('hex');
    for (const [key, at] of Object.entries(data.seen)) if (now() - at >= 86400000) delete data.seen[key];
    if (data.seen[id]) return;
    data.seen[id] = now();
    while (Object.keys(data.seen).length > 1000) delete data.seen[Object.keys(data.seen)[0]];
    data.pending.push({ code: safe, at: now() }); data.pending = data.pending.slice(-100); save(); schedule();
  }
  async function flush() {
    const data = state();
    if (shared.noticesSending || shared.noticesFailed || !data.pending.length || !guard.platformCheck('whatsapp').allowed) return;
    if (now() < data.lastAttempt + 60000) { schedule(); return; }
    const batch = data.pending.splice(0, 100);
    data.lastAttempt = now(); data.lastBatch = { status: 'attempted', count: batch.length }; save();
    if (shared.noticesFailed) return;
    const text = `Astra private notice: ${batch.length} contact reply failure(s) were kept out of their chats.\n` +
      [...new Set(batch.map(x => x.code))].slice(0, 8).join(', ') + '\nNo task actions were replayed.';
    shared.noticesSending = true;
    try {
      const result = send ? await send(text, ownerTarget()) : JSON.parse((await execute(cfg.openclawBin,
        ['--profile', cfg.profile, 'message', 'send', '--channel', 'whatsapp', '--account', 'default', '--target', ownerTarget(), '--message', text, '--json'],
        { timeout: 20000, maxBuffer: 16384 })).stdout);
      if (result?.ok === false || result?.success === false) throw new Error('unconfirmed');
      data.sent++; data.lastBatch.status = 'sent';
    } catch { data.lastBatch.status = 'unconfirmed'; }
    finally { shared.noticesSending = false; save(); schedule(); }
  }
  return { report, flush, resume: schedule, stop: () => { clearTimeout(timer); timer = undefined; },
    status: () => ({ pending: state().pending.length, sent: state().sent, storageAvailable: !shared.noticesFailed }) };
}

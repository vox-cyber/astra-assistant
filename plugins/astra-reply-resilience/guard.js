import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync, renameSync } from 'node:fs';
import { join } from 'node:path';
import { config, canonical, owner, trusted, awayText } from './identity.js';

const DAY = 86400000, HOUR = 3600000;
const hash = value => createHash('sha256').update(String(value)).digest('hex');
export const LIMITS = { contactPerHour: 12, externalPerHour: 40, externalPerDay: 120,
  ownerPerHour: 120, ownerPerDay: 600, duplicateMs: 600000 };
export function restriction(error) {
  const text = typeof error === 'string' ? error : error?.message ?? '';
  if (/\b429\b|too many requests|rate.?limit|retry.after/i.test(text)) return 'PLATFORM_RATE_LIMIT';
  if (/account.{0,40}(banned|suspended|disabled|restricted)|temporarily banned|feedback_required|action blocked/i.test(text)) return 'PLATFORM_RESTRICTED';
  if (/checkpoint_required|challenge_required|login_required|logged.?out|captcha|verification required/i.test(text)) return 'PLATFORM_VERIFICATION';
}
export function platformOf(event) {
  const p = event.params ?? {};
  if (event.toolName === 'message' && ['whatsapp', 'instagram'].includes(p.channel)) return p.channel;
  if (event.toolName === 'browser' && (p.profile ?? p.browserProfile) === 'instagram') return 'instagram';
  if (event.toolName === 'exec' && /\bwacli\b|\bwhatsapp\b/i.test(p.command ?? '')) return 'whatsapp';
}

export function createGuard(shared = {}, { now = Date.now, load, persist, limits = LIMITS } = {}) {
  const cfg = config(), directory = join(cfg.stateDir, 'messaging');
  const destination = (platform, raw) => platform === 'whatsapp' ? canonical(raw) :
    typeof raw === 'string' && /^@?[\w.]{1,64}$/.test(raw) ? raw.replace(/^@/, '').toLowerCase() : undefined;
  function state() {
    if (shared.policy) return shared.policy;
    let value;
    try { value = load ? load() : JSON.parse(readFileSync(join(directory, 'state.json'), 'utf8')); }
    catch (error) { if (load || error.code !== 'ENOENT') shared.storageFailed = true; }
    if (value && (value.version !== 1 || !value.peers || typeof value.peers !== 'object' || Array.isArray(value.peers) ||
        !value.paused || typeof value.paused !== 'object' || Array.isArray(value.paused) || !Array.isArray(value.attempts) ||
        Object.keys(value.peers).length > 10000 || value.attempts.length > 10000 ||
        Object.values(value.peers).some(x => !x || typeof x !== 'object' || Array.isArray(x)) ||
        value.attempts.some(x => !Number.isFinite(x.at) || typeof x.peer !== 'string' || typeof x.body !== 'string') ||
        value.ownerActivity && !Number.isFinite(value.ownerActivity.at) ||
        value.awayWindow && (typeof value.awayWindow.id !== 'string' || !Number.isFinite(value.awayWindow.expiresAt)) ||
        value.automation && (!Array.isArray(value.automation) || value.automation.length > 5000 || value.automation.some(x => typeof x.id !== 'string' || !Number.isFinite(x.at))))) {
      shared.storageFailed = true; value = undefined;
    }
    return shared.policy = value || { version: 1, peers: {}, paused: {}, attempts: [], automation: [] };
  }
  function save() {
    const data = state();
    if (shared.storageFailed) return false;
    data.attempts = data.attempts.filter(x => now() - x.at < DAY);
    try {
      if (persist) persist(data);
      else {
        mkdirSync(directory, { recursive: true, mode: 0o700 });
        const temporary = join(directory, `state.${process.pid}.tmp`);
        writeFileSync(temporary, JSON.stringify(data), { mode: 0o600 });
        renameSync(temporary, join(directory, 'state.json'));
      }
      return true;
    } catch { shared.storageFailed = true; return false; }
  }
  function platformCheck(platform) {
    if (!['whatsapp', 'instagram'].includes(platform)) return { allowed: false, reason: 'invalid_platform' };
    const data = state();
    if (shared.storageFailed) return { allowed: false, reason: 'storage_unavailable' };
    if (data.paused[platform]) return { allowed: false, reason: 'platform_paused' };
    return { allowed: true };
  }
  function activityCheck() {
    if (!cfg.awayEnabled) return { allowed: true };
    if (state().awayWindow && now() >= state().awayWindow.expiresAt) return { allowed: false, reason: 'away_window_expired' };
    if (!shared.observerReady) return { allowed: false, reason: 'owner_activity_unavailable' };
    if (shared.ownerOnline) return { allowed: false, reason: 'owner_online' };
    if (shared.ownerPending) return { allowed: false, reason: 'owner_message_pending' };
    if (Number.isFinite(state().ownerActivity?.at) && now() - state().ownerActivity.at < cfg.quietMinutes * 60000)
      return { allowed: false, reason: 'owner_recently_active' };
    return { allowed: true };
  }
  function recordActivity(at = now(), source = 'owner_sent_message') {
    if (!Number.isFinite(at) || at < 0 || at > now() + 60000) return false;
    if (at <= (state().ownerActivity?.at ?? 0)) return true;
    state().ownerActivity = { at: Math.min(at, now()), source };
    return save();
  }
  function setAwayWindow(id, expiresAt) {
    if (!cfg.awayEnabled || typeof id !== 'string' || !/^[a-f0-9]{32}$/.test(id) ||
        !Number.isFinite(expiresAt) || expiresAt <= now() || expiresAt > now() + DAY) return false;
    state().awayWindow = { id, startedAt: now(), expiresAt }; return save();
  }
  function automation(id) {
    if (typeof id !== 'string' || !id) return false;
    const data = state(), digest = hash(id);
    data.automation = (data.automation ?? []).filter(x => now() - x.at < DAY);
    if (data.automation.some(x => x.id === digest)) return true;
    data.automation.push({ id: digest, at: now() });
    data.automation = data.automation.slice(-5000);
    return save();
  }
  const isAutomation = id => typeof id === 'string' && (state().automation ?? []).some(x => x.id === hash(id) && now() - x.at < DAY);
  function optOut(platform, raw) {
    const address = destination(platform, raw);
    if (!address) return false;
    const key = hash(platform + ':' + address);
    if (!state().peers[key] && Object.keys(state().peers).length >= 10000) return false;
    state().peers[key] = { optedOut: true };
    return save();
  }
  function incoming(raw, body) {
    const valid = platformCheck('whatsapp'); if (!valid.allowed) return valid;
    const address = destination('whatsapp', raw);
    if (!address) return { allowed: false, reason: 'unknown_sender' };
    if (owner(raw)) return { allowed: true };
    const text = typeof body === 'string' ? body.trim() : '', key = hash('whatsapp:' + address), peer = state().peers[key] ?? {};
    if (/^(?:stop(?:\s+(?:astra|nemo|bot|messages))?|unsubscribe|opt[ -]?out|human|talk to (?:a )?human|do not message me|no more messages)[.!\s]*$/i.test(text) &&
        !(trusted(raw) && /^stop[.!\s]*$/i.test(text))) {
      optOut('whatsapp', raw); return { allowed: false, reason: 'opted_out' };
    }
    const start = /^(start|resume)\s+(astra|nemo)[.!\s]*$/i.test(text);
    if (peer.optedOut && !start) return { allowed: false, reason: 'opted_out' };
    const task = trusted(raw) && (/\b(astra|nemo)\b/i.test(text) || /^(stop|cancel|pause|ping)[.!\s]*$/i.test(text));
    if (task) return { allowed: true };
    if (!state().peers[key] && Object.keys(state().peers).length >= 10000) return { allowed: false, reason: 'store_full' };
    if (cfg.awayEnabled) {
      const active = activityCheck(); if (!active.allowed) return active;
      if (Number.isFinite(peer.awayAt) && now() - peer.awayAt < DAY) return { allowed: false, reason: 'already_acknowledged' };
      state().peers[key] = { ...peer, optedOut: false, awayUntil: now() + DAY };
      return save() ? { allowed: true, text: awayText(), kind: 'away' } : { allowed: false, reason: 'storage_unavailable' };
    }
    if (trusted(raw)) return { allowed: true };
    if (!cfg.publicChatEnabled || !start && !/\b(astra|nemo)\b/i.test(text) && !(peer.until > now()))
      return { allowed: false, reason: 'assistant_not_requested' };
    state().peers[key] = { ...peer, optedOut: false, until: now() + DAY };
    return save() ? { allowed: true, kind: 'chat' } : { allowed: false, reason: 'storage_unavailable' };
  }
  function preflight(platform, raw) {
    const valid = platformCheck(platform); if (!valid.allowed) return valid;
    const address = destination(platform, raw); if (!address) return { allowed: false, reason: 'invalid_destination' };
    const key = hash(platform + ':' + address), peer = state().peers[key];
    if (peer?.optedOut) return { allowed: false, reason: 'opted_out' };
    if (platform === 'whatsapp' && !trusted(raw) && !(peer?.until > now() || cfg.awayEnabled && peer?.awayUntil > now()))
      return { allowed: false, reason: 'no_recent_inbound' };
    return { allowed: true, key, owner: platform === 'whatsapp' && owner(raw) };
  }
  function reserve(platform, raw, content, { requestId, inboundAt } = {}) {
    const valid = preflight(platform, raw); if (!valid.allowed) return valid;
    if (platform === 'instagram' && (!Number.isFinite(inboundAt) || inboundAt > now() || now() - inboundAt >= DAY))
      return { allowed: false, reason: 'recent_inbound_required' };
    if (typeof content !== 'string' || !content.trim()) return { allowed: false, reason: 'missing_content' };
    const data = state(), peer = data.peers[valid.key], isAway = cfg.awayEnabled && !valid.owner && content.trim() === awayText();
    if (cfg.awayEnabled && platform === 'whatsapp' && !trusted(raw) && !isAway) return { allowed: false, reason: 'away_text_only' };
    if (isAway) {
      const active = activityCheck(); if (!active.allowed) return active;
      if (platform === 'instagram' && Number.isFinite(data.awayActivatedAt) && inboundAt < data.awayActivatedAt)
        return { allowed: false, reason: 'before_activation' };
      if (platform === 'instagram' && inboundAt <= (data.ownerActivity?.at ?? 0) + cfg.quietMinutes * 60000)
        return { allowed: false, reason: 'suppressed_old_inbound' };
      if (Number.isFinite(peer?.awayAt) && now() - peer.awayAt < DAY) return { allowed: false, reason: 'already_acknowledged' };
    }
    const attempts = data.attempts.filter(x => now() - x.at < DAY), body = hash(content.trim()), request = requestId ? hash(requestId) : undefined;
    if (attempts.some(x => x.peer === valid.key && (x.body === body && now() - x.at < limits.duplicateMs ||
        request && x.request === request && (platform === 'instagram' || x.body === body)))) return { allowed: false, reason: 'duplicate_attempt' };
    const group = attempts.filter(x => x.platform === platform && x.owner === valid.owner), hour = group.filter(x => now() - x.at < HOUR);
    if (group.length >= (valid.owner ? limits.ownerPerDay : limits.externalPerDay) || hour.length >= (valid.owner ? limits.ownerPerHour : limits.externalPerHour) ||
        !valid.owner && hour.filter(x => x.peer === valid.key).length >= limits.contactPerHour) return { allowed: false, reason: 'local_volume_limit' };
    data.attempts = [...attempts, { at: now(), platform, peer: valid.key, owner: valid.owner, body, ...(request ? { request } : {}) }];
    if (isAway) data.peers[valid.key] = { ...peer, awayAt: now() };
    return save() ? { allowed: true } : { allowed: false, reason: 'storage_unavailable' };
  }
  function pause(platform, code = 'OPERATOR_PAUSED') {
    if (!['whatsapp', 'instagram'].includes(platform)) return false;
    state().paused[platform] = { code, at: now() }; return save();
  }
  function resume(platform, reviewed) {
    if (reviewed !== true || !['whatsapp', 'instagram'].includes(platform)) return false;
    delete state().paused[platform]; return save();
  }
  function observation({ ready, online, pending } = {}) {
    if (ready !== undefined) shared.observerReady = ready === true;
    if (online !== undefined) shared.ownerOnline = online === true;
    if (pending !== undefined) shared.ownerPending = pending;
  }
  function status() {
    const data = state();
    return { storageAvailable: !shared.storageFailed, paused: data.paused, limits,
      optOuts: Object.values(data.peers).filter(x => x.optedOut).length,
      attemptsLastDay: data.attempts.filter(x => now() - x.at < DAY).length,
      awayReply: { enabled: cfg.awayEnabled && !(data.awayWindow && now() >= data.awayWindow.expiresAt),
        window: data.awayWindow ? { ...data.awayWindow, expired: now() >= data.awayWindow.expiresAt } : null,
        activatedAt: data.awayActivatedAt ?? null, text: awayText(), perSenderCooldownHours: 24,
        privateContextUsed: false, ownerActivity: { ...activityCheck(), quietMinutes: cfg.quietMinutes,
          observerReady: Boolean(shared.observerReady), onlineObserved: Boolean(shared.ownerOnline),
          lastActiveAt: data.ownerActivity?.at ?? null, pauseUntil: data.ownerActivity ? data.ownerActivity.at + cfg.quietMinutes * 60000 : null } },
      banPreventionGuaranteed: false };
  }
  return { incoming, reserve, preflight, pause, resume, optOut, recordActivity, setAwayWindow, automation, isAutomation,
    observation, activityCheck, platformCheck, status, initialize: () => {
      const data = state();
      if (cfg.awayEnabled && !data.awayWasEnabled) { data.awayActivatedAt = now(); delete data.awayWindow; }
      data.awayWasEnabled = cfg.awayEnabled;
      return save();
    },
    observeFailure: (platform, error) => { const code = restriction(error); if (code) pause(platform, code); return code; } };
}

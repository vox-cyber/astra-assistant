import { config, owner, canonical, addOwnerAlias } from './identity.js';

export function createActivity(shared, { runtime, guard, now = Date.now }) {
  if (shared.activity) return shared.activity;
  let controller, socket, timer, unwatch, original, wrapper, inFlight = 0;
  const pending = new Map(), key = { channelId: 'whatsapp', accountId: 'default', capability: 'connection-controller' };
  function clear(id) { const item = pending.get(id); if (item) clearTimeout(item.timer); pending.delete(id); guard.observation({ pending: pending.size }); }
  function automated(id) { guard.automation(id); clear(id); }
  function settle(id, force = false) {
    const item = pending.get(id);
    if (item && inFlight && !force) { item.timer = setTimeout(() => settle(id), 500); item.timer.unref?.(); return; }
    clear(id);
    if (item && !guard.isAutomation(id)) guard.recordActivity(item.at, inFlight ? 'unclassified_owner_activity' : 'owner_sent_message');
  }
  function messages(update = {}) {
    if (!['notify', 'append'].includes(update.type)) return;
    for (const message of update.messages ?? []) {
      const id = message.key?.id;
      if (!message.key?.fromMe || typeof id !== 'string' || !id || guard.isAutomation(id) || pending.has(id)) continue;
      const timestamp = Number(message.messageTimestamp), at = timestamp > 0 ? timestamp * 1000 : now();
      if (!Number.isFinite(at) || at > now() + 60000 || now() - at >= config().quietMinutes * 60000) continue;
      if (pending.size >= 1000) { guard.recordActivity(now(), 'activity_overflow'); continue; }
      const handle = setTimeout(() => settle(id), 500); handle.unref?.();
      pending.set(id, { at: Math.min(at, now()), timer: handle });
      guard.observation({ pending: pending.size });
    }
  }
  function presence(update = {}) {
    for (const [id, info] of Object.entries(update.presences ?? {})) {
      if (!owner(id)) continue;
      if (['available', 'composing', 'recording'].includes(info.lastKnownPresence)) {
        guard.observation({ online: true }); guard.recordActivity(now(), 'owner_presence');
      } else if (info.lastKnownPresence === 'unavailable') guard.observation({ online: false });
    }
  }
  function detach() {
    socket?.ev?.off?.('messages.upsert', messages); socket?.ev?.off?.('presence.update', presence);
    if (socket && socket.sendMessage === wrapper) socket.sendMessage = original;
    for (const id of [...pending.keys()]) settle(id, true);
    socket = undefined; guard.observation({ ready: false, online: false, pending: 0 });
  }
  function refresh() {
    const next = controller?.getCurrentSock?.(); if (next === socket) return;
    detach();
    if (!next?.ev?.on || typeof next.sendMessage !== 'function') return;
    // Alias discovery uses only the authenticated account's public identity,
    // and requires a match to the number already chosen in local setup.
    if (!owner(next.user?.id)) {
      const self = controller?.getSelfIdentity?.();
      if (!owner(self?.e164)) return;
      addOwnerAlias(self.jid); addOwnerAlias(self.lid);
    }
    if (!owner(next.user?.id)) return;
    if (next.user?.lid) addOwnerAlias(next.user.lid);
    socket = next; original = socket.sendMessage; const send = original;
    wrapper = function (...args) {
      inFlight++;
      let result; try { result = send.apply(this, args); } catch (error) { inFlight--; throw error; }
      Promise.resolve(result).then(sent => { inFlight--; if (sent?.key?.id) automated(sent.key.id); }, () => { inFlight--; });
      return result;
    };
    socket.sendMessage = wrapper;
    socket.ev.on('messages.upsert', messages); socket.ev.on('presence.update', presence);
    guard.observation({ ready: true });
  }
  function start() {
    if (timer) return;
    const registry = runtime?.channel?.runtimeContexts;
    if (!registry?.get || !registry?.watch) return;
    controller = registry.get(key);
    unwatch = registry.watch({ ...key, onEvent: () => { controller = registry.get(key); refresh(); } });
    refresh(); timer = setInterval(refresh, 1000); timer.unref?.();
  }
  function stop() { clearInterval(timer); timer = undefined; unwatch?.(); detach(); }
  return shared.activity = { start, stop, automated, status: () => ({ attached: Boolean(socket),
    pollingNetwork: false, waitsForAutomationSendIds: true, appOpenDetection: 'platform_exposed_owner_presence_only' }) };
}

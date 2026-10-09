import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { configure } from '../plugins/astra-reply-resilience/identity.js';
import { createGuard } from '../plugins/astra-reply-resilience/guard.js';
import { createActivity } from '../plugins/astra-reply-resilience/activity.js';

const OWNER = '+15555550100';
function fixture(t, send = () => Promise.resolve({ key: { id: 'automatic-id' } })) {
  configure({ ownerIds: [OWNER], awayEnabled: true, quietMinutes: 15 });
  let clock = 2000000000, stored;
  const shared = {};
  const guard = createGuard(shared, { now: () => clock, load: () => undefined, persist: x => { stored = structuredClone(x); } });
  const socket = { user: { id: OWNER.slice(1) + ':1@s.whatsapp.net' }, ev: new EventEmitter(), sendMessage: send };
  const controller = { getCurrentSock: () => socket };
  const runtime = { channel: { runtimeContexts: { get: () => controller, watch: () => () => {} } } };
  const activity = createActivity(shared, { runtime, guard, now: () => clock });
  activity.start(); t.after(() => activity.stop());
  return { guard, socket, activity, now: () => clock, advance: x => { clock += x; }, saved: () => stored };
}

test('manual owner send to any chat blocks immediately and persists after classification', async t => {
  const f = fixture(t);
  f.socket.ev.emit('messages.upsert', { type: 'notify', messages: [{ key: { id: 'manual-id', fromMe: true, remoteJid: 'other@lid' }, messageTimestamp: f.now() / 1000 }] });
  assert.equal(f.guard.activityCheck().reason, 'owner_message_pending');
  await new Promise(resolve => setTimeout(resolve, 550));
  assert.equal(f.guard.activityCheck().reason, 'owner_recently_active');
  assert.equal(f.saved().ownerActivity.at, f.now());
  f.advance(900001);
  assert.equal(f.guard.activityCheck().allowed, true);
});

test('delayed generated send preserves promise identity and never restarts human quiet period', async t => {
  let complete;
  const promise = new Promise(resolve => { complete = resolve; });
  const f = fixture(t, () => promise);
  assert.equal(f.socket.sendMessage('target', { text: 'synthetic' }), promise);
  f.socket.ev.emit('messages.upsert', { type: 'notify', messages: [{ key: { id: 'automatic-id', fromMe: true }, messageTimestamp: f.now() / 1000 }] });
  await new Promise(resolve => setTimeout(resolve, 550));
  assert.equal(f.guard.activityCheck().reason, 'owner_message_pending');
  complete({ key: { id: 'automatic-id' } });
  await promise; await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(f.guard.activityCheck().allowed, true);
  assert.equal(f.guard.status().awayReply.ownerActivity.lastActiveAt, null);
});

test('only authenticated owner presence changes activity state', t => {
  const f = fixture(t);
  f.socket.ev.emit('presence.update', { presences: { '15555550102@s.whatsapp.net': { lastKnownPresence: 'available' } } });
  assert.equal(f.guard.activityCheck().allowed, true);
  f.socket.ev.emit('presence.update', { presences: { '15555550100@s.whatsapp.net': { lastKnownPresence: 'composing' } } });
  assert.equal(f.guard.activityCheck().reason, 'owner_online');
});

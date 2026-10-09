import { homedir } from 'node:os';
import { join } from 'node:path';

const key = Symbol.for('astra.community.identity.v1');
const identity = globalThis[key] ??= { config: {}, aliases: new Set(), ownerKey: '' };
export function canonical(raw) {
  if (typeof raw !== 'string') return;
  const value = raw.replace(/^whatsapp:/, '').replace(/:\d+@/, '@');
  if (/^\d{7,20}@lid$/.test(value)) return value;
  const match = /^\+?(\d{7,15})(?:@s\.whatsapp\.net)?$/.exec(value);
  return match ? '+' + match[1] : undefined;
}
export function configure(config = {}) {
  const owners = (config.ownerIds ?? []).map(canonical).filter(Boolean);
  const ownerKey = owners.join(',');
  if (identity.ownerKey !== ownerKey) identity.aliases.clear();
  identity.ownerKey = ownerKey;
  identity.config = { ownerIds: owners, delegates: [], ownerName: 'the account owner',
    stateDir: join(homedir(), '.local/share/astra/private/runtime'),
    workspace: join(homedir(), '.local/share/astra/workspace'), openclawBin: 'openclaw',
    profile: 'astra-community', inboundDir: join(homedir(), '.openclaw-astra-community/media/inbound'),
    primaryModel: 'omniroute/kg/kilo-auto/free', fallbackModels: [], awayEnabled: false,
    publicChatEnabled: false, quietMinutes: 15, instagramJobId: '', voiceEnabled: false,
    ...config, ownerIds: owners };
  return identity.config;
}
export function config() { return identity.config; }
export function owner(raw) {
  const value = canonical(raw);
  return Boolean(value && ((identity.config.ownerIds ?? []).includes(value) || identity.aliases.has(value)));
}
export function trusted(raw) {
  const value = canonical(raw);
  return owner(raw) || Boolean(value && (identity.config.delegates ?? []).map(canonical).includes(value));
}
export function addOwnerAlias(raw) { const value = canonical(raw); if (value) identity.aliases.add(value); }
export function ownerTarget() { return (identity.config.ownerIds ?? []).find(x => x.startsWith('+')); }
export function awayText() {
  const cfg = config(), name = cfg.ownerName || 'the account owner';
  return cfg.awayText || `Hello, I'm Astra, ${name}'s AI assistant. ${name} is currently occupied and unable to respond immediately. Please leave your message for them to review when they are available. Thank you for your understanding.`;
}
export function requesterAllowed(ctx = {}, state) {
  if (ctx.requester?.channel === 'whatsapp') return trusted(ctx.requester.senderId);
  if (ctx.requester?.senderId || state?.access === 'public' || ctx.sessionKey?.includes(':whatsapp:')) return false;
  return state?.access === 'trusted' || ctx.sessionKey === 'agent:main:main' &&
    (!ctx.requester?.channel || ['webchat', 'cli', 'internal'].includes(ctx.requester.channel));
}
configure();

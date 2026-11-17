/** Builds the agent WebSocket URI from what the user typed. UI-only validation. */
export function parseAgentUri(input: string, token = ''): URL {
  let s = input.trim();
  if (s.length === 0) throw new Error('Enter the agent address');
  if (!s.includes('://')) s = `ws://${s}`;
  let u: URL;
  try {
    u = new URL(s);
  } catch {
    throw new Error('Enter a valid address');
  }
  if (u.protocol !== 'ws:' && u.protocol !== 'wss:') throw new Error('Use a ws:// address');
  if (!u.hostname) throw new Error('Missing host');
  const t = token.trim() !== '' ? token.trim() : u.searchParams.get('token') ?? '';
  if (t === '') throw new Error('Missing pairing token');
  const port = u.port !== '' ? u.port : '8765';
  return new URL(`ws${u.protocol === 'wss:' ? 's' : ''}://${u.hostname}:${port}/?token=${encodeURIComponent(t)}`);
}

export function agentIdFromUri(uri: URL): string {
  return `${uri.hostname}:${uri.port}`;
}

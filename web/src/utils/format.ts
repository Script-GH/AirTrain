import { type DeviceState } from '../types/models';

export const colors = {
  bg: '#0b0b0f',
  card: '#15151b',
  border: '#24242d',
  text: '#ededf0',
  muted: '#8a8a96',
  accent: '#7c6cff',
  green: '#3dd68c',
  amber: '#f5a524',
  red: '#f2555a',
} as const;

export function fmt(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`;
  return `${n}`;
}

export function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtDur(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m ${String(sec).padStart(2, '0')}s`;
}

export function stressLevel(s: number): { label: string; color: string } {
  if (s < 40) return { label: 'Low', color: colors.green };
  if (s < 65) return { label: 'Moderate', color: colors.accent };
  if (s < 85) return { label: 'High', color: colors.amber };
  return { label: 'Critical', color: colors.red };
}

export function stateColor(state: DeviceState): string {
  switch (state) {
    case 'training':
      return colors.green;
    case 'idle':
      return colors.muted;
    case 'busy':
      return colors.amber;
    case 'offline':
      return colors.red;
  }
}

export function stateLabel(state: DeviceState, paused: boolean): string {
  if (paused) return 'Paused';
  switch (state) {
    case 'training':
      return 'Training';
    case 'idle':
      return 'Idle';
    case 'busy':
      return 'In use';
    case 'offline':
      return 'Offline';
  }
}

export function pillColor(state: DeviceState, paused: boolean): string {
  if (paused) return colors.amber;
  return stateColor(state);
}

export function distinct(values: Array<string | undefined>, none: string): string {
  const set = [...new Set(values.filter((v): v is string => v != null && v !== ''))];
  return set.length === 0 ? none : set.join(', ');
}

export function deviceNoun(n: number): string {
  return n === 1 ? 'device' : 'devices';
}

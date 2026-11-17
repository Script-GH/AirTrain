import {
  type ClusterRef,
  type Device,
  type DeviceState,
  type Job,
  type RoundLog,
} from '../types/models';
import { type TelemetryCluster, type TelemetryMessage } from '../types/telemetry';

function n(v: unknown, fallback = 0): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fallback;
}

export function pushSample(list: number[], value: number, max = 40): number[] {
  const out = [...list, value];
  if (out.length > max) out.shift();
  return out;
}

export function locationFromTelemetry(t: TelemetryMessage): {
  city?: string;
  lat?: number;
  lon?: number;
} {
  const l = t.location;
  if (l == null) return {};
  const parts = [str(l.city), str(l.country)].filter((v): v is string => v != null);
  const lat = coord(l.lat, 90);
  const lon = coord(l.lon, 180);
  const hasPos = lat != null && lon != null;
  return {
    city: parts.length === 0 ? undefined : parts.join(', '),
    lat: hasPos ? lat : undefined,
    lon: hasPos ? lon : undefined,
  };
}

export function clusterFromTelemetry(t: TelemetryMessage): ClusterRef | undefined {
  const c = t.cluster;
  if (c == null || c.id == null) return undefined;
  return clusterFromBlock(c);
}

function clusterFromBlock(c: TelemetryCluster): ClusterRef {
  const lat = finite(c.lat);
  const lon = finite(c.lon);
  const hasPos = lat != null && lon != null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  return {
    id: String(c.id),
    name: c.name ?? String(c.id),
    region: typeof c.region === 'string' ? c.region : undefined,
    lat: hasPos ? lat : undefined,
    lon: hasPos ? lon : undefined,
    latencyMs: finite(c.latency_ms),
  };
}

function str(v: unknown): string | undefined {
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : undefined;
}

function coord(v: unknown, limit: number): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= limit ? v : undefined;
}

function finite(v: unknown): number | undefined {
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined;
}

export function deviceFromTelemetry(t: TelemetryMessage, linkId: string, prev?: Device): Device {
  const dev = t.device;
  const g = t.gpu;
  const c = t.cpu;
  const r = t.ram;
  const train = t.train;
  const limits = t.limits;
  const loc = locationFromTelemetry(t);
  const hasGpu = g.available === true;

  const util = hasGpu ? n(g.util) : n(c.util);
  const temp = hasGpu ? n(g.temp_c) : n(c.temp_c);
  const ramTotal = Math.max(n(r.total_gb, 1), 0.1);
  const ram = n(r.used_gb);
  const fan = g.fan_pct;
  const paused = t.paused === true;
  const state: DeviceState =
    t.state === 'training' ? 'training' : t.state === 'busy' ? 'busy' : 'idle';

  return {
    id: `agent:${dev.id ?? linkId}`,
    linkId,
    name: `${dev.name ?? linkId}`,
    gpu: hasGpu ? `${g.name} · CUDA` : `${c.name ?? 'CPU'} · CPU only`,
    icon: dev.kind === 'laptop' ? 'laptop' : 'desktop',
    vramTotal: hasGpu ? Math.max(n(g.vram_total_gb, 1), 0.1) : ramTotal,
    vramUsed: hasGpu ? n(g.vram_used_gb) : ram,
    state,
    paused,
    util,
    temp,
    tempLimit: n(g.temp_limit_c, n(limits.max_temp_c, 90)),
    power: n(g.power_w),
    powerLimit: Math.max(n(g.power_limit_w, 1), 1),
    ramTotal,
    ram,
    cpu: n(c.util),
    hasFan: typeof fan === 'number',
    fan: typeof fan === 'number' ? Math.round(fan) : 0,
    fanUnit: '%',
    cpuOnly: !hasGpu,
    clock: n(g.clock_mhz, n(c.freq_mhz)),
    throttled: g.throttled === true,
    samples: train == null ? 0 : Math.round(n(train.samples)),
    history: pushSample(prev?.history ?? [], util),
    tempHistory: pushSample(prev?.tempHistory ?? [], temp),
    city: loc.city,
    lat: loc.lat,
    lon: loc.lon,
    jobName: t.job?.name,
    cluster: clusterFromTelemetry(t),
  };
}

export function jobFromTelemetry(snaps: Iterable<TelemetryMessage>, startedAt: number): Job | undefined {
  let best: TelemetryMessage['train'] | undefined;
  for (const s of snaps) {
    const t = s.train;
    if (t != null && (best == null || n(t.round) > n(best.round))) best = t;
  }
  if (best == null) return undefined;
  const hist = best.history ?? [];
  const log: RoundLog[] = [...hist]
    .reverse()
    .map((h) => ({
      round: Math.round(n(h.round)),
      acc: n(h.accuracy),
      loss: n(h.loss),
      devices: 1,
      samples: Math.round(n(h.samples)),
    }));
  let throughput = 0;
  for (const s of snaps) throughput += n(s.train?.samples_per_s);
  return {
    round: Math.round(n(best.round)),
    totalRounds: Math.max(Math.round(n(best.total_rounds, 1)), 1),
    acc: hist.map((h) => n(h.accuracy)),
    loss: hist.map((h) => n(h.loss)),
    log,
    startedAt,
    throughput,
  };
}

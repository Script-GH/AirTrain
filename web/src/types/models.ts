export type DeviceState = 'training' | 'idle' | 'busy' | 'offline';

export type LinkStatus = 'connecting' | 'connected' | 'unauthorized' | 'error';

export type DeviceIcon = 'desktop' | 'laptop';

export interface ClusterRef {
  id: string;
  name: string;
  region?: string;
  /** Coordinator position; omitted when unknown. */
  lat?: number;
  lon?: number;
  latencyMs?: number;
}

export interface Device {
  id: string;
  name: string;
  gpu: string;
  icon: DeviceIcon;
  vramTotal: number;
  state: DeviceState;
  paused: boolean;
  util: number;
  vramUsed: number;
  temp: number;
  power: number;
  history: number[];
  samples: number;
  tempLimit: number;
  powerLimit: number;
  ramTotal: number;
  hasFan: boolean;
  cpu: number;
  ram: number;
  fan: number;
  clock: number;
  throttled: boolean;
  tempHistory: number[];
  /** "City, CC" as reported by the agent; undefined when unknown. */
  city?: string;
  lat?: number;
  lon?: number;
  /** Set for devices reported by a paired PC agent; undefined for demo devices. */
  linkId?: string;
  fanUnit: string;
  /** No supported GPU: util/VRAM fields carry CPU load and system RAM instead. */
  cpuOnly: boolean;
  jobName?: string;
  cluster?: ClusterRef;
}

export interface RoundLog {
  round: number;
  acc: number;
  loss: number;
  devices: number;
  samples: number;
}

export interface Job {
  round: number;
  totalRounds: number;
  acc: number[];
  loss: number[];
  /** Newest first. */
  log: RoundLog[];
  startedAt: number;
  throughput: number;
}

export interface AgentInfo {
  id: string;
  url: string;
  status: LinkStatus;
  error?: string;
}

export interface SwarmState {
  devices: Device[];
  job: Job;
  agents: AgentInfo[];
}

export function unitLabel(d: Device): string {
  return d.cpuOnly ? 'CPU' : 'GPU';
}

export function memLabel(d: Device): string {
  return d.cpuOnly ? 'RAM' : 'VRAM';
}

export function tempText(d: Device): string {
  return d.linkId != null && d.temp === 0 ? '—' : `${d.temp.toFixed(0)}°C`;
}

export function powerText(d: Device): string {
  return d.linkId != null && d.power === 0 ? '—' : `${d.power.toFixed(0)}W`;
}

/** 0-100 composite load score from GPU load, heat, power draw and memory pressure. */
export function stress(d: Device): number {
  const t = clamp((d.temp - 35) / (d.tempLimit - 35), 0, 1) * 100;
  const p = clamp(d.power / d.powerLimit, 0, 1) * 100;
  const m = clamp(d.vramUsed / d.vramTotal, 0, 1) * 100;
  return clamp(0.35 * d.util + 0.35 * t + 0.2 * p + 0.1 * m, 0, 100);
}

export function headroom(d: Device): number {
  return d.tempLimit - d.temp;
}

export function isActive(d: Device): boolean {
  return d.state === 'training' && !d.paused;
}

export function jobAccuracy(job: Job): number {
  return job.acc.length === 0 ? 0 : job.acc[job.acc.length - 1]!;
}

export function jobBestAccuracy(job: Job): number {
  return job.acc.length === 0 ? 0 : Math.max(...job.acc);
}

export function jobLoss(job: Job): number {
  return job.loss.length === 0 ? 0 : job.loss[job.loss.length - 1]!;
}

export function jobProgress(job: Job): number {
  return job.round / job.totalRounds;
}

export function agentDevices(devices: Device[]): Device[] {
  return devices.filter((d) => d.linkId != null);
}

export function activeCount(devices: Device[]): number {
  return agentDevices(devices).filter(isActive).length;
}

export function connectedCount(devices: Device[]): number {
  return agentDevices(devices).filter((d) => d.state !== 'offline').length;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

export interface NetNode {
  name: string;
  detail: string;
  state: DeviceState;
  city?: string;
  lat?: number;
  lon?: number;
  jobName?: string;
  cluster?: ClusterRef;
}

export function netNodeOf(d: Device): NetNode {
  return {
    name: d.name,
    detail: d.gpu,
    state: d.paused && d.state !== 'offline' ? 'idle' : d.state,
    city: d.city,
    lat: d.lat,
    lon: d.lon,
    jobName: d.jobName,
    cluster: d.cluster,
  };
}

export function onMap(n: NetNode): boolean {
  return n.lat != null && n.lon != null;
}

export function isLinked(n: NetNode): boolean {
  return n.cluster?.lat != null && n.cluster.lon != null;
}

/** Agent WebSocket and telemetry types, matching the v1 schema in agent/README.md. */

export type TelemetryType = 'hello' | 'telemetry' | 'ack';

export type DeviceKind = 'desktop' | 'laptop';

export type DeviceRunState = 'training' | 'idle' | 'busy';

export type TrainStatus =
  | 'starting'
  | 'loading'
  | 'waiting'
  | 'running'
  | 'done'
  | 'error'
  | 'stopped';

export type LocationSource = 'config' | 'ip';

export type ThrottleReason =
  | 'gpu_idle'
  | 'app_clock_setting'
  | 'sw_power_cap'
  | 'hw_slowdown'
  | 'sync_boost'
  | 'sw_thermal'
  | 'hw_thermal'
  | 'hw_power_brake'
  | 'display_clock';

export interface HelloMessage {
  type: 'hello';
  v: 1;
  device_id: string;
}

export interface AckMessage {
  type: 'ack';
  cmd: string;
  ok: boolean;
  paused?: boolean;
}

export interface AgentCommand {
  cmd: 'pause' | 'resume' | 'snapshot' | 'ping';
}

export interface TelemetryDevice {
  id: string;
  name: string;
  hostname: string;
  os: string;
  platform: string;
  kind: DeviceKind;
}

export interface GpuProcess {
  pid: number;
  kind: string;
  mem_gb: number;
}

export interface TelemetryGpu {
  available: boolean;
  reason?: string;
  vendor?: string;
  name?: string;
  driver?: string;
  util?: number | null;
  vram_used_gb?: number | null;
  vram_total_gb?: number | null;
  temp_c?: number | null;
  temp_limit_c?: number | null;
  temp_shutdown_c?: number | null;
  power_w?: number | null;
  power_limit_w?: number | null;
  fan_pct?: number | null;
  clock_mhz?: number | null;
  clock_max_mhz?: number | null;
  throttle_reasons?: ThrottleReason[];
  throttled?: boolean;
  processes?: GpuProcess[];
}

export interface TelemetryCpu {
  name: string;
  util: number;
  cores: number;
  freq_mhz: number | null;
  temp_c: number | null;
}

export interface TelemetryRam {
  used_gb: number;
  total_gb: number;
}

export interface TelemetryBattery {
  present: boolean;
  percent: number | null;
  plugged: boolean | null;
}

export interface TelemetryIdle {
  user_idle_s: number;
  method: string;
  idle: boolean;
  eligible: boolean;
  reasons: string[];
}

export interface TelemetryLocation {
  city: string | null;
  country: string | null;
  lat: number | null;
  lon: number | null;
  source: LocationSource;
}

export interface TelemetryLimits {
  max_temp_c: number;
  idle_minutes: number;
  min_battery_pct: number;
}

export interface TelemetryJob {
  id: string;
  name: string;
  batch_size: number;
}

export interface TelemetryCluster {
  id: string;
  name: string;
  region: string | null;
  city: string | null;
  devices: number | null;
  latency_ms: number | null;
  coordinator: string | null;
  lat: number | null;
  lon: number | null;
}

export interface TrainHistoryEntry {
  round: number;
  loss: number;
  accuracy: number;
  samples: number;
}

export interface TelemetryTrain {
  status: TrainStatus;
  round: number;
  total_rounds: number;
  step: number;
  steps_per_round: number;
  loss: number;
  accuracy: number;
  samples: number;
  samples_per_s: number;
  device: string;
  job: string;
  batch_size: number;
  dataset: string;
  history: TrainHistoryEntry[];
  error: string | null;
}

export interface TelemetryMessage {
  type: 'telemetry';
  v: 1;
  ts: number;
  device: TelemetryDevice;
  gpu: TelemetryGpu;
  cpu: TelemetryCpu;
  ram: TelemetryRam;
  battery: TelemetryBattery;
  idle: TelemetryIdle;
  blockers: string[];
  state: DeviceRunState;
  paused: boolean;
  uptime_s: number;
  location: TelemetryLocation | null;
  limits: TelemetryLimits;
  job: TelemetryJob | null;
  cluster: TelemetryCluster | null;
  train: TelemetryTrain | null;
}

export type AgentMessage = HelloMessage | TelemetryMessage | AckMessage;

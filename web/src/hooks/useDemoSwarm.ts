import { useCallback, useEffect, useRef, useState } from 'react';
import { demoDevices, demoJob, mockAgentTelemetry } from '../data/mock';
import {
  type AgentInfo,
  type Device,
  type Job,
  type RoundLog,
  type SwarmState,
  isActive,
} from '../types/models';
import { deviceFromTelemetry, pushSample } from '../utils/mapTelemetry';
import { agentIdFromUri, parseAgentUri } from '../utils/parseAgentUri';

function initialAgents(): Device[] {
  return mockAgentTelemetry.map((t) => {
    const linkId = `${t.device.hostname}:8765`;
    let prev: Device | undefined;
    // Prefill sparkline history with a short run of the current util/temp.
    for (let k = 0; k < 24; k++) prev = deviceFromTelemetry(t, linkId, prev);
    return prev!;
  });
}

export function useDemoSwarm(): {
  demo: SwarmState;
  agents: SwarmState;
  now: number;
  paired: AgentInfo[];
  togglePause: (id: string) => void;
  pairAgent: (url: string, token: string) => void;
  removeAgent: (id: string) => void;
} {
  const [demo, setDemo] = useState<SwarmState>(() => ({
    devices: demoDevices(),
    job: demoJob(),
    agents: [],
  }));
  const [agentDevices, setAgentDevices] = useState<Device[]>(initialAgents);
  const [paired, setPaired] = useState<AgentInfo[]>([]);
  const [now, setNow] = useState(() => Date.now());
  const tick = useRef(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      tick.current += 1;
      setNow(Date.now());
      setDemo((s) => advanceDemo(s, tick.current));
      setAgentDevices((devs) => devs.map(nudgeAgent));
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const togglePause = useCallback((id: string) => {
    const flip = (list: Device[]) => list.map((d) => (d.id === id ? { ...d, paused: !d.paused } : d));
    setDemo((s) => ({ ...s, devices: flip(s.devices) }));
    setAgentDevices(flip);
  }, []);

  const pairAgent = useCallback((url: string, token: string) => {
    const uri = parseAgentUri(url, token);
    const id = agentIdFromUri(uri);
    setPaired((list) => {
      const next = list.filter((a) => a.id !== id);
      next.push({ id, url: `${uri.hostname}:${uri.port}`, status: 'connected' });
      return next;
    });
  }, []);

  const removeAgent = useCallback((id: string) => {
    setPaired((list) => list.filter((a) => a.id !== id));
  }, []);

  const agents: SwarmState = {
    devices: agentDevices,
    job: demo.job,
    agents: paired,
  };

  return { demo, agents, now, paired, togglePause, pairAgent, removeAgent };
}

function advanceDemo(state: SwarmState, step: number): SwarmState {
  const devices = state.devices.map((d) => {
    const active = isActive(d);
    const target = active ? 88 + rand() * 10 : 2 + rand() * 4;
    const util = d.util + (target - d.util) * 0.5;
    const hotTarget = d.hasFan ? 72 : 84;
    const temp = d.temp + ((active ? hotTarget : 42) - d.temp) * 0.1 + rand() - 0.5;
    const throttled = temp > d.tempLimit - 3;
    const baseClock = d.hasFan ? 1950 : 1400;
    return {
      ...d,
      cpu: active ? 35 + rand() * 20 : 4 + rand() * 6,
      ram: d.ramTotal * (active ? 0.68 : 0.42) + rand() * 0.2,
      fan: d.hasFan ? (active ? 1700 + Math.round((temp - 40) * 25) + irand(80) : 900 + irand(60)) : 0,
      clock: active ? baseClock * (throttled ? 0.82 : 1) - rand() * 30 : 300 + rand() * 40,
      throttled: active && throttled,
      tempHistory: pushSample(d.tempHistory, temp),
      util,
      temp,
      vramUsed: d.vramTotal * (active ? 0.62 : 0.08),
      power: active ? (d.id === 'pc' ? 160 : 18) * (util / 100) + 5 : 5 + rand() * 2,
      history: pushSample(d.history, util),
      samples: d.samples + (active ? (d.id === 'pc' ? 1800 : 600) : 0),
    };
  });

  const prevTotal = state.devices.reduce((a, d) => a + d.samples, 0);
  const total = devices.reduce((a, d) => a + d.samples, 0);
  let job: Job = { ...state.job, throughput: total - prevTotal };
  if (devices.some(isActive) && step % 4 === 0 && job.round < job.totalRounds) {
    const r = job.round + 1;
    const a = 0.86 * (1 - Math.exp(-r / 10)) + (rand() - 0.5) * 0.01;
    const l = 2.3 * Math.exp(-r / 12) + 0.35 + (rand() - 0.5) * 0.04;
    const n = devices.filter(isActive).length;
    const entry: RoundLog = { round: r, acc: a, loss: l, devices: n, samples: total };
    job = { ...job, round: r, acc: [...job.acc, a], loss: [...job.loss, l], log: [entry, ...job.log] };
  }
  return { ...state, devices, job };
}

function nudgeAgent(d: Device): Device {
  const active = isActive(d);
  const target = active ? d.util : Math.max(2, d.util * 0.4);
  const util = d.util + (target + (rand() - 0.5) * 4 - d.util) * 0.35;
  const temp = d.temp + (rand() - 0.5) * 0.6;
  return {
    ...d,
    util,
    temp,
    cpu: Math.max(1, d.cpu + (rand() - 0.5) * 3),
    history: pushSample(d.history, util),
    tempHistory: pushSample(d.tempHistory, temp),
    samples: d.samples + (active ? 800 : 0),
  };
}

function rand(): number {
  return Math.random();
}

function irand(n: number): number {
  return Math.floor(Math.random() * n);
}

import { useMemo, useState } from 'react';
import { DottedMap, allInIndia } from '../components/DottedMap';
import { EmptyState } from '../components/EmptyState';
import { MapToggle } from '../components/MapToggle';
import { indiaMap, worldMap } from '../data/mapMasks';
import { isLinked, netNodeOf, onMap, type Device, type NetNode } from '../types/models';
import { colors, deviceNoun, distinct, stateColor } from '../utils/format';

export function NetworkTab({ devices, waiting, onPair }: { devices: Device[]; waiting: boolean; onPair: () => void }) {
  const nodes = useMemo(() => devices.map(netNodeOf), [devices]);
  const [indiaOverride, setIndiaOverride] = useState<boolean | undefined>();
  const autoIndia = allInIndia(indiaMap, nodes);
  const india = indiaOverride ?? autoIndia;
  const region = india ? indiaMap : worldMap;

  const online = nodes.filter((n) => n.state !== 'offline');
  const training = nodes.filter((n) => n.state === 'training').length;
  const latencies = online.map((n) => n.cluster?.latencyMs).filter((v): v is number => v != null);
  const avgLatency = latencies.length === 0 ? undefined : latencies.reduce((a, b) => a + b, 0) / latencies.length;
  const countries = new Set(online.map((n) => n.city?.split(', ').at(-1)).filter((v): v is string => v != null));
  const clusters = new Set(nodes.map((n) => n.cluster?.id).filter((v): v is string => v != null));
  const unmapped = nodes.filter((n) => !onMap(n)).length;
  const sorted = [...nodes].sort((a, b) => stateRank(a.state) - stateRank(b.state));

  return (
    <div className="page">
      <h1>Network</h1>
      <p className="subtitle">Devices running the AirTrain CLI</p>
      {nodes.length === 0 ? (
        <EmptyState waiting={waiting} onPair={onPair} />
      ) : (
        <div className="card net-stats">
          <div className="net-stats-row">
            <div className="net-hero">
              <div className="net-hero-n">{training}</div>
              <div className="muted small">{`${deviceNoun(training)} training now`}</div>
            </div>
            <div className="net-side">
              <NetStat label="Connected" value={`${online.length} / ${nodes.length}`} />
              <NetStat label="Clusters" value={`${clusters.size}`} />
              <NetStat label="Countries" value={`${countries.size}`} />
              <NetStat label="Latency" value={avgLatency == null ? '—' : `${Math.round(avgLatency)} ms`} />
            </div>
          </div>
          <div className="divider" />
          <InfoLine label="Job" value={distinct(nodes.map((n) => n.jobName), 'None picked')} />
          <InfoLine
            label="Cluster"
            value={distinct(
              nodes.map((n) => (n.cluster == null ? undefined : `${n.cluster.name} · ${n.cluster.region ?? '?'}`)),
              'Not connected',
            )}
          />
        </div>
      )}
      <div className="card map-card">
        <div className="map-card-head">
          <div className="map-card-title">Device map</div>
          <MapToggle
            labels={['World', 'India']}
            index={india ? 1 : 0}
            onChange={(i) => setIndiaOverride(i === 1)}
          />
        </div>
        <DottedMap region={region} nodes={nodes} />
        <div className="map-legend">
          {nodes.some(isLinked) && <Legend color={colors.accent} label="Coordinator" />}
          <Legend color={colors.green} label="Training" />
          <Legend color={colors.muted} label="Idle" />
          <Legend color={colors.amber} label="Busy" />
          <Legend color={colors.red} label="Offline" />
        </div>
        {unmapped > 0 && (
          <p className="map-note">
            {`${unmapped} ${unmapped === 1 ? 'device has' : 'devices have'} no location. Set one with: airtrain config --set location="City, CC"`}
          </p>
        )}
      </div>
      {nodes.length > 0 && (
        <>
          <div className="section-label">NODES</div>
          <div className="card node-list">
            {sorted.map((n) => (
              <NodeRow key={`${n.name}-${n.city ?? ''}`} node={n} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function NetStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="net-stat">
      <span className="muted small">{label}</span>
      <span className="net-stat-v tabular">{value}</span>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="info-line">
      <span className="info-k">{label}</span>
      <span className="info-v">{value}</span>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="legend">
      <span className="legend-dot" style={{ background: color }} />
      {label}
    </span>
  );
}

function NodeRow({ node: n }: { node: NetNode }) {
  const color = stateColor(n.state);
  const offline = n.state === 'offline';
  const latency = n.cluster?.latencyMs;
  return (
    <div className="node-row">
      <span className="node-dot" style={{ background: color }} />
      <div className="node-body">
        <div className="node-name">{n.name}</div>
        <div className="node-detail">{`${n.city ?? 'Location unknown'} · ${n.detail}`}</div>
        <div className="node-job" style={{ color: n.cluster == null ? 'var(--muted)' : 'var(--accent)' }}>
          {`${n.jobName ?? 'No job picked'} · ${n.cluster?.name ?? 'No cluster'}`}
        </div>
      </div>
      <div className={`node-lat tabular${offline ? ' offline' : ''}`}>
        {offline ? 'offline' : latency == null ? '—' : `${Math.round(latency)} ms`}
      </div>
    </div>
  );
}

function stateRank(s: NetNode['state']): number {
  return { training: 0, idle: 1, busy: 2, offline: 3 }[s];
}

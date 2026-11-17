import { DeviceList } from '../components/DeviceList';
import { JobCard } from '../components/JobCard';
import { StatusPill } from '../components/StatusPill';
import { IconLink } from '../icons';
import { type SwarmState, isActive } from '../types/models';
import { colors } from '../utils/format';

export function OverviewTab({
  swarm,
  live,
  onPair,
  onTogglePause,
}: {
  swarm: SwarmState;
  live: boolean;
  onPair: () => void;
  onTogglePause: (id: string) => void;
}) {
  const online = swarm.devices.filter((d) => d.state !== 'offline').length;
  const active = swarm.devices.filter(isActive).length;
  const total = swarm.devices.reduce((a, d) => a + d.samples, 0);

  return (
    <div className="page">
      <div className="page-head">
        <div className="grow">
          <h1>AirTrain</h1>
          <p className="subtitle">Idle compute, put to work</p>
        </div>
        <StatusPill
          label={live ? `${online} online` : 'Demo data'}
          color={live ? colors.green : colors.amber}
        />
        <button type="button" className="icon-btn filled" aria-label="Pair a PC agent" onClick={onPair}>
          <IconLink size={20} />
        </button>
      </div>
      <JobCard job={swarm.job} totalSamples={total} activeDevices={active} />
      <DeviceList devices={swarm.devices} onTogglePause={onTogglePause} />
    </div>
  );
}

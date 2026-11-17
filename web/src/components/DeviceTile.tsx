import {
  type Device,
  memLabel,
  powerText,
  tempText,
  unitLabel,
} from '../types/models';
import { pillColor, stateLabel } from '../utils/format';
import { DeviceIconView } from '../icons';
import { Sparkline } from './Sparkline';
import { Stat } from './Stat';
import { StatusPill } from './StatusPill';
import { IconPause, IconPlay } from '../icons';

export function DeviceTile({
  device,
  share,
  onTogglePause,
}: {
  device: Device;
  share: number;
  onTogglePause?: (id: string) => void;
}) {
  const d = device;
  const color = pillColor(d.state, d.paused);
  const label = stateLabel(d.state, d.paused);

  return (
    <div className="card device-tile">
      <div className="device-tile-head">
        <div className="device-icon">
          <DeviceIconView name={d.icon} />
        </div>
        <div className="device-tile-titles">
          <div className="device-tile-name">{d.name}</div>
          <div className="device-tile-gpu">{d.gpu}</div>
        </div>
        <StatusPill label={label} color={color} />
      </div>
      <Sparkline data={d.history} max={100} color={color} height={44} />
      <div className="stat-row">
        <Stat label={unitLabel(d)} value={`${d.util.toFixed(0)}%`} />
        <Stat label={memLabel(d)} value={`${d.vramUsed.toFixed(1)}/${d.vramTotal.toFixed(0)}G`} />
        <Stat label="Temp" value={tempText(d)} />
        <Stat label="Power" value={powerText(d)} />
      </div>
      <div className="device-tile-foot">
        <span className="muted tabular">{`${(share * 100).toFixed(0)}% of work`}</span>
        <button type="button" className="btn-quiet" onClick={() => onTogglePause?.(d.id)}>
          {d.paused ? <IconPlay size={18} /> : <IconPause size={18} />}
          {d.paused ? 'Resume' : 'Pause'}
        </button>
      </div>
    </div>
  );
}

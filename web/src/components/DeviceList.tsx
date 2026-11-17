import { type Device } from '../types/models';
import { DeviceTile } from './DeviceTile';

export function DeviceList({
  devices,
  onTogglePause,
}: {
  devices: Device[];
  onTogglePause?: (id: string) => void;
}) {
  const total = devices.reduce((a, d) => a + d.samples, 0);
  return (
    <div className="device-list">
      <div className="section-label">DEVICES</div>
      {devices.map((d) => (
        <DeviceTile
          key={d.id}
          device={d}
          share={total === 0 ? 0 : d.samples / total}
          onTogglePause={onTogglePause}
        />
      ))}
    </div>
  );
}

import { HealthPanel } from '../components/HealthPanel';
import { type Device } from '../types/models';

export function HealthTab({ devices }: { devices: Device[] }) {
  return (
    <div className="page">
      <h1>Device health</h1>
      <p className="subtitle">How hard each device is working</p>
      {devices.map((d) => (
        <HealthPanel key={d.id} device={d} />
      ))}
    </div>
  );
}

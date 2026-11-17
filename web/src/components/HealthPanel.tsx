import { type Device, headroom, powerText, stress, tempText } from '../types/models';
import { colors, stressLevel } from '../utils/format';
import { DeviceIconView } from '../icons';
import { LoadBar } from './LoadBar';
import { Sparkline } from './Sparkline';
import { Stat } from './Stat';
import { StatusPill } from './StatusPill';
import { StressGauge } from './StressGauge';

export function HealthPanel({ device }: { device: Device }) {
  const d = device;
  const level = stressLevel(stress(d));
  const hr = headroom(d);
  const tempColor = hr < 5 ? colors.red : hr < 15 ? colors.amber : colors.green;
  const tText = tempText(d);

  return (
    <div className="card health-panel">
      <div className="health-head">
        <DeviceIconView name={d.icon} size={20} />
        <div className="health-name">{d.name}</div>
        {d.throttled && <StatusPill label="Throttling" color={colors.red} />}
        <StatusPill label={level.label} color={level.color} />
      </div>
      <div className="health-body">
        <StressGauge value={stress(d)} color={level.color} />
        <div className="health-bars">
          {!d.cpuOnly && <LoadBar label="GPU" value={d.util / 100} text={`${d.util.toFixed(0)}%`} />}
          <LoadBar label="CPU" value={d.cpu / 100} text={`${d.cpu.toFixed(0)}%`} />
          {!d.cpuOnly && (
            <LoadBar
              label="VRAM"
              value={d.vramUsed / d.vramTotal}
              text={`${d.vramUsed.toFixed(1)}/${d.vramTotal.toFixed(0)}G`}
            />
          )}
          <LoadBar
            label="RAM"
            value={d.ram / d.ramTotal}
            text={`${d.ram.toFixed(1)}/${d.ramTotal.toFixed(0)}G`}
          />
          {powerText(d) !== '—' && (
            <LoadBar
              label="Power"
              value={d.power / d.powerLimit}
              text={`${d.power.toFixed(0)}/${d.powerLimit.toFixed(0)}W`}
            />
          )}
        </div>
      </div>
      <div className="health-temp-row">
        <span className="muted small">Temperature</span>
        <span className="spacer" />
        <span className="tabular" style={{ color: tempColor, fontWeight: 600 }}>
          {tText}
        </span>
        <span className="muted small">{`  /  limit ${d.tempLimit.toFixed(0)}°C`}</span>
      </div>
      <Sparkline data={d.tempHistory} max={d.tempLimit + 5} color={tempColor} height={56} />
      <div className="stat-row health-stats">
        <Stat label="Headroom" value={tText === '—' ? '—' : `${hr.toFixed(0)}°C`} />
        <Stat label="Clock" value={`${d.clock.toFixed(0)} MHz`} />
        <Stat
          label="Fan"
          value={d.hasFan ? `${d.fan} ${d.fanUnit}` : d.linkId != null ? 'n/a' : 'Fanless'}
        />
      </div>
    </div>
  );
}

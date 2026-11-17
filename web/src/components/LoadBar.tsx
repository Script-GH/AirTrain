import { colors } from '../utils/format';

export function LoadBar({ label, value, text }: { label: string; value: number; text: string }) {
  const v = Math.min(1, Math.max(0, value));
  const color = v > 0.9 ? colors.red : v > 0.75 ? colors.amber : colors.accent;
  return (
    <div className="loadbar">
      <span className="loadbar-label">{label}</span>
      <div className="loadbar-track">
        <div className="loadbar-fill" style={{ width: `${v * 100}%`, background: color }} />
      </div>
      <span className="loadbar-text">{text}</span>
    </div>
  );
}

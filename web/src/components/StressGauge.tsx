/** Semicircular stress gauge. Start 135deg, sweep 270deg, matching the Flutter painter. */
export function StressGauge({
  value,
  color,
  label = 'stress',
}: {
  value: number;
  color: string;
  label?: string;
}) {
  const width = 120;
  const height = 100;
  const r = Math.min(width, height * 1.2) / 2 - 6;
  const cx = width / 2;
  const cy = r + 6;
  const t = clamp(value / 100, 0, 1);
  const start = Math.PI * 0.75;
  const sweep = Math.PI * 1.5;

  return (
    <div className="gauge" style={{ width, height }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <path d={arcPath(cx, cy, r, start, sweep)} fill="none" stroke="var(--border)" strokeWidth="9" strokeLinecap="round" />
        {t > 0 && (
          <path
            d={arcPath(cx, cy, r, start, sweep * t)}
            fill="none"
            stroke={color}
            strokeWidth="9"
            strokeLinecap="round"
          />
        )}
      </svg>
      <div className="gauge-label">
        <div className="gauge-value">{value.toFixed(0)}</div>
        <div className="gauge-caption">{label}</div>
      </div>
    </div>
  );
}

function arcPath(cx: number, cy: number, r: number, start: number, sweep: number): string {
  const x0 = cx + r * Math.cos(start);
  const y0 = cy + r * Math.sin(start);
  const x1 = cx + r * Math.cos(start + sweep);
  const y1 = cy + r * Math.sin(start + sweep);
  const large = sweep > Math.PI ? 1 : 0;
  return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

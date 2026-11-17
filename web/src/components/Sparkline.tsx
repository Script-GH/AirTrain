export function Sparkline({
  data,
  max,
  color,
  height = 48,
}: {
  data: number[];
  max: number;
  color: string;
  height?: number;
}) {
  const w = 400;
  const h = height;
  if (data.length < 2) {
    return <div className="sparkline" style={{ height }} />;
  }
  const dx = w / (data.length - 1);
  const points = data.map((v, i) => {
    const x = i * dx;
    const y = h - clamp(v / max, 0, 1) * h;
    return `${x},${y}`;
  });
  const line = `M ${points.join(' L ')}`;
  const last = points[points.length - 1]!;
  const fill = `${line} L ${w},${h} L 0,${h} Z`;
  const id = `spark-${color.replace('#', '')}-${height}`;

  return (
    <svg className="sparkline" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height }}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fill} fill={`url(#${id})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <title>{last}</title>
    </svg>
  );
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

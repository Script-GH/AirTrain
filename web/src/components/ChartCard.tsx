import { Sparkline } from './Sparkline';

export function ChartCard({
  title,
  value,
  data,
  max,
  color,
}: {
  title: string;
  value: string;
  data: number[];
  max: number;
  color: string;
}) {
  return (
    <div className="card chart-card">
      <div className="chart-card-head">
        <div className="chart-card-title">{title}</div>
        <div className="tabular" style={{ color, fontWeight: 600 }}>
          {value}
        </div>
      </div>
      <Sparkline data={data} max={max} color={color} height={110} />
    </div>
  );
}

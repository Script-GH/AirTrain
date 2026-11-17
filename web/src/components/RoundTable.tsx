import { type RoundLog } from '../types/models';
import { pct } from '../utils/format';

export function RoundTable({ rows }: { rows: RoundLog[] }) {
  return (
    <div className="card round-table">
      {rows.length === 0 ? (
        <div className="round-empty">Waiting for first round</div>
      ) : (
        <>
          <RoundRow cells={['Round', 'Accuracy', 'Loss', 'Devices']} header />
          {rows.slice(0, 8).map((r) => (
            <RoundRow
              key={r.round}
              cells={[`#${r.round}`, pct(r.acc), r.loss.toFixed(3), `${r.devices}`]}
            />
          ))}
        </>
      )}
    </div>
  );
}

function RoundRow({ cells, header = false }: { cells: string[]; header?: boolean }) {
  return (
    <div className={header ? 'round-row header' : 'round-row'}>
      <span style={{ width: 56 }}>{cells[0]}</span>
      <span className="grow">{cells[1]}</span>
      <span className="grow">{cells[2]}</span>
      <span style={{ width: 56, textAlign: 'right' }}>{cells[3]}</span>
    </div>
  );
}

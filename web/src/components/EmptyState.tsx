import { IconLink } from '../icons';

const STEPS = ['airtrain analysis', 'airtrain connect', 'airtrain start training'];

export function EmptyState({
  waiting = false,
  onPair,
}: {
  waiting?: boolean;
  onPair?: () => void;
}) {
  return (
    <div className="card empty-state">
      <div className="empty-title">{waiting ? 'Waiting for your agents' : 'No devices yet'}</div>
      <p className="empty-copy">
        {waiting
          ? 'Paired agents appear here once they report in. Make sure each one is running:'
          : 'Only PCs running the AirTrain CLI show up here. Install it on a Windows or Linux PC and run:'}
      </p>
      <div className="empty-steps">
        {STEPS.map((step, i) => (
          <div className="empty-step" key={step}>
            <span className="empty-num tabular">{i + 1}</span>
            <code>{step}</code>
          </div>
        ))}
      </div>
      <button type="button" className="btn-accent" onClick={onPair}>
        <IconLink size={18} />
        Pair device
      </button>
    </div>
  );
}

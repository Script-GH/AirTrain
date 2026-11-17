import { ChartCard } from '../components/ChartCard';
import { KvRow } from '../components/KvRow';
import { ProgressRing } from '../components/ProgressRing';
import { RoundTable } from '../components/RoundTable';
import { StatCard } from '../components/StatCard';
import { type SwarmState, isActive, jobAccuracy, jobBestAccuracy, jobLoss, jobProgress } from '../types/models';
import { colors, fmt, fmtDur, pct } from '../utils/format';

export function TrainingTab({ swarm, now }: { swarm: SwarmState; now: number }) {
  const job = swarm.job;
  const elapsed = now - job.startedAt;
  const done = job.round >= job.totalRounds;
  const eta = job.round === 0 ? undefined : elapsed * ((job.totalRounds - job.round) / job.round);
  const training = swarm.devices.filter(isActive).length;
  const connected = swarm.devices.filter((d) => d.state !== 'offline').length;

  return (
    <div className="page">
      <h1>Training</h1>
      <p className="subtitle">CIFAR-10 CNN · FedAvg</p>
      <div className="card training-hero">
        <ProgressRing progress={jobProgress(job)} done={done} />
        <div className="training-kvs">
          <KvRow label="Round" value={`${job.round} / ${job.totalRounds}`} />
          <KvRow label="Elapsed" value={fmtDur(elapsed)} />
          <KvRow label="ETA" value={done ? 'Complete' : eta == null ? '--' : fmtDur(eta)} />
        </div>
      </div>
      <div className="metric-grid">
        <StatCard label="Accuracy" value={pct(jobAccuracy(job))} />
        <StatCard label="Best" value={pct(jobBestAccuracy(job))} />
        <StatCard label="Loss" value={jobLoss(job).toFixed(3)} />
        <StatCard label="Throughput" value={`${fmt(Math.round(job.throughput))}/s`} />
        <StatCard label="Devices training" value={`${training}`} />
        <StatCard label="Connected" value={`${connected} / ${swarm.devices.length}`} />
      </div>
      <ChartCard title="Accuracy" value={pct(jobAccuracy(job))} data={job.acc} max={1} color={colors.accent} />
      <ChartCard title="Loss" value={jobLoss(job).toFixed(3)} data={job.loss} max={2.7} color={colors.amber} />
      <div className="section-label">RECENT ROUNDS</div>
      <RoundTable rows={job.log} />
    </div>
  );
}

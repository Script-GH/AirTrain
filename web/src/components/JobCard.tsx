import { type Job, jobAccuracy, jobProgress } from '../types/models';
import { colors, deviceNoun, fmt, pct } from '../utils/format';
import { Sparkline } from './Sparkline';
import { Stat } from './Stat';

export function JobCard({
  job,
  totalSamples,
  activeDevices,
}: {
  job: Job;
  totalSamples: number;
  activeDevices: number;
}) {
  return (
    <div className="card job-card">
      <div className="job-card-head">
        <div className="job-card-title">CIFAR-10 CNN</div>
        <div className="muted tabular">{`Round ${job.round}/${job.totalRounds}`}</div>
      </div>
      <div className="job-card-metric">
        <span className="job-acc">{pct(jobAccuracy(job))}</span>
        <span className="job-acc-label">accuracy</span>
      </div>
      <Sparkline data={job.acc} max={1} color={colors.accent} height={56} />
      <div className="progress-line">
        <div className="progress-line-fill" style={{ width: `${jobProgress(job) * 100}%` }} />
      </div>
      <div className="stat-row">
        <Stat label="Samples" value={fmt(totalSamples)} />
        <Stat label="Training on" value={`${activeDevices} ${deviceNoun(activeDevices)}`} />
      </div>
    </div>
  );
}

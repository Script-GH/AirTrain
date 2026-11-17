import { useEffect, useState } from 'react';
import { AppShell } from './components/AppShell';
import { PairingSheet } from './components/PairingSheet';
import { type TabId } from './components/TabBar';
import { useDemoSwarm } from './hooks/useDemoSwarm';
import { HealthTab } from './tabs/HealthTab';
import { NetworkTab } from './tabs/NetworkTab';
import { OverviewTab } from './tabs/OverviewTab';
import { TrainingTab } from './tabs/TrainingTab';

const TABS: TabId[] = ['overview', 'training', 'health', 'network'];

function tabFromQuery(): TabId {
  const q = new URLSearchParams(window.location.search).get('tab');
  return TABS.includes(q as TabId) ? (q as TabId) : 'overview';
}

export default function App() {
  const { demo, agents, now, paired, togglePause, pairAgent, removeAgent } = useDemoSwarm();
  const [tab, setTab] = useState<TabId>(tabFromQuery);
  const [pairOpen, setPairOpen] = useState(false);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tab);
    window.history.replaceState(null, '', url);
  }, [tab]);

  return (
    <AppShell tab={tab} onChange={setTab}>
      {tab === 'overview' && (
        <OverviewTab swarm={demo} live={false} onPair={() => setPairOpen(true)} onTogglePause={togglePause} />
      )}
      {tab === 'training' && <TrainingTab swarm={demo} now={now} />}
      {tab === 'health' && <HealthTab devices={demo.devices} />}
      {tab === 'network' && (
        <NetworkTab devices={agents.devices} waiting={paired.length > 0} onPair={() => setPairOpen(true)} />
      )}
      <PairingSheet
        open={pairOpen}
        agents={paired}
        onClose={() => setPairOpen(false)}
        onConnect={pairAgent}
        onRemove={removeAgent}
      />
    </AppShell>
  );
}

import { type ReactNode } from 'react';
import { TabBar, type TabId } from './TabBar';

export function AppShell({
  tab,
  onChange,
  children,
}: {
  tab: TabId;
  onChange: (tab: TabId) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <main className="app-body">{children}</main>
      <TabBar tab={tab} onChange={onChange} />
    </div>
  );
}

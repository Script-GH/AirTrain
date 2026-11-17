import { IconGlobe, IconGrid, IconHeart, IconInsights } from '../icons';

export const TABS = [
  { id: 'overview', label: 'Overview', Icon: IconGrid },
  { id: 'training', label: 'Training', Icon: IconInsights },
  { id: 'health', label: 'Health', Icon: IconHeart },
  { id: 'network', label: 'Network', Icon: IconGlobe },
] as const;

export type TabId = (typeof TABS)[number]['id'];

export function TabBar({ tab, onChange }: { tab: TabId; onChange: (tab: TabId) => void }) {
  return (
    <nav className="tabbar" aria-label="Primary">
      {TABS.map(({ id, label, Icon }) => {
        const on = tab === id;
        return (
          <button
            key={id}
            type="button"
            className={on ? 'tab on' : 'tab'}
            aria-current={on ? 'page' : undefined}
            onClick={() => onChange(id)}
          >
            <span className="tab-icon">
              <Icon size={22} />
            </span>
            <span className="tab-label">{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

import { useState, type FormEvent } from 'react';
import { type AgentInfo, type LinkStatus } from '../types/models';
import { colors } from '../utils/format';
import { parseAgentUri } from '../utils/parseAgentUri';
import { IconClose, IconDesktop } from '../icons';
import { StatusPill } from './StatusPill';

export function PairingSheet({
  open,
  agents,
  onClose,
  onConnect,
  onRemove,
}: {
  open: boolean;
  agents: AgentInfo[];
  onClose: () => void;
  onConnect: (url: string, token: string) => void;
  onRemove: (id: string) => void;
}) {
  const [url, setUrl] = useState('');
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | undefined>();

  if (!open) return null;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    try {
      parseAgentUri(url, token);
      onConnect(url, token);
      setUrl('');
      setToken('');
      setError(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid address');
    }
  };

  return (
    <div className="sheet-backdrop" onClick={onClose} role="presentation">
      <div
        className="sheet"
        role="dialog"
        aria-label="Pair a PC agent"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sheet-handle" />
        <h2 className="sheet-title">Pair a PC agent</h2>
        <p className="sheet-copy">
          Run `airtrain serve` on the PC and paste the App URL it prints. Phone and PC must be on the
          same network.
        </p>
        <form onSubmit={submit}>
          <label className="field">
            <span>Agent URL</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="ws://192.168.1.20:8765/?token=..."
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
            />
          </label>
          <label className="field">
            <span>Token (if not in the URL)</span>
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="printed by airtrain serve"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
            />
          </label>
          {error && <div className="field-error">{error}</div>}
          <button type="submit" className="btn-accent">
            Connect
          </button>
        </form>
        {agents.length > 0 ? (
          <>
            <div className="section-label sheet-agents-label">PAIRED AGENTS</div>
            {agents.map((a) => (
              <AgentRow key={a.id} agent={a} onRemove={onRemove} />
            ))}
          </>
        ) : (
          <p className="sheet-empty">No agents paired. The app shows demo data until you add one.</p>
        )}
      </div>
    </div>
  );
}

function AgentRow({ agent, onRemove }: { agent: AgentInfo; onRemove: (id: string) => void }) {
  const { label, color } = linkLabel(agent.status);
  return (
    <div className="agent-row">
      <IconDesktop size={18} className="muted-icon" />
      <div className="agent-url tabular">{agent.url}</div>
      <StatusPill label={label} color={color} />
      <button type="button" className="icon-btn" aria-label="Remove" onClick={() => onRemove(agent.id)}>
        <IconClose size={18} />
      </button>
    </div>
  );
}

function linkLabel(status: LinkStatus): { label: string; color: string } {
  switch (status) {
    case 'connected':
      return { label: 'Connected', color: colors.green };
    case 'connecting':
      return { label: 'Connecting', color: colors.amber };
    case 'unauthorized':
      return { label: 'Wrong token', color: colors.red };
    case 'error':
      return { label: 'Unreachable', color: colors.red };
  }
}


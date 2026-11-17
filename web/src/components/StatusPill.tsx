export function StatusPill({ label, color }: { label: string; color: string }) {
  return (
    <span className="pill" style={{ color, background: hexAlpha(color, 0.12) }}>
      <span className="pill-dot" style={{ background: color }} />
      {label}
    </span>
  );
}

export function hexAlpha(hex: string, alpha: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

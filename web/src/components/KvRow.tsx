export function KvRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="kv">
      <span className="kv-k">{label}</span>
      <span className="kv-v tabular">{value}</span>
    </div>
  );
}

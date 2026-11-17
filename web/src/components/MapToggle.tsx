export function MapToggle({
  labels,
  index,
  onChange,
}: {
  labels: string[];
  index: number;
  onChange: (index: number) => void;
}) {
  return (
    <div className="seg">
      {labels.map((label, i) => (
        <button
          key={label}
          type="button"
          className={i === index ? 'seg-btn on' : 'seg-btn'}
          onClick={() => onChange(i)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

"use client";

export function Chip({
  children,
  selected,
  onClick,
}: {
  children: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`group px-3 py-1.5 rounded-full text-xs border transition-colors ${
        selected
          ? "bg-ink text-white border-ink"
          : "bg-white text-ink-light border-ink/15 hover:bg-ink hover:text-white hover:border-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-ink mb-1.5">{label}</label>
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="p-3 rounded-sm border border-ink/10 bg-paper">
      <div className="text-xs text-ink-light">{label}</div>
      <div className="text-lg font-semibold text-ink mt-1">{value}</div>
    </div>
  );
}

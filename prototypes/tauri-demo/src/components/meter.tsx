interface MeterProps {
  /** Percentage, clamped into 0-100. */
  value: number;
  /** Accessible name — the bar itself has no visible text. */
  label: string;
  /** Tailwind background class for the filled part. */
  barClassName?: string;
  testId?: string;
}

/** Thin labelled progress bar used by the KPI cards and the per-core grid. */
export function Meter({ value, label, barClassName = "bg-primary", testId }: MeterProps) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
    >
      <div
        className={`h-full rounded-full transition-[width] duration-500 ${barClassName}`}
        data-testid={testId}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

"use client";

interface ConfidenceBarProps {
  value: number; // 0.0 to 1.0
  label?: string;
  showPercent?: boolean;
}

export function ConfidenceBar({
  value,
  label,
  showPercent = true,
}: ConfidenceBarProps) {
  const clamped = Math.max(0, Math.min(1, value));
  const percent = Math.round(clamped * 100);

  const barColor =
    clamped >= 0.7 ? "#dc2626" : clamped >= 0.4 ? "#f59f00" : "#16a34a";

  return (
    <div className="w-full">
      {(label || showPercent) && (
        <div className="flex items-center justify-between mb-1.5 text-xs">
          {label && (
            <span className="font-semibold text-slate-600">
              {label}
            </span>
          )}
          {showPercent && (
            <span className="font-mono font-bold" style={{ color: barColor }}>
              {percent}%
            </span>
          )}
        </div>
      )}
      <div
        className="w-full h-2 rounded-full overflow-hidden bg-slate-200"
      >
        <div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${percent}%`,
            backgroundColor: barColor,
          }}
        />
      </div>
    </div>
  );
}

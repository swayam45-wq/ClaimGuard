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
    clamped >= 0.7 ? "#e03131" : clamped >= 0.4 ? "#f59f00" : "#2f9e44";

  return (
    <div className="w-full">
      {(label || showPercent) && (
        <div className="flex items-center justify-between mb-1.5 text-xs">
          {label && (
            <span className="font-medium" style={{ color: "#94a3b8" }}>
              {label}
            </span>
          )}
          {showPercent && (
            <span className="font-mono font-semibold" style={{ color: barColor }}>
              {percent}%
            </span>
          )}
        </div>
      )}
      <div
        className="w-full h-2 rounded-full overflow-hidden"
        style={{ backgroundColor: "#1e293b" }}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: `${percent}%`,
            backgroundColor: barColor,
          }}
        />
      </div>
    </div>
  );
}

"use client";

import { CheckCircle2, AlertTriangle, XCircle, ShieldAlert } from "lucide-react";

interface VerdictBannerProps {
  fraudLabel: "clean" | "suspicious" | "fraudulent";
  fraudProbability: number;
  estimateId: string;
}

export function VerdictBanner({
  fraudLabel,
  fraudProbability,
  estimateId,
}: VerdictBannerProps) {
  const percent = Math.round(fraudProbability * 100);

  const configs = {
    clean: {
      bgColor: "#052e16",
      borderColor: "#166534",
      textColor: "#86efac",
      titleColor: "#22c55e",
      title: "Clean Estimate — Low Fraud Risk",
      description:
        "No significant fraud anomalies or labor/part rate inflation patterns were detected.",
      icon: <CheckCircle2 className="h-8 w-8 text-green-400 shrink-0" />,
      badgeBg: "#14532d",
      badgeText: "VERIFIED CLEAN",
    },
    suspicious: {
      bgColor: "#451a03",
      borderColor: "#9a3412",
      textColor: "#fdba74",
      titleColor: "#f97316",
      title: "Suspicious Estimate — Manual Review Recommended",
      description:
        "Multiple borderline anomalies detected in labor hours, part pricing, or operation overlaps.",
      icon: <AlertTriangle className="h-8 w-8 text-orange-400 shrink-0" />,
      badgeBg: "#7c2d12",
      badgeText: "REQUIRES AUDIT",
    },
    fraudulent: {
      bgColor: "#450a0a",
      borderColor: "#991b1b",
      textColor: "#fca5a5",
      titleColor: "#ef4444",
      title: "High Fraud Probability Detected",
      description:
        "High-confidence fraud signatures identified (inflated book hours, part price markups, or phantom parts).",
      icon: <ShieldAlert className="h-8 w-8 text-red-400 shrink-0" />,
      badgeBg: "#7f1d1d",
      badgeText: "FLAGGED FRAUDULENT",
    },
  };

  const current = configs[fraudLabel] ?? configs.suspicious;

  return (
    <div
      className="rounded-2xl p-6 border shadow-lg"
      style={{
        backgroundColor: current.bgColor,
        borderColor: current.borderColor,
      }}
    >
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="mt-1">{current.icon}</div>
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h2
                className="text-xl font-bold tracking-tight"
                style={{ color: current.titleColor }}
              >
                {current.title}
              </h2>
              <span
                className="text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider"
                style={{
                  backgroundColor: current.badgeBg,
                  color: current.textColor,
                }}
              >
                {current.badgeText}
              </span>
            </div>
            <p className="text-sm mt-1 leading-relaxed" style={{ color: current.textColor }}>
              {current.description}
            </p>
            <p className="text-xs mt-2 font-mono" style={{ color: "#94a3b8" }}>
              Estimate Ref: <span className="font-semibold text-slate-200">{estimateId}</span>
            </p>
          </div>
        </div>

        <div className="text-right sm:border-l sm:pl-6 shrink-0" style={{ borderColor: current.borderColor }}>
          <span className="text-xs font-semibold uppercase tracking-wider block" style={{ color: "#94a3b8" }}>
            Model Score
          </span>
          <div className="text-3xl font-extrabold tracking-tight mt-0.5" style={{ color: current.titleColor }}>
            {percent}%
          </div>
          <span className="text-xs font-medium" style={{ color: current.textColor }}>
            Fraud Confidence
          </span>
        </div>
      </div>
    </div>
  );
}

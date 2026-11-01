"use client";

import { CheckCircle2, AlertTriangle, ShieldAlert } from "lucide-react";
import { motion } from "framer-motion";

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
      bgColor: "#f0fdf4",
      borderColor: "#bbf7d0",
      textColor: "#166534",
      titleColor: "#15803d",
      title: "Clean Estimate — Low Fraud Risk",
      description:
        "No significant fraud anomalies or labor/part rate inflation patterns were detected.",
      icon: <CheckCircle2 className="h-8 w-8 text-emerald-600 shrink-0" />,
      badgeBg: "#dcfce7",
      badgeText: "VERIFIED CLEAN",
      badgeTextColor: "#166534",
      scoreColor: "#16a34a",
    },
    suspicious: {
      bgColor: "#fffbeb",
      borderColor: "#fde68a",
      textColor: "#92400e",
      titleColor: "#b45309",
      title: "Suspicious Estimate — Manual Review Recommended",
      description:
        "Multiple borderline anomalies detected in labor hours, part pricing, or operation overlaps.",
      icon: <AlertTriangle className="h-8 w-8 text-amber-600 shrink-0" />,
      badgeBg: "#fef3c7",
      badgeText: "REQUIRES AUDIT",
      badgeTextColor: "#92400e",
      scoreColor: "#d97706",
    },
    fraudulent: {
      bgColor: "#fef2f2",
      borderColor: "#fecaca",
      textColor: "#991b1b",
      titleColor: "#b91c1c",
      title: "High Fraud Probability Detected",
      description:
        "High-confidence fraud signatures identified (inflated book hours, part price markups, or phantom parts).",
      icon: <ShieldAlert className="h-8 w-8 text-red-600 shrink-0" />,
      badgeBg: "#fee2e2",
      badgeText: "FLAGGED FRAUDULENT",
      badgeTextColor: "#991b1b",
      scoreColor: "#dc2626",
    },
  };

  const current = configs[fraudLabel] ?? configs.suspicious;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-2xl p-6 border shadow-sm"
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
                className="text-xs px-2.5 py-0.5 rounded-full font-bold uppercase tracking-wider border"
                style={{
                  backgroundColor: current.badgeBg,
                  color: current.badgeTextColor,
                  borderColor: current.borderColor,
                }}
              >
                {current.badgeText}
              </span>
            </div>
            <p className="text-sm mt-1 leading-relaxed" style={{ color: current.textColor }}>
              {current.description}
            </p>
            <p className="text-xs mt-2 font-mono text-slate-500">
              Estimate Ref: <span className="font-semibold text-navy-900">{estimateId}</span>
            </p>
          </div>
        </div>

        <div className="text-right sm:border-l sm:pl-6 shrink-0" style={{ borderColor: current.borderColor }}>
          <span className="text-xs font-semibold uppercase tracking-wider block text-slate-500">
            Model Score
          </span>
          <div className="text-3xl font-extrabold tracking-tight mt-0.5" style={{ color: current.scoreColor }}>
            {percent}%
          </div>
          <span className="text-xs font-medium" style={{ color: current.textColor }}>
            Fraud Confidence
          </span>
        </div>
      </div>
    </motion.div>
  );
}

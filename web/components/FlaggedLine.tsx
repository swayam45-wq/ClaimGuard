"use client";

import { ChevronDown, ChevronUp, AlertCircle, ShieldAlert } from "lucide-react";
import { ConfidenceBar } from "./ConfidenceBar";

interface FlaggedLineProps {
  lineId: number;
  fraudTypes: string[];
  confidence: number;
  explanation: string;
  isExpanded: boolean;
  onToggle: () => void;
}

const FRAUD_TYPE_LABELS: Record<string, string> = {
  inflated_labor_hours: "Inflated Labor Hours",
  part_price_markup: "Part Price Markup",
  duplicate_line_items: "Duplicate Line Item",
  unnecessary_operations: "Unnecessary Operation",
  phantom_parts: "Phantom Part (Trim Mismatch)",
  labor_parts_mismatch: "Labor / Parts Mismatch",
};

export function FlaggedLine({
  lineId,
  fraudTypes,
  confidence,
  explanation,
  isExpanded,
  onToggle,
}: FlaggedLineProps) {
  const primaryType = fraudTypes[0] ?? "unknown_pattern";
  const displayTitle = FRAUD_TYPE_LABELS[primaryType] ?? primaryType.replace(/_/g, " ");

  return (
    <div
      className="rounded-xl overflow-hidden border transition-all"
      style={{
        backgroundColor: "#0f1f3d",
        borderColor: isExpanded ? "#e03131" : "#1e3a5f",
      }}
    >
      <button
        onClick={onToggle}
        className="w-full p-4 flex items-center justify-between text-left transition-colors"
        style={{
          backgroundColor: isExpanded ? "#1e1427" : "#0f1f3d",
        }}
      >
        <div className="flex items-center gap-3 flex-wrap">
          <div
            className="p-1.5 rounded-lg shrink-0"
            style={{ backgroundColor: "#450a0a", border: "1px solid #7f1d1d" }}
          >
            <ShieldAlert className="h-4 w-4 text-red-400" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm font-semibold" style={{ color: "#93c5fd" }}>
                Line #{lineId}
              </span>
              <span className="text-sm font-semibold text-slate-100">
                {displayTitle}
              </span>
              {fraudTypes.length > 1 && (
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-medium"
                  style={{ backgroundColor: "#334155", color: "#cbd5e1" }}
                >
                  +{fraudTypes.length - 1} more
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          <div className="w-28 hidden sm:block">
            <ConfidenceBar value={confidence} showPercent={true} />
          </div>
          <div className="text-slate-400">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5" />
            ) : (
              <ChevronDown className="h-5 w-5" />
            )}
          </div>
        </div>
      </button>

      {isExpanded && (
        <div
          className="p-5 border-t space-y-4"
          style={{
            backgroundColor: "#081326",
            borderColor: "#1e3a5f",
          }}
        >
          {/* Mobile confidence bar */}
          <div className="sm:hidden">
            <ConfidenceBar value={confidence} label="Line Suspicion Confidence" />
          </div>

          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider mb-1" style={{ color: "#94a3b8" }}>
              Identified Fraud Patterns
            </h4>
            <div className="flex flex-wrap gap-2 mt-1.5">
              {fraudTypes.map((t) => (
                <span
                  key={t}
                  className="text-xs px-2.5 py-1 rounded-md font-medium"
                  style={{ backgroundColor: "#7f1d1d", color: "#fca5a5" }}
                >
                  {FRAUD_TYPE_LABELS[t] ?? t}
                </span>
              ))}
            </div>
          </div>

          <div
            className="p-3.5 rounded-lg border flex items-start gap-3"
            style={{
              backgroundColor: "#111827",
              borderColor: "#374151",
            }}
          >
            <AlertCircle className="h-4 w-4 text-blue-400 shrink-0 mt-0.5" />
            <div className="text-sm leading-relaxed text-slate-200">
              <span className="font-semibold text-white block mb-0.5">SHAP-Derived Explanation:</span>
              {explanation}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

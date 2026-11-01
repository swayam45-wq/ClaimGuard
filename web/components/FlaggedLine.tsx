"use client";

import { ChevronDown, ChevronUp, AlertCircle, ShieldAlert } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
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
      className="rounded-2xl overflow-hidden border transition-all shadow-sm"
      style={{
        backgroundColor: "#ffffff",
        borderColor: isExpanded ? "#f87171" : "#e2e8f0",
      }}
    >
      <button
        onClick={onToggle}
        className="w-full p-4 sm:p-5 flex items-center justify-between text-left transition-colors hover:bg-slate-50"
        style={{
          backgroundColor: isExpanded ? "#fff7ed" : "#ffffff",
        }}
      >
        <div className="flex items-center gap-3 flex-wrap">
          <div
            className="p-2 rounded-xl shrink-0"
            style={{ backgroundColor: "#fee2e2", border: "1px solid #fecaca" }}
          >
            <ShieldAlert className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-sm font-bold text-brand-600">
                Line #{lineId}
              </span>
              <span className="text-sm font-bold text-navy-900">
                {displayTitle}
              </span>
              {fraudTypes.length > 1 && (
                <span
                  className="text-xs px-2.5 py-0.5 rounded-full font-semibold bg-slate-100 text-slate-700 border border-slate-200"
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

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <div
              className="p-5 border-t space-y-4"
              style={{
                backgroundColor: "#fafbfc",
                borderColor: "#e2e8f0",
              }}
            >
              {/* Mobile confidence bar */}
              <div className="sm:hidden">
                <ConfidenceBar value={confidence} label="Line Suspicion Confidence" />
              </div>

              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider mb-2 text-slate-500">
                  Identified Fraud Patterns
                </h4>
                <div className="flex flex-wrap gap-2">
                  {fraudTypes.map((t) => (
                    <span
                      key={t}
                      className="text-xs px-3 py-1 rounded-lg font-semibold border"
                      style={{ backgroundColor: "#fef2f2", borderColor: "#fecaca", color: "#b91c1c" }}
                    >
                      {FRAUD_TYPE_LABELS[t] ?? t}
                    </span>
                  ))}
                </div>
              </div>

              <div
                className="p-4 rounded-xl border flex items-start gap-3 bg-white"
                style={{ borderColor: "#e2e8f0" }}
              >
                <AlertCircle className="h-5 w-5 text-brand-500 shrink-0 mt-0.5" />
                <div className="text-sm leading-relaxed text-slate-700">
                  <span className="font-bold text-navy-900 block mb-0.5">SHAP-Derived Explanation:</span>
                  {explanation}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from "recharts";
import { ArrowLeft, Clock, AlertTriangle } from "lucide-react";
import { VerdictBanner } from "@/components/VerdictBanner";
import { FlaggedLine } from "@/components/FlaggedLine";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FlaggedLineData {
  line_id: number;
  fraud_types: string[];
  confidence: number;
  explanation: string;
}

interface PredictionResult {
  estimate_id: string;
  fraud_probability: number;
  is_fraud: boolean;
  fraud_label: "clean" | "suspicious" | "fraudulent";
  flagged_lines: FlaggedLineData[];
  processing_time_ms: number;
}

interface PartInfo {
  name: string;
  oem_price: number;
  billed_price: number;
  source: string;
}

interface LineItem {
  line_id: number;
  operation: string;
  panel: string;
  description: string;
  part: PartInfo | null;
  labor_hours_billed: number;
  labor_hours_book: number;
  labor_rate: number;
}

interface Estimate {
  estimate_id: string;
  shop_id: string;
  region: string;
  vehicle: {
    year: number;
    make: string;
    model: string;
    trim: string;
    mileage: number;
    class: string;
  };
  scenario: string;
  line_items: LineItem[];
}

interface StoredPayload {
  result: PredictionResult;
  estimate: Estimate;
}

// ---------------------------------------------------------------------------
// Gauge chart (light mode)
// ---------------------------------------------------------------------------

function FraudGauge({ probability }: { probability: number }) {
  const pct = Math.round(probability * 100);
  const gaugeColor =
    pct >= 70 ? "#dc2626" : pct >= 40 ? "#f59f00" : "#16a34a";
  const trackColor = pct >= 70 ? "#fef2f2" : pct >= 40 ? "#fffbeb" : "#f0fdf4";
  const data = [{ value: pct, fill: gaugeColor }];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="flex flex-col items-center"
    >
      <p className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "#94a3b8" }}>
        Fraud Probability
      </p>
      <div style={{ width: 180, height: 180 }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="60%"
            outerRadius="90%"
            data={data}
            startAngle={225}
            endAngle={-45}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              background={{ fill: trackColor }}
              dataKey="value"
              cornerRadius={6}
              angleAxisId={0}
            />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <p
        className="text-4xl font-extrabold tracking-tight mt-[-16px]"
        style={{ color: gaugeColor }}
      >
        {pct}%
      </p>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Line items table (light mode)
// ---------------------------------------------------------------------------

function LineItemsTable({
  lines,
  flaggedIds,
}: {
  lines: LineItem[];
  flaggedIds: Set<number>;
}) {
  const headers = [
    "ID", "Operation", "Panel", "Description",
    "Labor Billed", "Labor Book", "Hrs Ratio",
    "Part Billed", "Part OEM", "Flags",
  ];

  return (
    <div
      className="overflow-x-auto rounded-2xl border"
      style={{ borderColor: "#e2e8f0" }}
    >
      <table className="w-full text-sm">
        <thead>
          <tr style={{ backgroundColor: "#f8fafc" }}>
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left font-semibold whitespace-nowrap text-xs uppercase tracking-wider"
                style={{ color: "#64748b", borderBottom: "1px solid #e2e8f0" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((line, idx) => {
            const isFlagged = flaggedIds.has(line.line_id);
            const hoursRatio =
              line.labor_hours_book > 0
                ? (line.labor_hours_billed / line.labor_hours_book).toFixed(2)
                : "—";

            return (
              <motion.tr
                key={line.line_id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.35, delay: idx * 0.06 }}
                style={{
                  backgroundColor: isFlagged
                    ? "#fff5f5"
                    : idx % 2 === 0
                    ? "#ffffff"
                    : "#f8fafc",
                  borderLeft: isFlagged ? "3px solid #dc2626" : "3px solid transparent",
                }}
              >
                <td className="px-4 py-3 font-mono font-semibold" style={{ color: "#0066cc" }}>
                  #{line.line_id}
                </td>
                <td className="px-4 py-3 font-medium" style={{ color: "#0d1b2e" }}>
                  {line.operation}
                </td>
                <td className="px-4 py-3 whitespace-nowrap" style={{ color: "#475569" }}>
                  {line.panel}
                </td>
                <td className="px-4 py-3 max-w-[200px]" style={{ color: "#64748b" }}>
                  {line.description}
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#0d1b2e" }}>
                  {line.labor_hours_billed}h
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#475569" }}>
                  {line.labor_hours_book}h
                </td>
                <td
                  className="px-4 py-3 text-right font-mono font-bold"
                  style={{
                    color:
                      parseFloat(hoursRatio) > 2
                        ? "#dc2626"
                        : parseFloat(hoursRatio) > 1.2
                        ? "#d97706"
                        : "#16a34a",
                  }}
                >
                  {hoursRatio}×
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#0d1b2e" }}>
                  {line.part ? `$${line.part.billed_price.toFixed(2)}` : "—"}
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#64748b" }}>
                  {line.part ? `$${line.part.oem_price.toFixed(2)}` : "—"}
                </td>
                <td className="px-4 py-3">
                  {isFlagged ? (
                    <span
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold"
                      style={{ backgroundColor: "#fee2e2", color: "#dc2626" }}
                    >
                      <AlertTriangle className="h-3 w-3" />
                      Flagged
                    </span>
                  ) : (
                    <span
                      className="inline-flex px-2.5 py-1 rounded-full text-xs font-semibold"
                      style={{ backgroundColor: "#dcfce7", color: "#16a34a" }}
                    >
                      Clean
                    </span>
                  )}
                </td>
              </motion.tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inner results component
// ---------------------------------------------------------------------------

function ResultsInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [expandedLines, setExpandedLines] = useState<Set<number>>(new Set());

  const payload = useMemo<StoredPayload | null>(() => {
    const raw = searchParams.get("data");
    if (!raw) return null;
    try {
      const json = decodeURIComponent(escape(atob(raw)));
      return JSON.parse(json) as StoredPayload;
    } catch {
      return null;
    }
  }, [searchParams]);

  const toggleLine = (id: number) => {
    setExpandedLines((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (!payload) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-24 text-center">
        <AlertTriangle className="h-16 w-16 mx-auto mb-4" style={{ color: "#f59f00" }} />
        <h2 className="text-2xl font-bold mb-2" style={{ color: "#0d1b2e" }}>
          No Result Data
        </h2>
        <p className="mb-6" style={{ color: "#64748b" }}>
          The result data is missing or corrupted. Please submit an estimate first.
        </p>
        <button
          onClick={() => router.push("/")}
          className="px-6 py-3 rounded-xl font-semibold text-white transition-all hover:opacity-90"
          style={{ background: "linear-gradient(135deg,#0d1b2e,#0066cc)" }}
        >
          Back to Home
        </button>
      </div>
    );
  }

  const { result, estimate } = payload;
  const flaggedIds = new Set(result.flagged_lines.map((f) => f.line_id));

  return (
    <div className="bg-white min-h-screen">
      {/* Results header strip */}
      <div
        className="border-b py-6"
        style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}
      >
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <button
            onClick={() => router.push("/")}
            className="flex items-center gap-2 text-sm font-medium mb-5 transition-colors hover:opacity-80"
            style={{ color: "#0066cc" }}
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Home
          </button>
          <VerdictBanner
            fraudLabel={result.fraud_label}
            fraudProbability={result.fraud_probability}
            estimateId={result.estimate_id}
          />
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Summary row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {/* Gauge */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="rounded-2xl p-8 flex flex-col items-center justify-center border"
            style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}
          >
            <FraudGauge probability={result.fraud_probability} />
          </motion.div>

          {/* Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-2xl p-7 col-span-2 border"
            style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}
          >
            <h3
              className="text-xs font-bold uppercase tracking-wider mb-5"
              style={{ color: "#94a3b8" }}
            >
              Estimate Summary
            </h3>
            <div className="grid grid-cols-2 gap-5">
              <StatItem label="Estimate ID" value={estimate.estimate_id} mono />
              <StatItem label="Shop ID" value={estimate.shop_id} mono />
              <StatItem
                label="Vehicle"
                value={`${estimate.vehicle.year} ${estimate.vehicle.make} ${estimate.vehicle.model}`}
              />
              <StatItem label="Region" value={estimate.region} />
              <StatItem label="Scenario" value={estimate.scenario} />
              <StatItem
                label="Line Items"
                value={`${estimate.line_items.length} total, ${result.flagged_lines.length} flagged`}
              />
              <StatItem label="Mileage" value={`${estimate.vehicle.mileage.toLocaleString()} mi`} />
              <StatItem label="Shop" value={estimate.shop_id} mono />
            </div>
          </motion.div>
        </div>

        {/* Line Items Table */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="mb-10"
        >
          <h2 className="text-lg font-bold mb-4" style={{ color: "#0d1b2e" }}>
            Line Items
          </h2>
          <LineItemsTable lines={estimate.line_items} flaggedIds={flaggedIds} />
        </motion.section>

        {/* Flagged Lines Accordion */}
        {result.flagged_lines.length > 0 && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <h2 className="text-lg font-bold mb-4" style={{ color: "#0d1b2e" }}>
              Flagged Lines — Detailed Analysis
            </h2>
            <div className="space-y-3">
              {result.flagged_lines.map((fl) => (
                <FlaggedLine
                  key={fl.line_id}
                  lineId={fl.line_id}
                  fraudTypes={fl.fraud_types}
                  confidence={fl.confidence}
                  explanation={fl.explanation}
                  isExpanded={expandedLines.has(fl.line_id)}
                  onToggle={() => toggleLine(fl.line_id)}
                />
              ))}
            </div>
          </motion.section>
        )}

        {/* Processing time */}
        <div
          className="mt-8 flex items-center gap-2 text-xs"
          style={{ color: "#94a3b8" }}
        >
          <Clock className="h-3.5 w-3.5" />
          Processed in {result.processing_time_ms.toFixed(1)} ms
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatItem helper
// ---------------------------------------------------------------------------

function StatItem({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider mb-0.5" style={{ color: "#94a3b8" }}>
        {label}
      </p>
      <p
        className={`text-sm font-semibold ${mono ? "font-mono" : ""}`}
        style={{ color: "#0d1b2e" }}
      >
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export — wrapped in Suspense for useSearchParams
// ---------------------------------------------------------------------------

export default function ResultsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-32">
          <div className="text-center">
            <div
              className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4"
              style={{ borderColor: "#0066cc", borderTopColor: "transparent" }}
            />
            <p style={{ color: "#94a3b8" }}>Loading results…</p>
          </div>
        </div>
      }
    >
      <ResultsInner />
    </Suspense>
  );
}

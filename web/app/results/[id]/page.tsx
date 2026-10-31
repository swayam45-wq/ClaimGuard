"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useMemo, useState } from "react";
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
// Gauge chart
// ---------------------------------------------------------------------------

function FraudGauge({ probability }: { probability: number }) {
  const pct = Math.round(probability * 100);

  const gaugeColor =
    pct >= 70 ? "#e03131" : pct >= 40 ? "#f59f00" : "#2f9e44";

  const data = [{ value: pct, fill: gaugeColor }];

  return (
    <div className="flex flex-col items-center">
      <p className="text-sm font-medium mb-2" style={{ color: "#94a3b8" }}>
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
            {/* background track */}
            <RadialBar
              background={{ fill: "#1e293b" }}
              dataKey="value"
              cornerRadius={6}
              angleAxisId={0}
            />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <p className="text-4xl font-bold mt-[-16px]" style={{ color: gaugeColor }}>
        {pct}%
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Line items table
// ---------------------------------------------------------------------------

function LineItemsTable({
  lines,
  flaggedIds,
}: {
  lines: LineItem[];
  flaggedIds: Set<number>;
}) {
  const headers = [
    "ID",
    "Operation",
    "Panel",
    "Description",
    "Labor Billed",
    "Labor Book",
    "Hrs Ratio",
    "Part Billed",
    "Part OEM",
    "Flags",
  ];

  return (
    <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid #1e293b" }}>
      <table className="w-full text-sm">
        <thead>
          <tr style={{ backgroundColor: "#0c1526" }}>
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left font-medium whitespace-nowrap"
                style={{ color: "#64748b", borderBottom: "1px solid #1e293b" }}
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
              <tr
                key={line.line_id}
                style={{
                  backgroundColor: isFlagged
                    ? "#450a0a22"
                    : idx % 2 === 0
                    ? "#0f1f3d"
                    : "#0a1628",
                  borderLeft: isFlagged ? "3px solid #e03131" : "3px solid transparent",
                }}
              >
                <td className="px-4 py-3 font-mono" style={{ color: "#93c5fd" }}>
                  #{line.line_id}
                </td>
                <td className="px-4 py-3" style={{ color: "#cbd5e1" }}>
                  {line.operation}
                </td>
                <td className="px-4 py-3 whitespace-nowrap" style={{ color: "#cbd5e1" }}>
                  {line.panel}
                </td>
                <td className="px-4 py-3 max-w-[200px]" style={{ color: "#94a3b8" }}>
                  {line.description}
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#cbd5e1" }}>
                  {line.labor_hours_billed}h
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#cbd5e1" }}>
                  {line.labor_hours_book}h
                </td>
                <td
                  className="px-4 py-3 text-right font-mono font-semibold"
                  style={{
                    color:
                      parseFloat(hoursRatio) > 2
                        ? "#f87171"
                        : parseFloat(hoursRatio) > 1.2
                        ? "#fbbf24"
                        : "#4ade80",
                  }}
                >
                  {hoursRatio}×
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#cbd5e1" }}>
                  {line.part ? `$${line.part.billed_price.toFixed(2)}` : "—"}
                </td>
                <td className="px-4 py-3 text-right font-mono" style={{ color: "#94a3b8" }}>
                  {line.part ? `$${line.part.oem_price.toFixed(2)}` : "—"}
                </td>
                <td className="px-4 py-3">
                  {isFlagged ? (
                    <span
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{ backgroundColor: "#7f1d1d", color: "#fca5a5" }}
                    >
                      <AlertTriangle className="h-3 w-3" />
                      Flagged
                    </span>
                  ) : (
                    <span
                      className="inline-flex px-2 py-0.5 rounded-full text-xs"
                      style={{ backgroundColor: "#14532d33", color: "#86efac" }}
                    >
                      Clean
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inner results component (uses useSearchParams)
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
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (!payload) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-24 text-center">
        <AlertTriangle className="h-16 w-16 mx-auto mb-4" style={{ color: "#f59f00" }} />
        <h2 className="text-2xl font-bold mb-2" style={{ color: "#f1f5f9" }}>
          No Result Data
        </h2>
        <p className="mb-6" style={{ color: "#94a3b8" }}>
          The result data is missing or corrupted. Please submit an estimate first.
        </p>
        <button
          onClick={() => router.push("/")}
          className="px-6 py-3 rounded-lg font-medium"
          style={{ backgroundColor: "#3b5bdb", color: "#fff" }}
        >
          Back to Home
        </button>
      </div>
    );
  }

  const { result, estimate } = payload;
  const flaggedIds = new Set(result.flagged_lines.map((f) => f.line_id));

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back */}
      <button
        onClick={() => router.push("/")}
        className="flex items-center gap-2 mb-6 text-sm transition-colors"
        style={{ color: "#64748b" }}
        onMouseEnter={(e) =>
          ((e.currentTarget as HTMLButtonElement).style.color = "#94a3b8")
        }
        onMouseLeave={(e) =>
          ((e.currentTarget as HTMLButtonElement).style.color = "#64748b")
        }
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Home
      </button>

      {/* Verdict banner */}
      <VerdictBanner
        fraudLabel={result.fraud_label}
        fraudProbability={result.fraud_probability}
        estimateId={result.estimate_id}
      />

      {/* Summary row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-6">
        {/* Gauge */}
        <div
          className="rounded-xl p-6 flex flex-col items-center justify-center"
          style={{ backgroundColor: "#0f1f3d", border: "1px solid #1e293b" }}
        >
          <FraudGauge probability={result.fraud_probability} />
        </div>

        {/* Stats */}
        <div
          className="rounded-xl p-6 col-span-2"
          style={{ backgroundColor: "#0f1f3d", border: "1px solid #1e293b" }}
        >
          <h3 className="text-sm font-semibold mb-4" style={{ color: "#94a3b8" }}>
            ESTIMATE SUMMARY
          </h3>
          <div className="grid grid-cols-2 gap-4">
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
        </div>
      </div>

      {/* Line Items Table */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold mb-4" style={{ color: "#f1f5f9" }}>
          Line Items
        </h2>
        <LineItemsTable lines={estimate.line_items} flaggedIds={flaggedIds} />
      </section>

      {/* Flagged Lines Accordion */}
      {result.flagged_lines.length > 0 && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold mb-4" style={{ color: "#f1f5f9" }}>
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
        </section>
      )}

      {/* Processing time */}
      <div
        className="mt-8 flex items-center gap-2 text-xs"
        style={{ color: "#475569" }}
      >
        <Clock className="h-3.5 w-3.5" />
        Processed in {result.processing_time_ms.toFixed(1)} ms
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
      <p className="text-xs mb-0.5" style={{ color: "#64748b" }}>
        {label}
      </p>
      <p
        className={`text-sm font-medium ${mono ? "font-mono" : ""}`}
        style={{ color: "#cbd5e1" }}
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
              style={{ borderColor: "#3b5bdb", borderTopColor: "transparent" }}
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

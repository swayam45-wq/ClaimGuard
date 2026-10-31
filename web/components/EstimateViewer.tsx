"use client";

import { AlertTriangle, Car, Store, MapPin, Wrench } from "lucide-react";

export interface PartInfo {
  name: string;
  oem_price: number;
  billed_price: number;
  source: string;
}

export interface LineItem {
  line_id: number;
  operation: string;
  panel: string;
  description: string;
  part: PartInfo | null;
  labor_hours_billed: number;
  labor_hours_book: number;
  labor_rate: number;
}

export interface EstimateData {
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

interface EstimateViewerProps {
  estimate: EstimateData;
  flaggedLineIds?: number[];
}

export function EstimateViewer({
  estimate,
  flaggedLineIds = [],
}: EstimateViewerProps) {
  const flaggedSet = new Set(flaggedLineIds);

  const totalLabor = estimate.line_items.reduce(
    (acc, li) => acc + li.labor_hours_billed * li.labor_rate,
    0
  );
  const totalParts = estimate.line_items.reduce(
    (acc, li) => acc + (li.part?.billed_price ?? 0),
    0
  );
  const grandTotal = totalLabor + totalParts;

  return (
    <div className="space-y-6">
      {/* Header Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div
          className="p-4 rounded-xl border flex items-center gap-3"
          style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-950/60 border border-blue-800/40">
            <Car className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400">Vehicle</p>
            <p className="text-sm font-semibold text-slate-100">
              {estimate.vehicle.year} {estimate.vehicle.make} {estimate.vehicle.model}
            </p>
            <p className="text-xs text-slate-400">{estimate.vehicle.trim} • {estimate.vehicle.mileage.toLocaleString()} mi</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3"
          style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-950/60 border border-blue-800/40">
            <Store className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400">Repair Facility</p>
            <p className="text-sm font-semibold font-mono text-slate-100">
              {estimate.shop_id}
            </p>
            <p className="text-xs text-slate-400">CIECA Partner</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3"
          style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-950/60 border border-blue-800/40">
            <MapPin className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400">Region & Impact</p>
            <p className="text-sm font-semibold capitalize text-slate-100">
              {estimate.region}
            </p>
            <p className="text-xs text-slate-400 capitalize">{estimate.scenario.replace(/_/g, " ")}</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3"
          style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-950/60 border border-blue-800/40">
            <Wrench className="h-5 w-5 text-blue-400" />
          </div>
          <div>
            <p className="text-xs text-slate-400">Billed Total</p>
            <p className="text-sm font-semibold font-mono text-emerald-400">
              ${grandTotal.toFixed(2)}
            </p>
            <p className="text-xs text-slate-400">{estimate.line_items.length} line items</p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ borderColor: "#1e293b", backgroundColor: "#0a1628" }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: "#0c1526" }}>
                <th className="px-4 py-3 text-left font-medium text-slate-400">#</th>
                <th className="px-4 py-3 text-left font-medium text-slate-400">Op</th>
                <th className="px-4 py-3 text-left font-medium text-slate-400">Panel</th>
                <th className="px-4 py-3 text-left font-medium text-slate-400">Description</th>
                <th className="px-4 py-3 text-right font-medium text-slate-400">Billed Hrs</th>
                <th className="px-4 py-3 text-right font-medium text-slate-400">Book Hrs</th>
                <th className="px-4 py-3 text-right font-medium text-slate-400">Part Billed</th>
                <th className="px-4 py-3 text-center font-medium text-slate-400">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {estimate.line_items.map((line) => {
                const isFlagged = flaggedSet.has(line.line_id);
                return (
                  <tr
                    key={line.line_id}
                    className="transition-colors"
                    style={{
                      backgroundColor: isFlagged ? "#450a0a22" : "transparent",
                    }}
                  >
                    <td className="px-4 py-3 font-mono text-blue-400">{line.line_id}</td>
                    <td className="px-4 py-3 text-slate-200">{line.operation}</td>
                    <td className="px-4 py-3 text-slate-300">{line.panel}</td>
                    <td className="px-4 py-3 text-slate-400 max-w-xs truncate">{line.description}</td>
                    <td className="px-4 py-3 text-right font-mono text-slate-200">
                      {line.labor_hours_billed.toFixed(1)}h
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-400">
                      {line.labor_hours_book.toFixed(1)}h
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-200">
                      {line.part ? `$${line.part.billed_price.toFixed(2)}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isFlagged ? (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-900/60 text-red-300 border border-red-800">
                          <AlertTriangle className="h-3 w-3" /> Flagged
                        </span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-950/60 text-emerald-300 border border-emerald-800">
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
      </div>
    </div>
  );
}

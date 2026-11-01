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
          className="p-4 rounded-xl border flex items-center gap-3 bg-white shadow-sm"
          style={{ borderColor: "#e2e8f0" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-50 border border-blue-200">
            <Car className="h-5 w-5 text-brand-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Vehicle</p>
            <p className="text-sm font-bold text-navy-900">
              {estimate.vehicle.year} {estimate.vehicle.make} {estimate.vehicle.model}
            </p>
            <p className="text-xs text-slate-500">{estimate.vehicle.trim} • {estimate.vehicle.mileage.toLocaleString()} mi</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3 bg-white shadow-sm"
          style={{ borderColor: "#e2e8f0" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-50 border border-blue-200">
            <Store className="h-5 w-5 text-brand-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Repair Facility</p>
            <p className="text-sm font-bold font-mono text-navy-900">
              {estimate.shop_id}
            </p>
            <p className="text-xs text-slate-500">CIECA Partner</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3 bg-white shadow-sm"
          style={{ borderColor: "#e2e8f0" }}
        >
          <div className="p-2.5 rounded-lg bg-blue-50 border border-blue-200">
            <MapPin className="h-5 w-5 text-brand-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Region & Impact</p>
            <p className="text-sm font-bold capitalize text-navy-900">
              {estimate.region}
            </p>
            <p className="text-xs text-slate-500 capitalize">{estimate.scenario.replace(/_/g, " ")}</p>
          </div>
        </div>

        <div
          className="p-4 rounded-xl border flex items-center gap-3 bg-white shadow-sm"
          style={{ borderColor: "#e2e8f0" }}
        >
          <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200">
            <Wrench className="h-5 w-5 text-emerald-600" />
          </div>
          <div>
            <p className="text-xs text-slate-500">Billed Total</p>
            <p className="text-sm font-bold font-mono text-emerald-600">
              ${grandTotal.toFixed(2)}
            </p>
            <p className="text-xs text-slate-500">{estimate.line_items.length} line items</p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div
        className="rounded-2xl border overflow-hidden bg-white shadow-sm"
        style={{ borderColor: "#e2e8f0" }}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ backgroundColor: "#f8fafc" }}>
                <th className="px-4 py-3 text-left font-semibold text-slate-600 text-xs uppercase tracking-wider">#</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600 text-xs uppercase tracking-wider">Op</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600 text-xs uppercase tracking-wider">Panel</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600 text-xs uppercase tracking-wider">Description</th>
                <th className="px-4 py-3 text-right font-semibold text-slate-600 text-xs uppercase tracking-wider">Billed Hrs</th>
                <th className="px-4 py-3 text-right font-semibold text-slate-600 text-xs uppercase tracking-wider">Book Hrs</th>
                <th className="px-4 py-3 text-right font-semibold text-slate-600 text-xs uppercase tracking-wider">Part Billed</th>
                <th className="px-4 py-3 text-center font-semibold text-slate-600 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {estimate.line_items.map((line) => {
                const isFlagged = flaggedSet.has(line.line_id);
                return (
                  <tr
                    key={line.line_id}
                    className="transition-colors hover:bg-slate-50"
                    style={{
                      backgroundColor: isFlagged ? "#fef2f2" : "transparent",
                    }}
                  >
                    <td className="px-4 py-3 font-mono font-bold text-brand-600">{line.line_id}</td>
                    <td className="px-4 py-3 font-medium text-navy-900">{line.operation}</td>
                    <td className="px-4 py-3 text-slate-600">{line.panel}</td>
                    <td className="px-4 py-3 text-slate-500 max-w-xs truncate">{line.description}</td>
                    <td className="px-4 py-3 text-right font-mono text-navy-900">
                      {line.labor_hours_billed.toFixed(1)}h
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-500">
                      {line.labor_hours_book.toFixed(1)}h
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-navy-900">
                      {line.part ? `$${line.part.billed_price.toFixed(2)}` : "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isFlagged ? (
                        <span className="inline-flex items-center gap-1 text-xs px-2.5 py-0.5 rounded-full bg-red-100 text-red-700 font-semibold border border-red-200">
                          <AlertTriangle className="h-3 w-3" /> Flagged
                        </span>
                      ) : (
                        <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 font-semibold border border-emerald-200">
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

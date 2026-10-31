"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Shield,
  Zap,
  Search,
  Upload,
  FileJson,
  Loader2,
  AlertCircle,
  ChevronRight,
  X,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

interface ApiError {
  detail: string | ValidationError[];
}

// ---------------------------------------------------------------------------
// Sample estimate
// ---------------------------------------------------------------------------

const SAMPLE_ESTIMATE: Estimate = {
  estimate_id: "EST-DEMO-001",
  shop_id: "SHOP-042",
  region: "midwest",
  vehicle: {
    year: 2021,
    make: "Honda",
    model: "Civic",
    trim: "EX",
    mileage: 45000,
    class: "compact",
  },
  scenario: "rear_end",
  line_items: [
    {
      line_id: 1,
      operation: "R&R",
      panel: "rear_bumper",
      description: "R&R rear bumper cover",
      part: {
        name: "bumper cover",
        oem_price: 285.0,
        billed_price: 285.0,
        source: "OEM",
      },
      labor_hours_billed: 2.5,
      labor_hours_book: 2.5,
      labor_rate: 78.0,
    },
    {
      line_id: 2,
      operation: "Replace",
      panel: "left_taillight",
      description: "Replace left taillight assembly",
      part: {
        name: "taillight assembly",
        oem_price: 320.0,
        billed_price: 320.0,
        source: "OEM",
      },
      labor_hours_billed: 1.0,
      labor_hours_book: 1.0,
      labor_rate: 78.0,
    },
    {
      line_id: 3,
      operation: "Repair",
      panel: "trunk_lid",
      description: "Repair trunk lid dents",
      part: null,
      labor_hours_billed: 8.5,
      labor_hours_book: 2.0,
      labor_rate: 78.0,
    },
  ],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function encodeResult(payload: unknown): string {
  return btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
}

// ---------------------------------------------------------------------------
// Feature cards
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: <Search className="h-6 w-6" style={{ color: "#3b5bdb" }} />,
    title: "6 Fraud Patterns Detected",
    desc: "Labor inflation, parts mark-up, phantom operations, duplicate lines, inconsistent hours, and unrelated repairs.",
  },
  {
    icon: <Shield className="h-6 w-6" style={{ color: "#3b5bdb" }} />,
    title: "Shop-Level Analysis",
    desc: "Tracks shop-level fraud history across submissions to surface repeat offenders.",
  },
  {
    icon: <Zap className="h-6 w-6" style={{ color: "#3b5bdb" }} />,
    title: "SHAP Explainability",
    desc: "Every decision is explained with SHAP values so adjusters understand exactly why a flag was raised.",
  },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"paste" | "upload">("paste");
  const [jsonText, setJsonText] = useState("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Fill sample ──────────────────────────────────────────────────────────
  const fillSample = () => {
    setJsonText(JSON.stringify(SAMPLE_ESTIMATE, null, 2));
    setError(null);
    setValidationErrors([]);
  };

  // ── File drop handlers ───────────────────────────────────────────────────
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  }, []);

  const handleFileSelect = (file: File) => {
    if (!file.name.endsWith(".json") && !file.name.endsWith(".jsonl")) {
      setError("Only .json and .jsonl files are supported.");
      return;
    }
    setUploadedFile(file);
    setError(null);
    setValidationErrors([]);
  };

  // ── Submit ───────────────────────────────────────────────────────────────
  const handleSubmit = async () => {
    setError(null);
    setValidationErrors([]);
    setLoading(true);

    try {
      let estimatePayload: Estimate;

      if (activeTab === "paste") {
        if (!jsonText.trim()) {
          setError("Please paste an estimate JSON or use the sample.");
          setLoading(false);
          return;
        }
        try {
          estimatePayload = JSON.parse(jsonText) as Estimate;
        } catch {
          setError("Invalid JSON — please check your input.");
          setLoading(false);
          return;
        }
      } else {
        if (!uploadedFile) {
          setError("Please upload a .json or .jsonl file.");
          setLoading(false);
          return;
        }
        const text = await uploadedFile.text();
        try {
          estimatePayload = JSON.parse(text) as Estimate;
        } catch {
          setError("Could not parse the uploaded file as JSON.");
          setLoading(false);
          return;
        }
      }

      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

      const response = await fetch(`${apiUrl}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(estimatePayload),
      });

      if (!response.ok) {
        const errData = (await response.json()) as ApiError;
        if (Array.isArray(errData.detail)) {
          setValidationErrors(errData.detail);
          setError("Validation failed — see field errors below.");
        } else {
          setError(
            typeof errData.detail === "string"
              ? errData.detail
              : "API error — please try again."
          );
        }
        setLoading(false);
        return;
      }

      const result = await response.json();
      const payload = { result, estimate: estimatePayload };
      const encoded = encodeResult(payload);

      router.push(`/results/${estimatePayload.estimate_id}?data=${encoded}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Network error: ${err.message}`
          : "Unexpected error — is the API running?"
      );
      setLoading(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      {/* Hero */}
      <div className="text-center mb-12">
        <div className="flex justify-center mb-6">
          <div
            className="p-4 rounded-2xl"
            style={{ backgroundColor: "#1e3a8a22", border: "1px solid #3b5bdb44" }}
          >
            <Shield className="h-14 w-14" style={{ color: "#3b5bdb" }} strokeWidth={1.5} />
          </div>
        </div>
        <h1
          className="text-5xl font-extrabold tracking-tight mb-4"
          style={{ color: "#f1f5f9" }}
        >
          Claim<span style={{ color: "#3b5bdb" }}>Guard</span>
        </h1>
        <p className="text-xl max-w-xl mx-auto" style={{ color: "#94a3b8" }}>
          AI-powered fraud detection for auto repair estimates
        </p>
      </div>

      {/* Form card */}
      <div
        className="rounded-2xl p-8 mb-10"
        style={{
          backgroundColor: "#0f1f3d",
          border: "1px solid #1e3a5f",
        }}
      >
        {/* Tabs */}
        <div
          className="flex gap-1 p-1 rounded-lg mb-6 w-fit"
          style={{ backgroundColor: "#0c1526" }}
        >
          {(["paste", "upload"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setError(null);
                setValidationErrors([]);
              }}
              className="px-5 py-2 rounded-md text-sm font-medium capitalize transition-all"
              style={
                activeTab === tab
                  ? { backgroundColor: "#3b5bdb", color: "#fff" }
                  : { color: "#94a3b8", backgroundColor: "transparent" }
              }
            >
              {tab === "paste" ? "Paste JSON" : "Upload File"}
            </button>
          ))}
        </div>

        {/* Paste tab */}
        {activeTab === "paste" && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium" style={{ color: "#cbd5e1" }}>
                Estimate JSON
              </label>
              <button
                onClick={fillSample}
                className="text-xs px-3 py-1 rounded-md font-medium"
                style={{
                  backgroundColor: "#1e3a5f",
                  color: "#93c5fd",
                  border: "1px solid #2563eb44",
                }}
              >
                Load sample estimate
              </button>
            </div>
            <textarea
              value={jsonText}
              onChange={(e) => setJsonText(e.target.value)}
              rows={20}
              spellCheck={false}
              placeholder={`{\n  "estimate_id": "EST-001",\n  "shop_id": "SHOP-001",\n  ...\n}`}
              className="w-full rounded-lg p-4 text-sm font-mono resize-y focus:outline-none focus:ring-2"
              style={{
                backgroundColor: "#071525",
                color: "#93c5fd",
                border: "1px solid #1e3a5f",
                caretColor: "#3b5bdb",
              }}
            />
          </div>
        )}

        {/* Upload tab */}
        {activeTab === "upload" && (
          <div>
            <label className="text-sm font-medium mb-2 block" style={{ color: "#cbd5e1" }}>
              Upload Estimate File
            </label>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="rounded-xl border-2 border-dashed p-12 text-center cursor-pointer transition-all"
              style={{
                borderColor: isDragging ? "#3b5bdb" : "#1e3a5f",
                backgroundColor: isDragging ? "#1e3a8a22" : "#071525",
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.jsonl"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelect(file);
                }}
              />
              {uploadedFile ? (
                <div className="flex flex-col items-center gap-3">
                  <FileJson className="h-10 w-10" style={{ color: "#3b5bdb" }} />
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: "#93c5fd" }}>
                      {uploadedFile.name}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setUploadedFile(null);
                      }}
                      className="p-0.5 rounded-full"
                      style={{ color: "#64748b" }}
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <span className="text-xs" style={{ color: "#64748b" }}>
                    {(uploadedFile.size / 1024).toFixed(1)} KB
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-3">
                  <Upload className="h-10 w-10" style={{ color: "#334155" }} />
                  <div>
                    <p className="text-sm font-medium" style={{ color: "#94a3b8" }}>
                      Drag and drop your file here
                    </p>
                    <p className="text-xs mt-1" style={{ color: "#64748b" }}>
                      Supports .json and .jsonl files
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error display */}
        {error && (
          <div
            className="mt-4 p-4 rounded-lg flex items-start gap-3"
            style={{ backgroundColor: "#450a0a", border: "1px solid #7f1d1d" }}
          >
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" style={{ color: "#f87171" }} />
            <div>
              <p className="text-sm font-medium" style={{ color: "#fca5a5" }}>
                {error}
              </p>
              {validationErrors.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {validationErrors.map((ve, i) => (
                    <li key={i} className="text-xs" style={{ color: "#fca5a5" }}>
                      <span className="font-mono" style={{ color: "#f87171" }}>
                        {ve.loc.join(" → ")}
                      </span>
                      {": "}
                      {ve.msg}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="mt-6 w-full py-3.5 rounded-xl font-semibold text-base flex items-center justify-center gap-2 transition-all"
          style={
            loading
              ? { backgroundColor: "#1e3a8a", color: "#93c5fd", cursor: "not-allowed" }
              : { backgroundColor: "#3b5bdb", color: "#fff" }
          }
        >
          {loading ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" />
              Analyzing…
            </>
          ) : (
            <>
              <Search className="h-5 w-5" />
              Analyze Estimate
              <ChevronRight className="h-5 w-5" />
            </>
          )}
        </button>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {FEATURES.map((f) => (
          <div
            key={f.title}
            className="rounded-xl p-6"
            style={{
              backgroundColor: "#0f1f3d",
              border: "1px solid #1e3a5f",
            }}
          >
            <div className="mb-3">{f.icon}</div>
            <h3 className="text-sm font-semibold mb-1.5" style={{ color: "#f1f5f9" }}>
              {f.title}
            </h3>
            <p className="text-xs leading-relaxed" style={{ color: "#64748b" }}>
              {f.desc}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

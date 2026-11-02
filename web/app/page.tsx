"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, useInView } from "framer-motion";
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
  BarChart2,
  CheckCircle,
  Brain,
  Lock,
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
// Sample estimates for immediate testing
// ---------------------------------------------------------------------------

const SAMPLE_INFLATED_LABOR: Estimate = {
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
      description: "R&R rear bumper cover assembly",
      part: { name: "bumper cover", oem_price: 285.0, billed_price: 285.0, source: "OEM" },
      labor_hours_billed: 2.5,
      labor_hours_book: 2.5,
      labor_rate: 78.0,
    },
    {
      line_id: 2,
      operation: "Replace",
      panel: "left_taillight",
      description: "Replace left taillight assembly",
      part: { name: "taillight assembly", oem_price: 320.0, billed_price: 320.0, source: "OEM" },
      labor_hours_billed: 1.0,
      labor_hours_book: 1.0,
      labor_rate: 78.0,
    },
    {
      line_id: 3,
      operation: "Repair",
      panel: "trunk_lid",
      description: "Repair trunk lid panel dents",
      part: null,
      labor_hours_billed: 8.5,
      labor_hours_book: 2.0,
      labor_rate: 78.0,
    },
  ],
};

const SAMPLE_CLEAN: Estimate = {
  estimate_id: "EST-CLEAN-001",
  shop_id: "SHOP-088",
  region: "northeast",
  vehicle: {
    year: 2023,
    make: "Toyota",
    model: "Camry",
    trim: "LE",
    mileage: 18200,
    class: "mid-size",
  },
  scenario: "front_impact",
  line_items: [
    {
      line_id: 1,
      operation: "R&R",
      panel: "front_bumper",
      description: "R&R front bumper cover assembly",
      part: { name: "front bumper cover", oem_price: 380.0, billed_price: 380.0, source: "OEM" },
      labor_hours_billed: 2.8,
      labor_hours_book: 2.8,
      labor_rate: 75.0,
    },
    {
      line_id: 2,
      operation: "Replace",
      panel: "right_headlight",
      description: "Replace passenger side LED headlight",
      part: { name: "headlight assembly", oem_price: 410.0, billed_price: 410.0, source: "OEM" },
      labor_hours_billed: 1.2,
      labor_hours_book: 1.2,
      labor_rate: 75.0,
    },
    {
      line_id: 3,
      operation: "Repair",
      panel: "hood",
      description: "Repair minor crease at leading hood edge",
      part: null,
      labor_hours_billed: 2.5,
      labor_hours_book: 2.5,
      labor_rate: 75.0,
    },
  ],
};

const SAMPLE_PARTS_MARKUP: Estimate = {
  estimate_id: "EST-MARKUP-001",
  shop_id: "SHOP-129",
  region: "southwest",
  vehicle: {
    year: 2022,
    make: "Ford",
    model: "F-150",
    trim: "XL",
    mileage: 34000,
    class: "truck",
  },
  scenario: "side_swipe",
  line_items: [
    {
      line_id: 1,
      operation: "Replace",
      panel: "left_door_front",
      description: "Replace driver front door shell (OEM markup)",
      part: { name: "front door shell", oem_price: 650.0, billed_price: 1040.0, source: "OEM" },
      labor_hours_billed: 4.0,
      labor_hours_book: 3.8,
      labor_rate: 82.0,
    },
    {
      line_id: 2,
      operation: "Refinish",
      panel: "roof",
      description: "Refinish roof panel (non-adjacent panel)",
      part: null,
      labor_hours_billed: 3.5,
      labor_hours_book: 2.0,
      labor_rate: 82.0,
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
// Animated counter
// ---------------------------------------------------------------------------

function AnimatedCounter({
  value,
  suffix = "",
  duration = 1600,
}: {
  value: number;
  suffix?: string;
  duration?: number;
}) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    const update = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(eased * value));
      if (progress < 1) requestAnimationFrame(update);
    };
    requestAnimationFrame(update);
  }, [inView, value, duration]);

  return (
    <span ref={ref}>
      {display.toLocaleString()}
      {suffix}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Stats data
// ---------------------------------------------------------------------------

const STATS = [
  { label: "PR-AUC", value: 98.3, suffix: "%", desc: "Out-of-sample PR-AUC (CV 0.980)" },
  { label: "Estimates Trained", value: 50000, suffix: "+", desc: "CIECA BMS synthetic records" },
  { label: "Fraud Patterns", value: 6, suffix: "", desc: "Labor, parts, phantom & more" },
  { label: "Avg Latency", value: 28, suffix: " ms", desc: "Real-time API inference" },
];

// ---------------------------------------------------------------------------
// Feature cards
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: <Search className="h-7 w-7" style={{ color: "#0066cc" }} />,
    title: "6 Fraud Patterns Detected",
    desc: "Labor inflation, parts mark-up, phantom operations, duplicate lines, inconsistent hours, and unrelated repairs — all flagged in real time.",
    color: "#e8f1fb",
  },
  {
    icon: <Shield className="h-7 w-7" style={{ color: "#0066cc" }} />,
    title: "Shop-Level Analysis",
    desc: "Tracks fraud history across all submissions from the same shop to surface repeat offenders across your network.",
    color: "#e8f1fb",
  },
  {
    icon: <Brain className="h-7 w-7" style={{ color: "#0066cc" }} />,
    title: "SHAP Explainability",
    desc: "Every decision is backed by SHAP values so adjusters understand exactly why each flag was raised — no black boxes.",
    color: "#e8f1fb",
  },
  {
    icon: <Zap className="h-7 w-7" style={{ color: "#f97316" }} />,
    title: "28 ms Real-Time API",
    desc: "Sub-30 ms inference over a FastAPI backend — fast enough for inline adjuster workflows and bulk batch processing.",
    color: "#fff7ed",
  },
  {
    icon: <BarChart2 className="h-7 w-7" style={{ color: "#16a34a" }} />,
    title: "Enterprise Metrics Dashboard",
    desc: "Live confusion matrix, PR curve, per-fraud-type recall, and SHAP feature importance — all accessible in one dashboard.",
    color: "#f0fdf4",
  },
  {
    icon: <Lock className="h-7 w-7" style={{ color: "#7c3aed" }} />,
    title: "CIECA BMS Native Schema",
    desc: "Built natively on CIECA BMS line-item schemas and CCC ONE estimate structures used across the P&C insurance industry.",
    color: "#faf5ff",
  },
];

// ---------------------------------------------------------------------------
// Trust badges
// ---------------------------------------------------------------------------

const TRUST = [
  { label: "CIECA BMS", sub: "Native Schema" },
  { label: "XGBoost", sub: "Classifier" },
  { label: "GroupKFold", sub: "Zero Shop Leakage" },
  { label: "SHAP", sub: "Explainable AI" },
  { label: "P&C Insurance", sub: "Industry Standard" },
];

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"paste" | "upload">("paste");
  const [jsonText, setJsonText] = useState(() =>
    JSON.stringify(SAMPLE_INFLATED_LABOR, null, 2)
  );
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingSeconds, setLoadingSeconds] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLDivElement>(null);

  // ── Timer for slow Render free-tier cold starts ─────────────────────────
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (loading) {
      setLoadingSeconds(0);
      timer = setInterval(() => {
        setLoadingSeconds((s) => s + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [loading]);

  // ── Fill preset samples ──────────────────────────────────────────────────
  const loadPreset = (preset: Estimate) => {
    setJsonText(JSON.stringify(preset, null, 2));
    setError(null);
    setValidationErrors([]);
  };

  // ── Scroll to form ───────────────────────────────────────────────────────
  const scrollToForm = () => {
    formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
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

      const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
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
    <div className="bg-white">
      {/* ─────────────────── HERO ─────────────────────────────────────────── */}
      <section className="relative overflow-hidden hero-gradient-light pt-20 pb-28">
        {/* Decorative circles */}
        <div
          className="absolute top-[-120px] right-[-120px] w-[500px] h-[500px] rounded-full opacity-10"
          style={{ background: "radial-gradient(circle, #4d9be8 0%, transparent 70%)" }}
          aria-hidden="true"
        />
        <div
          className="absolute bottom-[-80px] left-[-80px] w-[350px] h-[350px] rounded-full opacity-8"
          style={{ background: "radial-gradient(circle, #0066cc 0%, transparent 70%)" }}
          aria-hidden="true"
        />

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold mb-8 border"
            style={{
              backgroundColor: "rgba(77,155,232,0.12)",
              borderColor: "rgba(77,155,232,0.3)",
              color: "#93c5fd",
            }}
          >
            <span
              className="relative w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: "#22c55e" }}
            >
              <span
                className="absolute inset-0 rounded-full animate-ping"
                style={{ backgroundColor: "#22c55e", opacity: 0.5 }}
              />
            </span>
            Live · XGBoost + SHAP · CIECA BMS · PR-AUC = 0.983
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight text-white leading-[1.08] mb-6"
          >
            AI Fraud Detection
            <br />
            <span className="gradient-text-light">for Auto Repair</span>
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed"
            style={{ color: "#93c5fd" }}
          >
            ClaimGuard analyzes auto repair estimates using a production XGBoost classifier
            trained on 50,000 CIECA BMS records — surfacing labor inflation, phantom parts,
            and pricing anomalies in under 30 ms.
          </motion.p>

          {/* CTA buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col sm:flex-row gap-4 justify-center items-center"
          >
            <button
              onClick={scrollToForm}
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold text-white transition-all hover:opacity-90 hover:shadow-xl hover:-translate-y-0.5"
              style={{ background: "linear-gradient(135deg,#0066cc,#4d9be8)" }}
            >
              <Search className="h-5 w-5" />
              Analyze an Estimate
              <ChevronRight className="h-5 w-5" />
            </button>
            <a
              href="/metrics"
              className="flex items-center gap-2 px-7 py-3.5 rounded-xl text-base font-semibold border transition-all hover:bg-white/10"
              style={{ color: "#93c5fd", borderColor: "rgba(147,197,253,0.35)" }}
            >
              <BarChart2 className="h-5 w-5" />
              View Model Metrics
            </a>
          </motion.div>
        </div>
      </section>

      {/* ─────────────────── STATS STRIP ─────────────────────────────────── */}
      <section className="border-y" style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-8">
            {STATS.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: [0.22, 1, 0.36, 1] }}
                className="text-center"
              >
                <div
                  className="text-4xl font-extrabold tracking-tight mb-1"
                  style={{ color: "#0d1b2e" }}
                >
                  <AnimatedCounter value={stat.value} suffix={stat.suffix} />
                </div>
                <div className="text-sm font-semibold" style={{ color: "#0066cc" }}>
                  {stat.label}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "#94a3b8" }}>
                  {stat.desc}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─────────────────── FEATURE CARDS ───────────────────────────────── */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-14"
          >
            <span
              className="text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full"
              style={{ backgroundColor: "#e8f1fb", color: "#0066cc" }}
            >
              Platform Capabilities
            </span>
            <h2
              className="text-3xl sm:text-4xl font-extrabold tracking-tight mt-4 mb-3"
              style={{ color: "#0d1b2e" }}
            >
              Built for the P&C Insurance Industry
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: "#475569" }}>
              From CIECA BMS line items to SHAP explanations — every component
              is designed for real adjuster workflows.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.5, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
                className="card-hover rounded-2xl p-7 border"
                style={{ backgroundColor: f.color, borderColor: "#e2e8f0" }}
              >
                <div
                  className="inline-flex p-3 rounded-xl mb-5"
                  style={{ backgroundColor: "rgba(255,255,255,0.7)" }}
                >
                  {f.icon}
                </div>
                <h3 className="text-base font-bold mb-2" style={{ color: "#0d1b2e" }}>
                  {f.title}
                </h3>
                <p className="text-sm leading-relaxed" style={{ color: "#475569" }}>
                  {f.desc}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ─────────────────── TRUST STRIP ─────────────────────────────────── */}
      <section
        className="py-8 border-y"
        style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
            {TRUST.map((t) => (
              <div key={t.label} className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 shrink-0" style={{ color: "#16a34a" }} />
                <span className="text-sm font-semibold" style={{ color: "#0d1b2e" }}>
                  {t.label}
                </span>
                <span className="text-xs" style={{ color: "#94a3b8" }}>
                  {t.sub}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─────────────────── ESTIMATE INTAKE FORM ────────────────────────── */}
      <section ref={formRef} className="py-20" style={{ backgroundColor: "#f8fafc" }}>
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
            className="text-center mb-10"
          >
            <span
              className="text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full"
              style={{ backgroundColor: "#e8f1fb", color: "#0066cc" }}
            >
              Fraud Analysis Engine
            </span>
            <h2
              className="text-3xl font-extrabold tracking-tight mt-4 mb-2"
              style={{ color: "#0d1b2e" }}
            >
              Submit an Estimate for Analysis
            </h2>
            <p className="text-sm" style={{ color: "#475569" }}>
              Paste or upload a CIECA BMS–formatted JSON estimate. Results returned in &lt;30 ms.
            </p>
          </motion.div>

          {/* Form card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
            className="bg-white rounded-2xl p-8 shadow-lg border"
            style={{ borderColor: "#e2e8f0" }}
          >
            {/* Tabs */}
            <div
              className="flex gap-1 p-1 rounded-xl mb-6 w-fit"
              style={{ backgroundColor: "#f1f5f9" }}
            >
              {(["paste", "upload"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => {
                    setActiveTab(tab);
                    setError(null);
                    setValidationErrors([]);
                  }}
                  className="px-5 py-2 rounded-lg text-sm font-medium capitalize transition-all"
                  style={
                    activeTab === tab
                      ? {
                          background: "linear-gradient(135deg,#0d1b2e,#0066cc)",
                          color: "#fff",
                          boxShadow: "0 2px 8px rgba(0,102,204,0.25)",
                        }
                      : { color: "#64748b", backgroundColor: "transparent" }
                  }
                >
                  {tab === "paste" ? "Paste JSON" : "Upload File"}
                </button>
              ))}
            </div>

            {/* Paste tab */}
            {activeTab === "paste" && (
              <div>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                  <label className="text-sm font-semibold" style={{ color: "#0d1b2e" }}>
                    Estimate JSON
                  </label>
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="text-xs text-slate-400 mr-1">Presets:</span>
                    <button
                      type="button"
                      onClick={() => loadPreset(SAMPLE_CLEAN)}
                      className="text-xs px-2.5 py-1 rounded-md font-semibold border transition-all hover:bg-emerald-50 text-emerald-700 border-emerald-200"
                    >
                      Clean (Low Risk)
                    </button>
                    <button
                      type="button"
                      onClick={() => loadPreset(SAMPLE_INFLATED_LABOR)}
                      className="text-xs px-2.5 py-1 rounded-md font-semibold border transition-all hover:bg-rose-50 text-rose-700 border-rose-200"
                    >
                      Inflated Labor (High)
                    </button>
                    <button
                      type="button"
                      onClick={() => loadPreset(SAMPLE_PARTS_MARKUP)}
                      className="text-xs px-2.5 py-1 rounded-md font-semibold border transition-all hover:bg-amber-50 text-amber-700 border-amber-200"
                    >
                      Parts Markup (Suspicious)
                    </button>
                  </div>
                </div>
                <textarea
                  value={jsonText}
                  onChange={(e) => setJsonText(e.target.value)}
                  rows={20}
                  spellCheck={false}
                  placeholder={`{\n  "estimate_id": "EST-001",\n  "shop_id": "SHOP-001",\n  ...\n}`}
                  className="w-full rounded-xl p-4 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-blue-300 border"
                  style={{
                    backgroundColor: "#f8fafc",
                    color: "#0d1b2e",
                    borderColor: "#e2e8f0",
                    caretColor: "#0066cc",
                  }}
                />
              </div>
            )}

            {/* Upload tab */}
            {activeTab === "upload" && (
              <div>
                <label className="text-sm font-semibold mb-2 block" style={{ color: "#0d1b2e" }}>
                  Upload Estimate File
                </label>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="rounded-2xl border-2 border-dashed p-14 text-center cursor-pointer transition-all"
                  style={{
                    borderColor: isDragging ? "#0066cc" : "#cbd5e1",
                    backgroundColor: isDragging ? "#e8f1fb" : "#f8fafc",
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
                      <FileJson className="h-10 w-10" style={{ color: "#0066cc" }} />
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold" style={{ color: "#0d1b2e" }}>
                          {uploadedFile.name}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploadedFile(null);
                          }}
                          className="p-0.5 rounded-full hover:bg-gray-200"
                          style={{ color: "#94a3b8" }}
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                      <span className="text-xs" style={{ color: "#94a3b8" }}>
                        {(uploadedFile.size / 1024).toFixed(1)} KB
                      </span>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-3">
                      <Upload className="h-10 w-10" style={{ color: "#94a3b8" }} />
                      <div>
                        <p className="text-sm font-semibold" style={{ color: "#475569" }}>
                          Drag and drop your file here
                        </p>
                        <p className="text-xs mt-1" style={{ color: "#94a3b8" }}>
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
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4 p-4 rounded-xl flex items-start gap-3 border"
                style={{ backgroundColor: "#fef2f2", borderColor: "#fecaca" }}
              >
                <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" style={{ color: "#dc2626" }} />
                <div>
                  <p className="text-sm font-semibold" style={{ color: "#dc2626" }}>
                    {error}
                  </p>
                  {validationErrors.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {validationErrors.map((ve, i) => (
                        <li key={i} className="text-xs" style={{ color: "#ef4444" }}>
                          <span className="font-mono">{ve.loc.join(" → ")}</span>
                          {": "}
                          {ve.msg}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </motion.div>
            )}

            {/* Submit button */}
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="mt-6 w-full py-4 rounded-xl font-bold text-base flex items-center justify-center gap-2 text-white transition-all hover:opacity-90 hover:shadow-xl hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed disabled:translate-y-0"
              style={{ background: "linear-gradient(135deg,#0d1b2e,#0066cc)" }}
            >
              {loading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  {loadingSeconds > 3
                    ? `Waking up server on Render... (${loadingSeconds}s)`
                    : "Analyzing Estimate…"}
                </>
              ) : (
                <>
                  <Search className="h-5 w-5" />
                  Analyze Estimate
                  <ChevronRight className="h-5 w-5" />
                </>
              )}
            </button>

            {/* Live demo wake-up note */}
            <div className="mt-4 p-3.5 rounded-xl border bg-slate-50 border-slate-200 flex items-start gap-2.5 text-xs text-slate-600">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse mt-1 shrink-0" />
              <div>
                <span className="font-semibold text-navy-900">Live Demo Cloud Notice: </span>
                Free-tier backend instances on Render spin down during idle periods. If your first request takes ~30 seconds, the container is waking up.
              </div>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}

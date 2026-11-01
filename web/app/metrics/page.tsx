"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity,
  Award,
  CheckCircle2,
  RefreshCw,
  Sliders,
  Calendar,
  Layers,
  AlertCircle,
} from "lucide-react";
import { MetricsCharts } from "@/components/MetricsCharts";

interface ModelInfoResponse {
  model_version: string;
  training_date: string;
  n_features: number;
  feature_names: string[];
  metrics: {
    precision: number;
    recall: number;
    f1: number;
    pr_auc: number;
    threshold?: number;
    per_fraud_type?: Record<string, { recall: number; count: number }>;
    confusion_matrix?: number[][];
    test_shop_count?: number;
    test_sample_count?: number;
    eval_date?: string;
  };
  best_params: Record<string, string | number | boolean>;
}

const STAT_CARDS = [
  {
    key: "f1" as const,
    label: "F1 Score",
    sub: "Target: ≥ 0.850 on held-out shops",
    icon: Award,
    color: "#16a34a",
    bg: "#f0fdf4",
    border: "#bbf7d0",
  },
  {
    key: "pr_auc" as const,
    label: "PR-AUC",
    sub: "Precision-Recall Area under curve",
    icon: Activity,
    color: "#0066cc",
    bg: "#e8f1fb",
    border: "#c3d9f5",
  },
  {
    key: "precision" as const,
    label: "Precision",
    sub: "At optimal fraud threshold",
    icon: CheckCircle2,
    color: "#7c3aed",
    bg: "#faf5ff",
    border: "#ddd6fe",
  },
  {
    key: "recall" as const,
    label: "Recall",
    sub: "Overall fraud detection coverage",
    icon: Activity,
    color: "#d97706",
    bg: "#fffbeb",
    border: "#fde68a",
  },
];

export default function MetricsPage() {
  const [data, setData] = useState<ModelInfoResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchModelInfo = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/model-info`);
      if (!res.ok) {
        throw new Error(`API returned ${res.status}: ${res.statusText}`);
      }
      const json: ModelInfoResponse = await res.json();
      setData(json);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to connect to ClaimGuard prediction service."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelInfo();
  }, []);

  return (
    <div className="bg-white min-h-screen">
      {/* Page hero strip */}
      <div
        className="border-b py-12"
        style={{
          background: "linear-gradient(135deg, #0d1b2e 0%, #0f2a5c 100%)",
          borderColor: "#1b3a6b",
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5"
          >
            <div>
              <span
                className="text-xs font-bold uppercase tracking-wider px-3 py-1 rounded-full inline-block mb-4"
                style={{ backgroundColor: "rgba(77,155,232,0.18)", color: "#93c5fd" }}
              >
                Model Performance · CIECA BMS Benchmark
              </span>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-2">
                Classifier &amp; Explainer Evaluation
              </h1>
              <p className="text-sm" style={{ color: "#93c5fd" }}>
                Evaluated on held-out repair shop clusters with zero shop leakage across GroupKFold splits.
              </p>
            </div>

            <button
              onClick={fetchModelInfo}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold border transition-all hover:opacity-80 disabled:opacity-50 shrink-0"
              style={{
                borderColor: "rgba(147,197,253,0.3)",
                color: "#93c5fd",
                backgroundColor: "rgba(77,155,232,0.1)",
              }}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              Refresh Metrics
            </button>
          </motion.div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Loading state */}
        {loading && !data && (
          <div className="py-24 text-center">
            <div
              className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4"
              style={{ borderColor: "#0066cc", borderTopColor: "transparent" }}
            />
            <p className="text-sm" style={{ color: "#64748b" }}>
              Querying model artifacts from API...
            </p>
          </div>
        )}

        {/* Error state */}
        {error && !data && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-6 rounded-2xl border mb-8 flex items-start gap-4"
            style={{ backgroundColor: "#fef2f2", borderColor: "#fecaca" }}
          >
            <AlertCircle className="h-6 w-6 shrink-0 mt-0.5" style={{ color: "#dc2626" }} />
            <div>
              <h3 className="text-sm font-bold" style={{ color: "#dc2626" }}>
                Could not retrieve model metrics
              </h3>
              <p className="text-xs mt-1" style={{ color: "#ef4444" }}>
                {error}
              </p>
              <p className="text-xs mt-2" style={{ color: "#64748b" }}>
                Ensure the FastAPI service is running (uvicorn api.main:app) and the model has been trained.
              </p>
            </div>
          </motion.div>
        )}

        {/* Main content */}
        {data && (
          <div className="space-y-8">
            {/* KPI cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {STAT_CARDS.map((card, i) => {
                const Icon = card.icon;
                const val = data.metrics[card.key] ?? 0;
                return (
                  <motion.div
                    key={card.key}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.45, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
                    className="p-6 rounded-2xl border"
                    style={{ backgroundColor: card.bg, borderColor: card.border }}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span
                        className="text-xs font-bold uppercase tracking-wider"
                        style={{ color: card.color }}
                      >
                        {card.label}
                      </span>
                      <div
                        className="p-1.5 rounded-lg"
                        style={{ backgroundColor: "rgba(255,255,255,0.7)" }}
                      >
                        <Icon className="h-4 w-4" style={{ color: card.color }} />
                      </div>
                    </div>
                    <div
                      className="text-3xl font-extrabold font-mono tracking-tight"
                      style={{ color: card.color }}
                    >
                      {val.toFixed(3)}
                    </div>
                    <p className="text-xs mt-1.5" style={{ color: "#64748b" }}>
                      {card.sub}
                      {card.key === "precision" && data.metrics.threshold !== undefined && (
                        <span className="ml-1">({data.metrics.threshold})</span>
                      )}
                    </p>
                  </motion.div>
                );
              })}
            </div>

            {/* Charts */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.35 }}
            >
              <MetricsCharts
                metrics={data.metrics}
                featureNames={data.feature_names}
              />
            </motion.div>

            {/* Model Info Details */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.45 }}
              className="p-7 rounded-2xl border"
              style={{ backgroundColor: "#f8fafc", borderColor: "#e2e8f0" }}
            >
              <h3
                className="text-base font-bold mb-5 flex items-center gap-2"
                style={{ color: "#0d1b2e" }}
              >
                <Sliders className="h-5 w-5" style={{ color: "#0066cc" }} />
                Model Architecture &amp; Training Metadata
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-sm">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider mb-1.5" style={{ color: "#94a3b8" }}>
                    Classifier
                  </p>
                  <p className="font-semibold" style={{ color: "#0d1b2e" }}>
                    XGBoost Binary Classifier
                  </p>
                  <p className="text-xs mt-0.5" style={{ color: "#64748b" }}>
                    tree_method=hist · GroupKFold
                  </p>
                  <div className="flex items-center gap-2 mt-2.5 text-xs" style={{ color: "#94a3b8" }}>
                    <Calendar className="h-3.5 w-3.5" />
                    Trained: {data.training_date}
                  </div>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-wider mb-1.5" style={{ color: "#94a3b8" }}>
                    Feature Dimensionality
                  </p>
                  <p className="font-semibold flex items-center gap-1.5" style={{ color: "#0d1b2e" }}>
                    <Layers className="h-4 w-4" style={{ color: "#0066cc" }} />
                    {data.n_features} Featurized Predictors
                  </p>
                  <p className="text-xs mt-1" style={{ color: "#64748b" }}>
                    Line aggregates, ratios, RapidFuzz similarity, one-hot ops
                  </p>
                </div>

                <div>
                  <p className="text-xs font-bold uppercase tracking-wider mb-1.5" style={{ color: "#94a3b8" }}>
                    Optimal Hyperparameters
                  </p>
                  <div
                    className="font-mono text-xs space-y-1.5 rounded-xl border p-3"
                    style={{ backgroundColor: "#ffffff", borderColor: "#e2e8f0" }}
                  >
                    {Object.entries(data.best_params).map(([k, v]) => (
                      <div key={k} className="flex justify-between gap-4">
                        <span style={{ color: "#94a3b8" }}>{k}:</span>
                        <span className="font-semibold" style={{ color: "#0066cc" }}>
                          {String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
}

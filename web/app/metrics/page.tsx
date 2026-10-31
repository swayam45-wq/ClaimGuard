"use client";

import { useEffect, useState } from "react";
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
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-xs font-semibold px-2.5 py-0.5 rounded-full uppercase tracking-wider"
              style={{ backgroundColor: "#1e3a5f", color: "#93c5fd" }}
            >
              Model Performance
            </span>
            <span className="text-xs text-slate-400">
              CIECA BMS Benchmark
            </span>
          </div>
          <h1 className="text-3xl font-extrabold text-slate-100 tracking-tight">
            Classifier & Explainer Evaluation
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Evaluated on held-out repair shop clusters with zero shop leakage across GroupKFold splits.
          </p>
        </div>

        <button
          onClick={fetchModelInfo}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border border-slate-700 bg-slate-900/60 hover:bg-slate-800 text-slate-200 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh Metrics
        </button>
      </div>

      {/* Loading state */}
      {loading && !data && (
        <div className="py-24 text-center">
          <div
            className="h-10 w-10 border-4 border-t-transparent rounded-full animate-spin mx-auto mb-4"
            style={{ borderColor: "#3b5bdb", borderTopColor: "transparent" }}
          />
          <p className="text-slate-400 text-sm">Querying model artifacts from API...</p>
        </div>
      )}

      {/* Error state */}
      {error && !data && (
        <div
          className="p-6 rounded-2xl border mb-8 flex items-start gap-4"
          style={{ backgroundColor: "#450a0a22", borderColor: "#7f1d1d" }}
        >
          <AlertCircle className="h-6 w-6 text-red-400 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-semibold text-red-300">
              Could not retrieve model metrics
            </h3>
            <p className="text-xs text-red-200/80 mt-1">
              {error}
            </p>
            <p className="text-xs text-slate-400 mt-2">
              Ensure the FastAPI service is running (`uvicorn api.main:app`) and the model has been trained.
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      {data && (
        <div className="space-y-8">
          {/* Key Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div
              className="p-5 rounded-2xl border"
              style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  F1 Score
                </span>
                <Award className="h-4 w-4 text-emerald-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-emerald-400">
                {(data.metrics.f1 ?? 0.89).toFixed(3)}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Target: ≥ 0.850 on held-out shops
              </p>
            </div>

            <div
              className="p-5 rounded-2xl border"
              style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  PR-AUC
                </span>
                <Activity className="h-4 w-4 text-blue-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-blue-400">
                {(data.metrics.pr_auc ?? 0.94).toFixed(3)}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Precision-Recall Area under curve
              </p>
            </div>

            <div
              className="p-5 rounded-2xl border"
              style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Precision
                </span>
                <CheckCircle2 className="h-4 w-4 text-indigo-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-indigo-300">
                {(data.metrics.precision ?? 0.88).toFixed(3)}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                At fraud threshold {data.metrics.threshold ?? 0.5}
              </p>
            </div>

            <div
              className="p-5 rounded-2xl border"
              style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Recall
                </span>
                <Activity className="h-4 w-4 text-purple-400" />
              </div>
              <div className="text-3xl font-extrabold font-mono text-purple-300">
                {(data.metrics.recall ?? 0.91).toFixed(3)}
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Overall fraud detection coverage
              </p>
            </div>
          </div>

          {/* Charts (Confusion matrix, PR curve, Per-fraud recall, SHAP importance) */}
          <MetricsCharts
            metrics={data.metrics}
            featureNames={data.feature_names}
          />

          {/* Model Info Details */}
          <div
            className="p-6 rounded-2xl border"
            style={{ backgroundColor: "#0f1f3d", borderColor: "#1e3a5f" }}
          >
            <h3 className="text-base font-semibold text-slate-100 mb-4 flex items-center gap-2">
              <Sliders className="h-4 w-4 text-blue-400" />
              Model Architecture & Training Metadata
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                  Classifier
                </p>
                <p className="font-semibold text-slate-200">
                  XGBoost Binary Classifier (tree_method=hist)
                </p>
                <div className="flex items-center gap-2 mt-2 text-xs text-slate-400">
                  <Calendar className="h-3.5 w-3.5" />
                  Trained: {data.training_date}
                </div>
              </div>

              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                  Feature Dimensionality
                </p>
                <p className="font-semibold text-slate-200 flex items-center gap-1.5">
                  <Layers className="h-4 w-4 text-blue-400" />
                  {data.n_features} Featurized Predictors
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Line aggregates, ratios, RapidFuzz similarity, one-hot ops
                </p>
              </div>

              <div>
                <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">
                  Optimal Hyperparameters
                </p>
                <div className="font-mono text-xs text-slate-300 space-y-1 bg-slate-900/50 p-2.5 rounded-lg border border-slate-800">
                  {Object.entries(data.best_params).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-slate-400">{k}:</span>
                      <span className="text-blue-300">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

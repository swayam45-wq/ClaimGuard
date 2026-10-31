# web

ClaimGuard Next.js 14 Dashboard.

Built with Next.js 14 (App Router), TypeScript, Tailwind CSS, and Recharts.

## Architecture

- `app/layout.tsx` — Dark, responsive layout with top navigation
- `app/page.tsx` — Estimate Intake (paste JSON with sample loader or upload .json/.jsonl)
- `app/results/[id]/page.tsx` — Analysis results with VerdictBanner, Fraud Gauge, Line Items table, and SHAP-explained expandable flagged line accordions
- `app/metrics/page.tsx` — Real-time model evaluation metrics (F1, PR-AUC, Confusion Matrix, Per-Fraud-Type Recall, SHAP importance)
- `components/` — Modular components: `VerdictBanner`, `FlaggedLine`, `ConfidenceBar`, `EstimateViewer`, `MetricsCharts`

## Running Locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Configuration

Set `NEXT_PUBLIC_API_URL` to point to the running FastAPI service (defaults to `http://localhost:8000`).

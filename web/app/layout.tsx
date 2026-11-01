import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import { Shield, BarChart2, Home, ChevronRight } from "lucide-react";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "ClaimGuard — AI Fraud Detection for Auto Repair Estimates",
  description:
    "AI-powered fraud detection for P&C insurance auto repair estimates, built on CIECA BMS standards.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-white text-navy-900 antialiased">
        {/* ── Top Navigation ─────────────────────────────────────── */}
        <header className="sticky top-0 z-50 bg-white nav-shadow border-b border-gray-100">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              {/* Logo */}
              <Link
                href="/"
                className="flex items-center gap-2.5 group"
                aria-label="ClaimGuard home"
              >
                <div
                  className="p-1.5 rounded-lg group-hover:scale-105"
                  style={{
                    background: "linear-gradient(135deg,#0d1b2e,#0066cc)",
                    transition: "transform 0.2s cubic-bezier(0.22,1,0.36,1)",
                  }}
                >
                  <Shield className="h-5 w-5 text-white" strokeWidth={2.5} />
                </div>
                <span className="text-lg font-bold tracking-tight text-navy-900">
                  Claim
                  <span style={{ color: "#0066cc" }}>Guard</span>
                </span>
              </Link>

              {/* Nav links */}
              <nav className="flex items-center gap-1" aria-label="Main navigation">
                <NavLink href="/" icon={<Home className="h-4 w-4" />} label="Home" />
                <NavLink
                  href="/metrics"
                  icon={<BarChart2 className="h-4 w-4" />}
                  label="Model Metrics"
                />
              </nav>

              {/* CTA button */}
              <Link
                href="/"
                className="hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90 hover:shadow-md"
                style={{ background: "linear-gradient(135deg,#0d1b2e,#0066cc)" }}
              >
                Analyze Estimate
                <ChevronRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </header>

        {/* ── Page content ────────────────────────────────────────── */}
        <main className="min-h-[calc(100vh-4rem)]">{children}</main>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <footer style={{ backgroundColor: "#0d1b2e" }}>
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-10">
              {/* Brand column */}
              <div>
                <div className="flex items-center gap-2.5 mb-4">
                  <div
                    className="p-1.5 rounded-lg"
                    style={{ background: "linear-gradient(135deg,#1b3a6b,#0066cc)" }}
                  >
                    <Shield className="h-5 w-5 text-white" strokeWidth={2.5} />
                  </div>
                  <span className="text-lg font-bold text-white">
                    Claim<span style={{ color: "#4d9be8" }}>Guard</span>
                  </span>
                </div>
                <p className="text-sm leading-relaxed" style={{ color: "#94a3b8" }}>
                  AI-powered fraud detection for auto repair estimates in P&amp;C insurance,
                  modeled on CIECA BMS and CCC ONE standards.
                </p>
              </div>

              {/* Platform */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color: "#4d9be8" }}>
                  Platform
                </h4>
                <ul className="space-y-2 text-sm" style={{ color: "#94a3b8" }}>
                  <li><Link href="/" className="hover:text-white transition-colors">Estimate Intake</Link></li>
                  <li><Link href="/metrics" className="hover:text-white transition-colors">Model Metrics</Link></li>
                </ul>
              </div>

              {/* Tech */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color: "#4d9be8" }}>
                  Technology
                </h4>
                <ul className="space-y-2 text-sm" style={{ color: "#94a3b8" }}>
                  {["XGBoost Classifier", "SHAP Explainability", "27-Feature Matrix", "CIECA BMS Schema", "FastAPI Backend"].map((t) => (
                    <li key={t} className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full shrink-0" style={{ backgroundColor: "#0066cc" }} />
                      {t}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Bottom bar */}
            <div
              className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-3 border-t"
              style={{ borderColor: "#1b3a6b" }}
            >
              <p className="text-xs" style={{ color: "#64748b" }}>
                © {new Date().getFullYear()} ClaimGuard. All rights reserved.
              </p>
              <div className="flex items-center gap-1.5 text-xs" style={{ color: "#64748b" }}>
                <Shield className="h-3.5 w-3.5" style={{ color: "#4d9be8" }} />
                <span>F1&thinsp;=&thinsp;0.968 · PR-AUC&thinsp;=&thinsp;0.982 · 28 ms latency</span>
              </div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}

function NavLink({
  href,
  icon,
  label,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium text-gray-600 hover:text-navy-900 hover:bg-gray-100 transition-colors"
    >
      {icon}
      {label}
    </Link>
  );
}

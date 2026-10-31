import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import { Shield, BarChart2, Home } from "lucide-react";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ClaimGuard — AI Fraud Detection",
  description: "AI-powered fraud detection for auto repair estimates",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.className} min-h-screen`}
        style={{ backgroundColor: "#0f172a", color: "#e2e8f0" }}
      >
        {/* Top Navigation */}
        <nav
          className="sticky top-0 z-50 border-b"
          style={{
            backgroundColor: "#0c1526",
            borderColor: "#1e293b",
          }}
        >
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
                    backgroundColor: "#3b5bdb",
                    transition: "transform 0.15s ease",
                  }}
                >
                  <Shield className="h-5 w-5 text-white" strokeWidth={2.5} />
                </div>
                <span
                  className="text-lg font-bold tracking-tight"
                  style={{ color: "#f1f5f9" }}
                >
                  Claim
                  <span style={{ color: "#3b5bdb" }}>Guard</span>
                </span>
              </Link>

              {/* Nav Links */}
              <div className="flex items-center gap-1">
                <NavLink href="/" icon={<Home className="h-4 w-4" />} label="Home" />
                <NavLink
                  href="/metrics"
                  icon={<BarChart2 className="h-4 w-4" />}
                  label="Metrics"
                />
              </div>
            </div>
          </div>
        </nav>

        {/* Page content */}
        <main className="min-h-[calc(100vh-4rem)]">{children}</main>

        {/* Footer */}
        <footer
          className="border-t mt-16 py-6"
          style={{ borderColor: "#1e293b" }}
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
            <p className="text-sm" style={{ color: "#64748b" }}>
              © {new Date().getFullYear()} ClaimGuard. AI-powered fraud detection.
            </p>
            <div className="flex items-center gap-1" style={{ color: "#64748b" }}>
              <Shield className="h-3.5 w-3.5" />
              <span className="text-xs">Powered by XGBoost + SHAP</span>
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
      className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:text-slate-100 hover:bg-slate-800/80 transition-colors"
    >
      {icon}
      {label}
    </Link>
  );
}

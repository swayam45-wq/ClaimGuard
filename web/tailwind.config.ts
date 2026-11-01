import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          50:  "#e8eef6",
          100: "#c6d4e8",
          200: "#9ab4d5",
          500: "#1b3a6b",
          700: "#0f2a5c",
          900: "#0d1b2e",
        },
        brand: {
          50:  "#e8f1fb",
          100: "#c3d9f5",
          400: "#4d9be8",
          500: "#0066cc",
          600: "#0055aa",
          700: "#004488",
        },
        orange: {
          400: "#fb923c",
          500: "#f97316",
          600: "#ea6c0b",
        },
        danger:  { 500: "#e03131", 600: "#c92a2a" },
        warning: { 500: "#f59f00", 600: "#e67700" },
        success: { 500: "#16a34a", 600: "#15803d" },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      animation: {
        "fade-in-up":   "fadeInUp 0.6s cubic-bezier(0.22,1,0.36,1) both",
        "fade-in":      "fadeIn 0.5s ease both",
        "scale-in":     "scaleIn 0.5s cubic-bezier(0.22,1,0.36,1) both",
        "slide-down":   "slideDown 0.35s cubic-bezier(0.22,1,0.36,1) both",
        "count-up":     "countUp 0.6s cubic-bezier(0.22,1,0.36,1) both",
        "shimmer":      "shimmer 1.5s linear infinite",
        "bar-fill":     "barFill 1.2s cubic-bezier(0.22,1,0.36,1) both",
        "pulse-ring":   "pulse-ring 1.5s ease-out infinite",
      },
      keyframes: {
        fadeInUp:    { from: { opacity: "0", transform: "translateY(28px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        fadeIn:      { from: { opacity: "0" }, to: { opacity: "1" } },
        scaleIn:     { from: { opacity: "0", transform: "scale(0.92)" }, to: { opacity: "1", transform: "scale(1)" } },
        slideDown:   { from: { opacity: "0", maxHeight: "0" }, to: { opacity: "1", maxHeight: "800px" } },
        countUp:     { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        shimmer:     { "0%": { backgroundPosition: "-200% center" }, "100%": { backgroundPosition: "200% center" } },
        barFill:     { from: { width: "0%" } },
        "pulse-ring": { "0%": { transform: "scale(1)", opacity: "0.6" }, "100%": { transform: "scale(1.6)", opacity: "0" } },
      },
    },
  },
  plugins: [],
};
export default config;

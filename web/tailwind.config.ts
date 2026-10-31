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
        brand: {
          50: "#f0f4ff",
          500: "#3b5bdb",
          600: "#3451c7",
          900: "#1a2a6c",
        },
        danger: { 500: "#e03131", 600: "#c92a2a" },
        warning: { 500: "#f59f00", 600: "#e67700" },
        success: { 500: "#2f9e44", 600: "#2b8a3e" },
      },
    },
  },
  plugins: [],
};
export default config;

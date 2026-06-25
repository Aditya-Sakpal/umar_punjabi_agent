/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0b0f14",
          panel: "#121820",
          border: "#1e2936",
          muted: "#64748b",
          accent: "#22d3ee",
          buy: "#34d399",
          sell: "#f87171",
          risk: "#fb923c",
          warn: "#fbbf24",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

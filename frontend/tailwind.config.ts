import type { Config } from "tailwindcss";

/**
 * Neumorphism (Soft UI), BustGuard edition. Every colour, shadow, radius and font comes from
 * the CSS variables in app/globals.css, so components never hard-code design values.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        fg: "var(--fg)",
        muted: "var(--muted)",
        placeholder: "var(--placeholder)",
        accent: { DEFAULT: "var(--accent)", light: "var(--accent-light)", text: "var(--accent-text)" },
        risk: {
          low: "var(--risk-low)",
          medium: "var(--risk-medium)",
          high: "var(--risk-high)",
          cw: "var(--risk-cw)",
          "low-text": "var(--risk-low-text)",
          "medium-text": "var(--risk-medium-text)",
          "high-text": "var(--risk-high-text)",
        },
        grid: "var(--grid)",
      },
      boxShadow: {
        neu: "var(--shadow-extruded)",
        "neu-hover": "var(--shadow-extruded-hover)",
        "neu-sm": "var(--shadow-extruded-sm)",
        "neu-inset": "var(--shadow-inset)",
        "neu-inset-deep": "var(--shadow-inset-deep)",
        "neu-inset-sm": "var(--shadow-inset-sm)",
        none: "none",
      },
      borderRadius: {
        card: "var(--radius-card)",
        panel: "var(--radius-panel)",
        control: "var(--radius-control)",
      },
      fontFamily: {
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
      },
      transitionDuration: { ui: "300ms", dial: "500ms" },
      keyframes: {
        "cw-pulse": {
          "0%, 100%": { boxShadow: "var(--shadow-inset-sm), 0 0 0 0 var(--cw-ring)" },
          "50%": { boxShadow: "var(--shadow-inset-sm), 0 0 0 4px var(--cw-ring)" },
        },
      },
      animation: { "cw-pulse": "cw-pulse 2s ease-out infinite" },
      minHeight: { touch: "44px" },
      minWidth: { touch: "44px" },
    },
  },
  plugins: [],
};

export default config;

import type { Config } from "tailwindcss";

/**
 * Design tokens. Colours follow the product brief; chart colours live in
 * lib/chart-theme.ts so charts and UI share one palette.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    screens: { sm: "640px", md: "768px", lg: "1024px", xl: "1280px", "2xl": "1536px" },
    extend: {
      colors: {
        // Match-centre look: near-black panels, red interface accent, gold / green team pair.
        bg: { DEFAULT: "#0B0C10", 2: "#111318", card: "#15171D", elev: "#1C1F27" },
        ink: { DEFAULT: "#ECEEF2", 2: "#A0A5B1", 3: "#6B7180" },
        line: { DEFAULT: "#262A33", soft: "#1D2028" },
        // "cyan" is the interface accent token used across the app (now red)
        cyan: { DEFAULT: "#E5394F", dim: "#8E2433" },
        violet: { DEFAULT: "#E9B23C" },
        emerald: { DEFAULT: "#33C17A" },
        amber: { DEFAULT: "#F2B53A" },
        danger: { DEFAULT: "#FF6B6B" },
        team: { a: "#E9B23C", b: "#33C17A" },
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"],
        display: ['"Space Grotesk Variable"', '"Space Grotesk"', "Inter", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      spacing: { 18: "4.5rem" },
      borderRadius: { card: "4px" },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.025) inset, 0 10px 30px -18px rgba(0,0,0,0.9)",
      },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [],
};
export default config;

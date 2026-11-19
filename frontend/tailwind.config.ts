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
        // Terminal look: black panels, amber interface accent, blue / red for the two sides.
        bg: { DEFAULT: "#050607", 2: "#0A0C0F", card: "#0D0F12", elev: "#15181D" },
        ink: { DEFAULT: "#E6E8EB", 2: "#9AA0A9", 3: "#626973" },
        line: { DEFAULT: "#22262C", soft: "#181B20" },
        // "cyan" is the interface accent token used across the app (now terminal amber)
        cyan: { DEFAULT: "#FF9F1C", dim: "#8A5510" },
        violet: { DEFAULT: "#4DA3FF" },
        emerald: { DEFAULT: "#2BD67B" },
        amber: { DEFAULT: "#F5D547" },
        danger: { DEFAULT: "#FF4D4F" },
        team: { a: "#4DA3FF", b: "#FF5C5C" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        display: ['"IBM Plex Sans Condensed"', '"IBM Plex Sans"', "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.04em" }],
      },
      spacing: { 18: "4.5rem" },
      borderRadius: { card: "2px" },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.025) inset, 0 10px 30px -18px rgba(0,0,0,0.9)",
      },
      transitionDuration: { DEFAULT: "150ms" },
    },
  },
  plugins: [],
};
export default config;

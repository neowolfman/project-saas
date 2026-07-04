export * from "./tokens.json";
export { default as tokens } from "./tokens.json";

export const palette = {
  bg: { base: "#0a0e14", raised: "#11161f", sunken: "#070a0f", overlay: "#161c28" },
  brand: { 400: "#5eead4", 500: "#2dd4bf", 600: "#14b8a6", contrast: "#04110f" },
  accent: { lime: "#a3e635", amber: "#fbbf24", violet: "#a78bfa" },
  semantic: { success: "#34d399", warning: "#fbbf24", danger: "#f87171", info: "#60a5fa" },
  data: ["#2dd4bf", "#a3e635", "#60a5fa", "#a78bfa", "#fbbf24", "#f87171"] as const,
} as const;

export const typeScale = {
  xs: "0.75rem",
  sm: "0.875rem",
  base: "1rem",
  lg: "1.125rem",
  xl: "1.375rem",
  "2xl": "1.75rem",
  "3xl": "2.25rem",
  "4xl": "3rem",
} as const;

export const space = {
  0: "0", 1: "0.25rem", 2: "0.5rem", 3: "0.75rem", 4: "1rem",
  5: "1.5rem", 6: "2rem", 7: "3rem", 8: "4rem",
} as const;

export const radius = {
  sm: "0.375rem", DEFAULT: "0.5rem", lg: "0.75rem", xl: "1rem", full: "9999px",
} as const;

export const zIndex = {
  base: 0, raised: 10, sticky: 20, drawer: 40, modal: 100, toast: 1000,
} as const;

export const motion = {
  fast: "150ms", base: "200ms", slow: "300ms",
  ease: "cubic-bezier(0.22, 1, 0.36, 1)",
} as const;

export const breakpoints = {
  sm: "640px", md: "768px", lg: "1024px", xl: "1280px", "2xl": "1440px",
} as const;

export const currency = { code: "CLP", locale: "es-CL", rateFromUSD: 950 } as const;

export const formatCLP = (value: number): string =>
  new Intl.NumberFormat(currency.locale, {
    style: "currency",
    currency: currency.code,
    maximumFractionDigits: 0,
  }).format(value);

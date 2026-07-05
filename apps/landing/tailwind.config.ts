import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
    "../../libs/design-system/src/**/*.{ts,tsx}",
    "../../libs/ui-tokens/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "var(--bg-base)",
          raised: "var(--bg-raised)",
          sunken: "var(--bg-sunken)",
          overlay: "var(--bg-overlay)",
        },
        surface: {
          DEFAULT: "var(--surface)",
          hover: "var(--surface-hover)",
          active: "var(--surface-active)",
        },
        line: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        fg: {
          primary: "var(--fg-primary)",
          secondary: "var(--fg-secondary)",
          muted: "var(--fg-muted)",
        },
        brand: {
          400: "var(--brand-400)",
          500: "var(--brand-500)",
          600: "var(--brand-600)",
          contrast: "var(--brand-contrast)",
        },
        accent: {
          lime: "var(--accent-lime)",
          amber: "var(--accent-amber)",
          violet: "var(--accent-violet)",
        },
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        info: "var(--info)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        "2xl": "calc(var(--radius-xl) * 1.25)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow)",
        glow: "var(--shadow-glow)",
      },
      transitionTimingFunction: {
        ease: "var(--ease)",
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        base: "var(--motion-base)",
        slow: "var(--motion-slow)",
      },
      maxWidth: {
        "7xl": "80rem",
      },
    },
  },
  plugins: [],
};

export default config;

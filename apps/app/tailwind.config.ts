import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "var(--bg-base)",
        raised: "var(--bg-raised)",
        sunken: "var(--bg-sunken)",
        overlay: "var(--bg-overlay)",
        surface: {
          DEFAULT: "var(--surface)",
          hover: "var(--surface-hover)",
          active: "var(--surface-active)",
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
      borderColor: {
        DEFAULT: "var(--border)",
        subtle: "var(--border-subtle)",
        strong: "var(--border-strong)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "JetBrains Mono", "monospace"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        DEFAULT: "var(--shadow)",
        glow: "var(--shadow-glow)",
      },
      transitionDuration: {
        fast: "var(--motion-fast)",
        DEFAULT: "var(--motion-base)",
        slow: "var(--motion-slow)",
      },
      transitionTimingFunction: {
        DEFAULT: "var(--ease)",
      },
    },
  },
  plugins: [],
};

export default config;

import { TIERS } from "@saas/design-system";
import RoiCalculator from "./roi-calculator";

const NAV_LINKS = [
  { href: "#producto", label: "Producto" },
  { href: "#pricing", label: "Pricing" },
  { href: "#docs", label: "Docs" },
];

const HERO_STATS = [
  { value: "30%", label: "Eficiencia operativa promedio" },
  { value: "99,99%", label: "SLA tier VIP" },
  { value: "<1s", label: "Latencia escritura ledger" },
];

const FEATURES = [
  {
    index: "01",
    title: "PM + FinOps convergentes",
    description:
      "Margen y SLA derivados de ledgers inmutables. Cada hora trabajada actualiza costo, ingreso y rentabilidad en tiempo real.",
    accent: "var(--brand-500)" as const,
  },
  {
    index: "02",
    title: "Aislamiento enterprise híbrido",
    description:
      "Schema compartido para escala y DB dedicada para VIP. Cumplimiento y aislamiento sin sacrificar velocidad de despliegue.",
    accent: "var(--accent-violet)" as const,
  },
  {
    index: "03",
    title: "Zero-friction para devs",
    description:
      "Registro de horas automático vía webhooks de Git. Commits y PRs se traducen en eventos financieros sin fricción.",
    accent: "var(--accent-lime)" as const,
  },
];

export default function LandingPage() {
  const year = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--fg-primary)]">
      <Navbar />
      <main>
        <Hero />
        <Features />
        <RoiSection />
        <Pricing />
        <CtaSection />
      </main>
      <Footer year={year} />
    </div>
  );
}

function Navbar() {
  return (
    <header className="sticky top-0 z-[var(--z-sticky)] border-b border-[var(--border-subtle)] bg-[var(--bg-base)]/80 backdrop-blur-md">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <a
          href="#"
          className="flex items-center gap-2.5 text-lg font-semibold tracking-tight"
        >
          <span className="tnum grid h-8 w-8 place-items-center rounded-lg bg-[var(--brand-500)] font-mono text-sm font-bold text-[var(--brand-contrast)]">
            P+
          </span>
          <span>
            PM<span className="text-[var(--brand-500)]">+</span>FinOps
          </span>
        </a>
        <div className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm text-[var(--fg-secondary)] transition-colors hover:text-[var(--fg-primary)]"
            >
              {link.label}
            </a>
          ))}
        </div>
        <a
          href="#cta"
          className="rounded-lg bg-[var(--brand-500)] px-4 py-2 text-sm font-medium text-[var(--brand-contrast)] transition-all hover:bg-[var(--brand-400)] hover:shadow-[var(--shadow-glow)]"
        >
          Comenzar
        </a>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden border-b border-[var(--border-subtle)]">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute left-1/2 top-[-8rem] h-[32rem] w-[60rem] -translate-x-1/2 rounded-full opacity-[0.18] blur-3xl"
          style={{
            background:
              "radial-gradient(closest-side, var(--brand-500), transparent)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              "linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)",
            backgroundSize: "48px 48px",
            maskImage:
              "radial-gradient(ellipse at center, black 40%, transparent 75%)",
          }}
        />
      </div>

      <div className="mx-auto max-w-7xl px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--bg-raised)] px-3 py-1 text-xs text-[var(--fg-secondary)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--brand-500)]" />
            Multi-tenant SaaS · Convergencia PM + FinOps
          </span>

          <h1 className="mt-6 text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            Cada hora trabajada es un{" "}
            <span className="text-[var(--brand-500)]">evento financiero</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-[var(--fg-secondary)] sm:text-lg">
            PM+FinOps unifica project management y operaciones financieras sobre
            ledgers inmutables. Margen, SLA y costos derivados automáticamente
            desde el trabajo real.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#cta"
              className="inline-flex w-full items-center justify-center rounded-lg bg-[var(--brand-500)] px-6 py-3 text-sm font-semibold text-[var(--brand-contrast)] transition-all hover:bg-[var(--brand-400)] hover:shadow-[var(--shadow-glow)] sm:w-auto"
            >
              Comenzar gratis
            </a>
            <a
              href="#producto"
              className="inline-flex w-full items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-raised)] px-6 py-3 text-sm font-semibold text-[var(--fg-primary)] transition-all hover:border-[var(--brand-500)] hover:bg-[var(--surface-hover)] sm:w-auto"
            >
              Ver demo
            </a>
          </div>

          <dl className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-px overflow-hidden rounded-xl border border-[var(--border-subtle)] bg-[var(--border-subtle)] sm:grid-cols-3">
            {HERO_STATS.map((stat) => (
              <div
                key={stat.label}
                className="bg-[var(--bg-raised)] px-6 py-6 text-center"
              >
                <dt className="sr-only">{stat.label}</dt>
                <dd>
                  <div className="tnum text-3xl font-bold tracking-tight text-[var(--fg-primary)] sm:text-4xl">
                    {stat.value}
                  </div>
                  <div className="mt-2 text-xs text-[var(--fg-muted)]">
                    {stat.label}
                  </div>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

function Features() {
  return (
    <section id="producto" className="border-b border-[var(--border-subtle)]">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <SectionHeading
          eyebrow="Tres pilares"
          title="Una plataforma, tres convergencias"
          subtitle="Diseñada para equipos que necesitan precisión financiera sin frenar la entrega."
        />

        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {FEATURES.map((feature) => (
            <article
              key={feature.index}
              className="group relative flex flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-6 transition-all hover:border-[var(--brand-500)] hover:bg-[var(--surface-hover)]"
            >
              <div
                className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-30"
                style={{
                  background: `radial-gradient(closest-side, ${feature.accent}, transparent)`,
                }}
              />
              <div className="relative">
                <div className="flex items-center justify-between">
                  <span
                    className="tnum font-mono text-sm font-semibold"
                    style={{ color: feature.accent }}
                  >
                    {feature.index}
                  </span>
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: feature.accent }}
                  />
                </div>
                <h3 className="mt-5 text-xl font-semibold tracking-tight text-[var(--fg-primary)]">
                  {feature.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-[var(--fg-secondary)]">
                  {feature.description}
                </p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

function RoiSection() {
  return (
    <section className="border-b border-[var(--border-subtle)] bg-[var(--bg-sunken)]">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <SectionHeading
          eyebrow="Calculadora de ROI"
          title="Cuánto puedes ahorrar"
          subtitle="Estima el ahorro mensual que genera la convergencia PM + FinOps en tu operación."
        />
        <div className="mt-14">
          <RoiCalculator />
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  return (
    <section id="pricing" className="border-b border-[var(--border-subtle)]">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <SectionHeading
          eyebrow="Pricing"
          title="Planes para cada nivel de aislamiento"
          subtitle="Desde multi-tenant compartido hasta DB dedicada para VIP. Precios en CLP."
        />

        <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {TIERS.map((tier) => (
            <PricingCard key={tier.id} tier={tier} />
          ))}
        </div>
      </div>
    </section>
  );
}

function PricingCard({
  tier,
}: {
  tier: (typeof TIERS)[number];
}) {
  const highlighted = Boolean(tier.highlight);
  return (
    <article
      className={`relative flex flex-col rounded-xl border p-6 transition-all ${
        highlighted
          ? "border-[var(--brand-500)] bg-[var(--bg-raised)] shadow-[var(--shadow-glow)]"
          : "border-[var(--border)] bg-[var(--bg-raised)] hover:border-[var(--brand-500)]/60 hover:bg-[var(--surface-hover)]"
      }`}
    >
      {highlighted ? (
        <span className="absolute -top-3 left-6 rounded-full bg-[var(--brand-500)] px-3 py-1 text-xs font-semibold text-[var(--brand-contrast)]">
          Más popular
        </span>
      ) : null}

      <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--fg-secondary)]">
        {tier.name}
      </h3>
      <div className="tnum mt-3 text-2xl font-bold tracking-tight text-[var(--fg-primary)]">
        {tier.priceLabel}
      </div>

      <ul className="mt-6 flex-1 space-y-3 border-t border-[var(--border-subtle)] pt-6">
        {tier.features.map((feature) => (
          <li
            key={feature}
            className="flex items-start gap-2.5 text-sm text-[var(--fg-secondary)]"
          >
            <svg
              aria-hidden="true"
              viewBox="0 0 20 20"
              className={`mt-0.5 h-4 w-4 flex-shrink-0 ${
                highlighted ? "text-[var(--brand-500)]" : "text-[var(--fg-muted)]"
              }`}
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M4 10.5l3.5 3.5L16 6"
              />
            </svg>
            <span>{feature}</span>
          </li>
        ))}
      </ul>

      <a
        href="#cta"
        className={`mt-6 inline-flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition-all ${
          highlighted
            ? "bg-[var(--brand-500)] text-[var(--brand-contrast)] hover:bg-[var(--brand-400)]"
            : "border border-[var(--border)] bg-[var(--bg-base)] text-[var(--fg-primary)] hover:border-[var(--brand-500)]"
        }`}
      >
        Elegir {tier.name}
      </a>
    </article>
  );
}

function CtaSection() {
  return (
    <section id="cta" className="border-b border-[var(--border-subtle)]">
      <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-24 lg:px-8">
        <div className="relative overflow-hidden rounded-2xl border border-[var(--brand-500)]/40 bg-[var(--bg-sunken)] px-6 py-16 text-center sm:px-12 sm:py-20">
          <div
            className="pointer-events-none absolute inset-0 -z-10 opacity-40"
            style={{
              background:
                "radial-gradient(60% 120% at 50% 0%, rgba(45,212,191,0.18), transparent 70%)",
            }}
          />
          <div
            className="pointer-events-none absolute left-1/2 top-0 -z-10 h-64 w-[40rem] -translate-x-1/2 opacity-25 blur-3xl"
            style={{
              background:
                "radial-gradient(closest-side, var(--brand-500), transparent)",
            }}
          />

          <h2 className="mx-auto max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
            ¿Listo para converger{" "}
            <span className="text-[var(--brand-500)]">PM y FinOps</span>?
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-base text-[var(--fg-secondary)]">
            Empieza gratis en minutos. Sin tarjeta de crédito.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#"
              className="inline-flex w-full items-center justify-center rounded-lg bg-[var(--brand-500)] px-6 py-3 text-sm font-semibold text-[var(--brand-contrast)] transition-all hover:bg-[var(--brand-400)] hover:shadow-[var(--shadow-glow)] sm:w-auto"
            >
              Comenzar gratis
            </a>
            <a
              href="#pricing"
              className="inline-flex w-full items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--bg-raised)] px-6 py-3 text-sm font-semibold text-[var(--fg-primary)] transition-all hover:border-[var(--brand-500)] sm:w-auto"
            >
              Ver pricing
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer({ year }: { year: number }) {
  return (
    <footer className="border-t border-[var(--border-subtle)] bg-[var(--bg-sunken)]">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <a
            href="#"
            className="flex items-center gap-2.5 text-base font-semibold tracking-tight"
          >
            <span className="tnum grid h-7 w-7 place-items-center rounded-md bg-[var(--brand-500)] font-mono text-xs font-bold text-[var(--brand-contrast)]">
              P+
            </span>
            <span className="text-[var(--fg-secondary)]">
              PM<span className="text-[var(--brand-500)]">+</span>FinOps
            </span>
          </a>

          <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-[var(--fg-secondary)]">
            <a href="#producto" className="transition-colors hover:text-[var(--fg-primary)]">
              Producto
            </a>
            <a href="#pricing" className="transition-colors hover:text-[var(--fg-primary)]">
              Pricing
            </a>
            <a href="#docs" className="transition-colors hover:text-[var(--fg-primary)]">
              Docs
            </a>
            <a href="#" className="transition-colors hover:text-[var(--fg-primary)]">
              Privacidad
            </a>
            <a href="#" className="transition-colors hover:text-[var(--fg-primary)]">
              Términos
            </a>
          </nav>
        </div>

        <div className="mt-8 border-t border-[var(--border-subtle)] pt-6 text-center text-xs text-[var(--fg-muted)]">
          <span className="tnum">© {year} PM+FinOps</span>
          <span className="mx-2">·</span>
          <span>FinOps Dark Design System</span>
        </div>
      </div>
    </footer>
  );
}

function SectionHeading({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--brand-500)]">
        {eyebrow}
      </span>
      <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
        {title}
      </h2>
      <p className="mt-4 text-base leading-relaxed text-[var(--fg-secondary)]">
        {subtitle}
      </p>
    </div>
  );
}

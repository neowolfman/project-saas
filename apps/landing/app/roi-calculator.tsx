"use client";

import { useMemo, useState } from "react";
import { formatCLP } from "@saas/ui-tokens";

const EFFICIENCY_GAIN = 0.3;

export default function RoiCalculator() {
  const [projects, setProjects] = useState(8);
  const [hoursPerProject, setHoursPerProject] = useState(120);
  const [costPerHour, setCostPerHour] = useState(35000);

  const { totalHours, monthlySavings } = useMemo(() => {
    const hours = Math.max(0, projects) * Math.max(0, hoursPerProject);
    const savings = hours * Math.max(0, costPerHour) * EFFICIENCY_GAIN;
    return { totalHours: hours, monthlySavings: savings };
  }, [projects, hoursPerProject, costPerHour]);

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
      <div className="space-y-5 rounded-xl border border-[var(--border)] bg-[var(--bg-raised)] p-6 sm:p-8">
        <NumberField
          id="roi-projects"
          label="Proyectos / mes"
          hint="Cantidad de proyectos activos por mes."
          value={projects}
          min={0}
          step={1}
          onChange={(v) => setProjects(v)}
        />
        <NumberField
          id="roi-hours"
          label="Horas promedio / proyecto"
          hint="Horas estimadas de trabajo por proyecto."
          value={hoursPerProject}
          min={0}
          step={10}
          onChange={(v) => setHoursPerProject(v)}
        />
        <NumberField
          id="roi-cost"
          label="Costo promedio / hora (CLP)"
          hint="Costo de la hora profesional en pesos chilenos."
          value={costPerHour}
          min={0}
          step={1000}
          onChange={(v) => setCostPerHour(v)}
        />
        <p className="text-xs leading-relaxed text-[var(--fg-muted)]">
          El ahorro se calcula como horas &times; costo &times;{" "}
          <span className="font-medium text-[var(--brand-500)]">30%</span> de
          ganancia de eficiencia.
        </p>
      </div>

      <div className="relative flex flex-col justify-between overflow-hidden rounded-xl border border-[var(--brand-500)]/40 bg-[var(--bg-sunken)] p-6 sm:p-8">
        <div
          className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full opacity-25 blur-3xl"
          style={{
            background:
              "radial-gradient(closest-side, var(--brand-500), transparent)",
          }}
        />
        <div className="relative">
          <span className="text-xs font-medium uppercase tracking-wider text-[var(--fg-secondary)]">
            Ahorro estimado mensual
          </span>
          <div className="tnum mt-3 text-4xl font-bold tracking-tight text-[var(--brand-400)] sm:text-5xl">
            {formatCLP(monthlySavings)}
          </div>
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-[var(--border-subtle)] pt-6">
            <Metric
              label="Horas totales / mes"
              value={
                <span className="tnum">{totalHours.toLocaleString("es-CL")}</span>
              }
            />
            <Metric
              label="Ganancia eficiencia"
              value={
                <span className="text-[var(--accent-lime)]">
                  +{EFFICIENCY_GAIN * 100}%
                </span>
              }
            />
          </div>
        </div>
      </div>
    </div>
  );
}

interface NumberFieldProps {
  id: string;
  label: string;
  hint?: string;
  value: number;
  min?: number;
  step?: number;
  onChange: (value: number) => void;
}

function NumberField({
  id,
  label,
  hint,
  value,
  min,
  step,
  onChange,
}: NumberFieldProps) {
  return (
    <div>
      <label
        htmlFor={id}
        className="block text-sm font-medium text-[var(--fg-primary)]"
      >
        {label}
      </label>
      {hint ? (
        <p className="mt-1 text-xs text-[var(--fg-muted)]">{hint}</p>
      ) : null}
      <div className="tnum mt-2 flex items-center rounded-lg border border-[var(--border)] bg-[var(--bg-base)] transition-colors focus-within:border-[var(--brand-500)] focus-within:shadow-[var(--shadow-glow)]">
        <input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="tnum w-full bg-transparent px-3 py-2.5 text-base text-[var(--fg-primary)] outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
        />
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-xs text-[var(--fg-muted)]">{label}</dt>
      <dd className="tnum mt-1 text-lg font-semibold text-[var(--fg-primary)]">
        {value}
      </dd>
    </div>
  );
}

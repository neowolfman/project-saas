import type { ComponentType } from "react";

type Tone = "brand" | "violet" | "lime" | "amber";
type TrendTone = "success" | "danger";
type Status = "Activo" | "En riesgo" | "Pausado";

const cn = (...xs: (string | false | null | undefined)[]): string => xs.filter(Boolean).join(" ");

type IconProps = { className?: string };

function Svg({ className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

const GridIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
  </Svg>
);

const FolderIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
  </Svg>
);

const CheckIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <polyline points="9 11 12 14 22 4" />
    <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
  </Svg>
);

const TrendIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <polyline points="3 17 9 11 13 15 21 7" />
    <polyline points="14 7 21 7 21 14" />
  </Svg>
);

const FileIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="8" y1="13" x2="16" y2="13" />
    <line x1="8" y1="17" x2="13" y2="17" />
  </Svg>
);

const SlidersIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <line x1="4" y1="21" x2="4" y2="14" />
    <line x1="4" y1="10" x2="4" y2="3" />
    <line x1="12" y1="21" x2="12" y2="12" />
    <line x1="12" y1="8" x2="12" y2="3" />
    <line x1="20" y1="21" x2="20" y2="16" />
    <line x1="20" y1="12" x2="20" y2="3" />
    <line x1="1" y1="14" x2="7" y2="14" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="17" y1="16" x2="23" y2="16" />
  </Svg>
);

const SearchIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="11" cy="11" r="7" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
  </Svg>
);

const BellIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
    <path d="M13.73 21a2 2 0 0 1-3.46 0" />
  </Svg>
);

const ChevronIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <polyline points="6 9 12 15 18 9" />
  </Svg>
);

const LayersIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </Svg>
);

const ClockIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <circle cx="12" cy="12" r="9" />
    <polyline points="12 7 12 12 15 14" />
  </Svg>
);

const PercentIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <line x1="19" y1="5" x2="5" y2="19" />
    <circle cx="6.5" cy="6.5" r="2.5" />
    <circle cx="17.5" cy="17.5" r="2.5" />
  </Svg>
);

const AlertIcon = ({ className }: IconProps) => (
  <Svg className={className}>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </Svg>
);

const nav: { label: string; active?: boolean; icon: ComponentType<IconProps> }[] = [
  { label: "Dashboard", active: true, icon: GridIcon },
  { label: "Proyectos", icon: FolderIcon },
  { label: "Tareas", icon: CheckIcon },
  { label: "FinOps", icon: TrendIcon },
  { label: "Reportes", icon: FileIcon },
  { label: "Configuración", icon: SlidersIcon },
];

const kpis: {
  label: string;
  value: string;
  trend: string;
  tone: Tone;
  trendTone: TrendTone;
  icon: ComponentType<IconProps>;
}[] = [
  { label: "Proyectos activos", value: "24", trend: "\u2191 12%", tone: "brand", trendTone: "success", icon: LayersIcon },
  { label: "Horas esta semana", value: "1.847h", trend: "\u2191 4,2%", tone: "violet", trendTone: "success", icon: ClockIcon },
  { label: "Margen promedio", value: "34,2%", trend: "\u2191 1,8 pp", tone: "lime", trendTone: "success", icon: PercentIcon },
  { label: "SLA en riesgo", value: "3", trend: "\u2191 2", tone: "amber", trendTone: "danger", icon: AlertIcon },
];

const projects: {
  proyecto: string;
  cliente: string;
  horas: string;
  costo: string;
  ingresos: string;
  margen: number;
  margenLabel: string;
  estado: Status;
}[] = [
  { proyecto: "API Redesign", cliente: "Acme Corp", horas: "124h", costo: "$4.640.000", ingresos: "$7.200.000", margen: 35.6, margenLabel: "35,6%", estado: "Activo" },
  { proyecto: "Cloud Migration", cliente: "Banco del Sur", horas: "310h", costo: "$11.780.000", ingresos: "$18.500.000", margen: 36.3, margenLabel: "36,3%", estado: "Activo" },
  { proyecto: "Mobile App", cliente: "Retail Norte", horas: "96h", costo: "$3.744.000", ingresos: "$4.100.000", margen: 8.7, margenLabel: "8,7%", estado: "En riesgo" },
  { proyecto: "Data Warehouse", cliente: "Grupo Minero", horas: "210h", costo: "$7.980.000", ingresos: "$11.300.000", margen: 29.4, margenLabel: "29,4%", estado: "Activo" },
  { proyecto: "Portal Empleados", cliente: "Municipal SV", horas: "58h", costo: "$2.178.000", ingresos: "$2.300.000", margen: 5.3, margenLabel: "5,3%", estado: "Pausado" },
];

const activity: { time: string; text: string; tone: Tone }[] = [
  { time: "hace 2h", text: "Mar\u00eda Gonz\u00e1lez registr\u00f3 2.5h en API Redesign", tone: "brand" },
  { time: "hace 3h", text: "Webhook Git: commit resuelve #142 [Time: 1h]", tone: "violet" },
  { time: "hace 5h", text: "Contrato \u2018Cloud Migration\u2019 actualizado", tone: "lime" },
  { time: "hace 6h", text: "Juan P\u00e9rez complet\u00f3 tarea \u2018Dise\u00f1o DB schema\u2019", tone: "brand" },
  { time: "hace 8h", text: "SLA alert: Proyecto \u2018Mobile App\u2019 al 85% del budget", tone: "amber" },
];

const toneMap: Record<Tone, string> = {
  brand: "bg-[#2dd4bf1a] text-brand-500",
  violet: "bg-[#a78bfa1a] text-accent-violet",
  lime: "bg-[#a3e6351a] text-accent-lime",
  amber: "bg-[#fbbf241a] text-accent-amber",
};

const dotMap: Record<Tone, string> = {
  brand: "bg-brand-500",
  violet: "bg-accent-violet",
  lime: "bg-accent-lime",
  amber: "bg-accent-amber",
};

const trendTone: Record<TrendTone, string> = {
  success: "text-success",
  danger: "text-danger",
};

const marginTone = (pct: number): { text: string } => {
  if (pct > 30) return { text: "text-success" };
  if (pct >= 15) return { text: "text-accent-amber" };
  return { text: "text-danger" };
};

const statusTone = (status: Status): string => {
  switch (status) {
    case "Activo":
      return "bg-[#34d3991a] text-success";
    case "En riesgo":
      return "bg-[#fbbf241a] text-accent-amber";
    case "Pausado":
      return "bg-[#9aa7bd1a] text-fg-secondary";
  }
};

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-base text-fg-primary">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-subtle bg-raised">
        <div className="flex h-16 items-center gap-2.5 border-b border-subtle px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-brand-500 text-base font-bold text-brand-contrast">
            +
          </div>
          <div className="text-sm font-semibold tracking-tight">
            <span className="text-fg-primary">PM</span>
            <span className="text-brand-500">+FinOps</span>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <p className="px-3 pb-2 pt-2 text-[10px] font-semibold uppercase tracking-wider text-fg-muted">
            Operación
          </p>
          {nav.map((item) => (
            <a
              key={item.label}
              href="#"
              className={cn(
                "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors duration-fast",
                item.active
                  ? "bg-[#2dd4bf14] font-medium text-brand-500"
                  : "text-fg-secondary hover:bg-surface-hover hover:text-fg-primary",
              )}
            >
              {item.active && (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-brand-500" />
              )}
              <item.icon className="h-[18px] w-[18px] shrink-0" />
              <span>{item.label}</span>
            </a>
          ))}
        </nav>

        <div className="border-t border-subtle p-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-2 transition-colors duration-fast hover:bg-surface-hover">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#2dd4bf1f] text-sm font-semibold text-brand-500">
              CT
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-fg-primary">Carlos Torres</p>
              <p className="truncate text-xs text-fg-muted">Admin · Acme Corp</p>
            </div>
          </div>
        </div>
      </aside>

      <div className="ml-60">
        <header className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b border-subtle bg-base px-6">
          <h1 className="text-lg font-semibold text-fg-primary">Dashboard</h1>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative hidden md:block">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" />
              <input
                type="search"
                placeholder="Buscar proyectos, tareas..."
                className="h-9 w-72 rounded-md border border-subtle bg-sunken pl-9 pr-3 text-sm text-fg-primary placeholder:text-fg-muted focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
            </div>

            <button
              type="button"
              className="relative flex h-9 w-9 items-center justify-center rounded-md border border-subtle bg-sunken text-fg-secondary transition-colors duration-fast hover:text-fg-primary"
            >
              <BellIcon className="h-[18px] w-[18px]" />
              <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-danger" />
            </button>

            <button
              type="button"
              className="flex h-9 items-center gap-2 rounded-md border border-subtle bg-sunken px-2.5 transition-colors duration-fast hover:border-strong"
            >
              <span className="flex h-5 w-5 items-center justify-center rounded bg-brand-500 text-[10px] font-bold text-brand-contrast">
                A
              </span>
              <span className="text-sm text-fg-secondary">Acme Corp</span>
              <ChevronIcon className="h-4 w-4 text-fg-muted" />
            </button>
          </div>
        </header>

        <main className="space-y-6 px-6 py-6">
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            {kpis.map((k) => (
              <div
                key={k.label}
                className="rounded-lg border border-subtle bg-raised p-4 transition-colors duration-fast hover:border-strong"
              >
                <div className="flex items-center justify-between">
                  <div className={cn("flex h-10 w-10 items-center justify-center rounded-md", toneMap[k.tone])}>
                    <k.icon className="h-5 w-5" />
                  </div>
                  <span className={cn("inline-flex items-center gap-1 text-xs font-medium tabular-nums", trendTone[k.trendTone])}>
                    {k.trend}
                  </span>
                </div>
                <p className="mt-4 text-xs font-medium uppercase tracking-wide text-fg-muted">{k.label}</p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-fg-primary">{k.value}</p>
              </div>
            ))}
          </section>

          <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
            <div className="overflow-hidden rounded-lg border border-subtle bg-raised xl:col-span-2">
              <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
                <div>
                  <h2 className="text-sm font-semibold text-fg-primary">Margen por proyecto</h2>
                  <p className="text-xs text-fg-muted">Top 5 por facturación del período</p>
                </div>
                <span className="rounded-md border border-subtle bg-sunken px-2 py-1 text-xs text-fg-secondary tabular-nums">
                  5 de 24
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-subtle text-left text-[11px] uppercase tracking-wide text-fg-muted">
                      <th className="px-4 py-2.5 font-medium">Proyecto</th>
                      <th className="px-4 py-2.5 font-medium">Cliente</th>
                      <th className="px-4 py-2.5 text-right font-medium">Horas</th>
                      <th className="px-4 py-2.5 text-right font-medium">Costo</th>
                      <th className="px-4 py-2.5 text-right font-medium">Ingresos</th>
                      <th className="px-4 py-2.5 text-right font-medium">Margen</th>
                      <th className="px-4 py-2.5 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projects.map((p) => (
                      <tr
                        key={p.proyecto}
                        className="border-b border-[#161d2a] transition-colors duration-fast last:border-0 hover:bg-surface-hover"
                      >
                        <td className="px-4 py-3 font-medium text-fg-primary">{p.proyecto}</td>
                        <td className="px-4 py-3 text-fg-secondary">{p.cliente}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-fg-secondary">{p.horas}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-fg-secondary">{p.costo}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-fg-primary">{p.ingresos}</td>
                        <td className={cn("px-4 py-3 text-right font-medium tabular-nums", marginTone(p.margen).text)}>
                          {p.margenLabel}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                              statusTone(p.estado),
                            )}
                          >
                            {p.estado}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <aside className="overflow-hidden rounded-lg border border-subtle bg-raised xl:col-span-1">
              <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
                <h2 className="text-sm font-semibold text-fg-primary">Actividad reciente</h2>
                <span className="text-xs text-fg-muted">Hoy</span>
              </div>
              <ul className="divide-y divide-[#161d2a]">
                {activity.map((a, i) => (
                  <li key={i} className="flex gap-3 px-4 py-3 transition-colors duration-fast hover:bg-surface-hover">
                    <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dotMap[a.tone])} />
                    <div className="min-w-0">
                      <p className="text-sm leading-snug text-fg-primary">{a.text}</p>
                      <p className="mt-1 text-xs tabular-nums text-fg-muted">{a.time}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </aside>
          </section>
        </main>
      </div>
    </div>
  );
}

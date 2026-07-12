export const DESIGN_SYSTEM_NAME = "FinOps Dark";

export type Tier = "starter" | "growth" | "enterprise" | "vip";

export interface TierInfo {
  id: Tier;
  name: string;
  priceLabel: string;
  features: readonly string[];
  highlight?: boolean;
}

export const TIERS: readonly TierInfo[] = [
  { id: "starter", name: "Starter", priceLabel: "$46.600/mes", features: ["Multi-tenant (shared)", "RBAC + MFA", "Time tracking", "1 año retención audit"] },
  { id: "growth", name: "Growth", priceLabel: "$189.000/mes", features: ["Todo Starter", "Webhooks Git", "Dashboards margen", "Rate-limit 600/min"], highlight: true },
  { id: "enterprise", name: "Enterprise", priceLabel: "$1.424.000/mes", features: ["Schema aislado", "SSO SAML/OIDC", "SLA 99,9%", "3 años retención"] },
  { id: "vip", name: "VIP / Custom", priceLabel: "A contrato", features: ["DB dedicada", "Recursos VIP Swarm", "SLA 99,99%", "7 años WORM"] },
];

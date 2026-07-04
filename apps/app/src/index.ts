// apps/app/src/index.ts - barrel for app
export { appConfig } from './app.config';

export const appConfig = {
  name: "app",
  description: "SaaS PM+FinOps - Producto principal (dashboard, proyectos, FinOps)",
  version: "0.1.0"
} as const;
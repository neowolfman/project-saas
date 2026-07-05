# =============================================================================
# SaaS PM+FinOps — Frontend dev container (Next.js + pnpm workspace)
#
# Build context: REPO ROOT (../../ from infra/docker/)
# Compartido por apps/landing y apps/app — el comando se override en compose.
# =============================================================================

FROM node:20-alpine AS base

RUN apk add --no-cache libc6-compat && \
    corepack enable && \
    corepack prepare pnpm@9.12.0 --activate

WORKDIR /app

# Copiar archivos de configuración del workspace raíz
COPY package.json pnpm-workspace.yaml .npmrc ./

# Copiar TODOS los package.json del workspace para resolución de dependencias
COPY apps/landing/package.json apps/landing/package.json
COPY apps/app/package.json apps/app/package.json
COPY libs/ui-tokens/package.json libs/ui-tokens/package.json
COPY libs/design-system/package.json libs/design-system/package.json
COPY libs/api-contracts/package.json libs/api-contracts/package.json

# Instalar dependencias del workspace completo
# --no-frozen-lockfile porque aún no tenemos pnpm-lock.yaml commiteado
RUN pnpm install --no-frozen-lockfile

# El código fuente se monta via volumes en docker-compose para hot reload.
# Exponer el puerto de Next.js dev server
EXPOSE 3000

# Comando por defecto — se override en docker-compose por cada app
CMD ["pnpm", "--filter", "@saas/landing", "dev", "--hostname", "0.0.0.0"]

FROM node:24-slim AS build
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./apps/web/
RUN pnpm build

FROM node:24-slim
ENV NODE_ENV=production HOST=0.0.0.0 PORT=8000
WORKDIR /app
COPY --from=build --chown=node:node /repo/apps/web/.output/ ./.output/
USER node
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:8000/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"
CMD ["node", ".output/server/index.mjs"]

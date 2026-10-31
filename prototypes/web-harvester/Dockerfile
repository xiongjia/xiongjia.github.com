# Three runtime images:
#   runtime (default) — patchright + bundled Chromium, i.e. no Camoufox download
#   camoufox          — also bakes Camoufox's Firefox build in at build time,
#                       which is the only place the 1.3 GB fetch belongs
#   cloakbrowser      — bakes CloakBrowser's ~200 MB stealth Chromium in instead
#
#   docker build -t web-harvester .
#   docker build --target camoufox \
#     --build-arg CAMOUFOX_MIRROR=https://ghfast.top/ \
#     -t web-harvester:camoufox .
#   docker build --target cloakbrowser -t web-harvester:cloakbrowser .

FROM node:24-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM node:24-bookworm-slim AS runtime
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates libnss3 libgbm1 libasound2 libgtk-3-0 libx11-xcb1 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxtst6 libxt6 \
      fonts-noto-cjk xvfb \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY scripts ./scripts
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist

RUN useradd -m -u 1000 app \
    && mkdir -p /app/.cache /app/data \
    && chown -R app /app
USER app

# The bundled Chromium is the fallback engine; baked in so the container needs
# no network at run time.
ENV HARVEST_BROWSER=patchright \
    HARVEST_CHANNEL=chromium \
    TZ=Asia/Shanghai \
    LANG=zh_CN.UTF-8
RUN pnpm exec patchright install --with-deps chromium

EXPOSE 8765
CMD ["node", "dist/main.js"]

# Camoufox variant: Firefox build fetched during the build, then frozen into the
# image. Pass CAMOUFOX_MIRROR when github.com release downloads are blocked.
FROM runtime AS camoufox
ARG CAMOUFOX_MIRROR=
ENV CAMOUFOX_MIRROR=${CAMOUFOX_MIRROR}
RUN pnpm camoufox:fetch
ENV HARVEST_BROWSER=camoufox

# CloakBrowser variant: the stealth Chromium build is fetched during the build
# (cloakbrowser.dev redirects to GitHub releases, ~200 MB) and cached in the
# image. Builds newer than v146 need a license key at run time:
#   docker run -e CLOAKBROWSER_LICENSE_KEY=cb_xxxx ...
# The free key allows a single concurrent session, so stay on one profile.
FROM runtime AS cloakbrowser
ENV CLOAKBROWSER_CACHE_DIR=/app/.cloakbrowser \
    CLOAKBROWSER_AUTO_UPDATE=false \
    HARVEST_BROWSER=cloakbrowser
RUN pnpm exec cloakbrowser install && chown -R app /app/.cloakbrowser

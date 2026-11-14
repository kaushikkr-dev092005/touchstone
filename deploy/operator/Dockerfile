FROM --platform=$BUILDPLATFORM oven/bun:1.4.0@sha256:5ff609364c049b54eb0ff560ec96319729a972078ef2c755d758f0c6ef89c2d6 AS frontend
WORKDIR /source
COPY apps/web/package.json apps/web/bun.lock apps/web/
RUN cd apps/web && bun install --frozen-lockfile --ignore-scripts
COPY apps/web apps/web
COPY tools/build_site_evidence.py tools/build_site_evidence.py
COPY tools/build_public_dashboard.py tools/build_public_dashboard.py
COPY apps/dashboard apps/dashboard
COPY touchstone touchstone
COPY bench bench
RUN apt-get update && apt-get install -y --no-install-recommends python3 && rm -rf /var/lib/apt/lists/*
RUN cd apps/web && bun run build

FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS quote_runtime
WORKDIR /node
COPY integrations/metal/package.json integrations/metal/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df AS operator
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 10001 touchstone && useradd --uid 10001 --gid 10001 --no-user-group --create-home operator && mkdir -p /var/lib/touchstone && chown 10001:10001 /var/lib/touchstone
COPY touchstone touchstone
COPY tools/run_operator.py tools/run_operator.py
COPY tools/operator_backup.py tools/operator_backup.py
COPY integrations/metal integrations/metal
COPY --from=quote_runtime /node/node_modules integrations/metal/node_modules
COPY --from=quote_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /source/apps/web/dist apps/web/dist
ARG SOURCE_REVISION=unknown
LABEL org.opencontainers.image.revision=$SOURCE_REVISION
ENV TOUCHSTONE_SOURCE_REVISION=$SOURCE_REVISION TOUCHSTONE_IGNORE_LOCAL_CONFIG=1 PYTHONUNBUFFERED=1
USER operator
EXPOSE 8089
VOLUME /var/lib/touchstone
CMD ["python", "tools/run_operator.py", "serve", "--bind", "0.0.0.0", "--config", "/var/lib/touchstone/operator-config.json", "--data-dir", "/var/lib/touchstone/jobs"]

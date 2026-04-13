FROM mcr.microsoft.com/playwright:v1.50.0-noble

WORKDIR /e2e

# Bake in dependencies at build time.
# Browsers are pre-installed in the base image — no playwright install needed.
COPY package.json package-lock.json* ./
RUN npm install

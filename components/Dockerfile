# ==========================================
# Stage: image-base
# ==========================================
FROM node:24-slim AS image-base

WORKDIR /app

COPY --chown=civicpatch_user:civicpatch_user package.json package-lock.json /app
RUN npm install
COPY --chown=civicpatch_user:civicpatch_user . /app

USER civicpatch_user


# ==========================================
# Stage: development
# ==========================================

FROM image-base AS development

ENV NODE_ENV="development" \
    BUILD_ENV="development"

WORKDIR /app

RUN ls -la
COPY ./src/frontend/package.json ./src/frontend/package-lock.json /app
RUN npm install
COPY ./src/frontend/ /app

RUN ["npm", "run", "build"]
CMD ["npm", "run", "start-proxy-server"]

# ==========================================
# Final Stage: production
# ==========================================

# PRODUCTION IMAGE
FROM image-base AS production

ENV CIVICPATCH_ENV="production"

WORKDIR /app
EXPOSE 80 
# # Keep the container running
# CMD ["tail", "-f", "/dev/null"]
CMD ["npm", "run", "start-proxy-server"]

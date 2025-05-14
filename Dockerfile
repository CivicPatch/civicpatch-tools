FROM ruby:3.4.2

RUN apt-get update && apt-get install -y  \
  nodejs npm \
  cmake sudo \
  && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password civicpatch_user
WORKDIR /app
RUN chown -R civicpatch_user:civicpatch_user /app && \
  chmod -R 755 /app

USER civicpatch_user

RUN git init --initial-branch=main && \
  git remote add origin https://${GITHUB_TOKEN}:x-oauth-basic@github.com/CivicPatch/open-data.git && \
  git sparse-checkout set package.json package-lock.json \
  Gemfile Gemfile.lock open_data.gemspec lib/open_data/version.rb && \
  git pull origin main

RUN ls -la

RUN npm ci
RUN bundle install

USER root
RUN ./node_modules/.bin/playwright install-deps

USER civicpatch_user
RUN ./node_modules/.bin/playwright install chromium

CMD ["tail", "-f", "/dev/null"]

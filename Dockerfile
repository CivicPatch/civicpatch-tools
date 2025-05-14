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

COPY --chown=civicpatch_user Gemfile Gemfile.lock open_data.gemspec ./
COPY --chown=civicpatch_user lib/open_data/version.rb ./lib/open_data/
COPY --chown=civicpatch_user package.json package-lock.json ./

RUN bundle install
RUN npm ci

USER root
RUN ./node_modules/.bin/playwright install-deps

USER civicpatch_user
RUN ./node_modules/.bin/playwright install chromium

COPY --chown=civicpatch_user . .

CMD ["tail", "-f", "/dev/null"]

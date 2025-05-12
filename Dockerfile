FROM ruby:3.4.2

RUN apt-get update && apt-get install -y  \
  nodejs npm \
  cmake sudo \
  && rm -rf /var/lib/apt/lists/*

RUN adduser --disabled-password civicpatch_user
USER civicpatch_user

WORKDIR /app

COPY --chown=civicpatch_user Gemfile Gemfile.lock ./
COPY --chown=civicpatch_user package.json package-lock.json ./
COPY --chown=civicpatch_user . .

RUN bundle install
RUN npm install

USER root
RUN ./node_modules/.bin/playwright install-deps

USER civicpatch_user
RUN ./node_modules/.bin/playwright install

CMD ["bundle", "exec", "rake", "pipeline:hello"]

FROM ruby:3.4.2

RUN apt-get update && apt-get install -y  \
  nodejs npm \
  cmake sudo \
  git \
  jq \ 
  && rm -rf /var/lib/apt/lists/*

# Add latest gh cli for updating comments/reviewing prs
RUN (type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
  && sudo mkdir -p -m 755 /etc/apt/keyrings \
  && out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  && cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
  && sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
  && sudo apt update \
  && sudo apt install gh -y

RUN adduser --disabled-password civicpatch_user
WORKDIR /app
RUN chown -R civicpatch_user:civicpatch_user /app && \
  chmod -R 755 /app

USER civicpatch_user

COPY --chown=civicpatch_user civpatch/package.json civpatch/package-lock.json ./civpatch/
COPY --chown=civicpatch_user civpatch/Gemfile civpatch/Gemfile.lock civpatch/Rakefile ./civpatch/

WORKDIR /app/civpatch

RUN ls -la

RUN npm ci
RUN bundle install

USER root
RUN ./node_modules/.bin/playwright install-deps

USER civicpatch_user
RUN ./node_modules/.bin/playwright install chromium

COPY --chown=civicpatch_user civpatch/lib/ /app/civpatch/lib/

CMD ["tail", "-f", "/dev/null"]

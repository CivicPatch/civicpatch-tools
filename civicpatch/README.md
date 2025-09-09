# civicpatch

This project collects the elected officials data for municipalities in the
United States.

Data collected includes

- names
- roles (ex: Mayor, Council Member)
- divisions (ex: Ward 1)
- images
- phone numbers
- emails
- websites

Roles and divisions are standardized via the rules listed under [./config](./config).

## Development

### Requirements

- [mise](https://mise.jdx.dev/getting-started.html)
- [docker](https://www.docker.com/products/docker-desktop/)

## Setup

1. Set up [environment variables](#environment-setup) # TODO setup
2. Run `mise install`
  This will install python & poetry, but these are used for
  typehinting (ex: with vs code). Actual development and scripts
  should run inside docker

### Commands

#### Run tests

- `mise unit`
  - Quick tests

- `mise integration`
  - Calls 3rd party services
  - Runs (local) nlp tests

#### Add new package

```sh
mise container poetry add <package>
docker compose build
```

## Environment Setup

Add a .env file with the following variables:

```dotenv
BRAVE_SEARCH_TOKEN=
GOOGLE_SEARCH_TOKEN=
GOOGLE_SEARCH_ENGINE_ID=
SERP_API_SEARCH_TOKEN=

GOOGLE_GEMINI_TOKEN=
OPENAI_TOKEN=
TOGETHER_AI_TOKEN=

CRUDDER_URL="https://crudder.civicpatch.org"
CRUDDER_SHARED_TOKEN=ABCDEF12345
```

Optional environment variables:

- GOOGLE_SHEETS_TOKEN and GOOGLE_SHEETS_ID are used to log
  calculated operating costs of running each scrape job.

```dotenv
GOOGLE_SHEETS_TOKEN=
GOOGLE_SHEETS_ID=
```

### CRUDDER_SHARED_TOKEN
1. Go to crudder.civicpatch.org and generate an API token.
2. Email the repo maintainer about your new account. Provide the following details:
  - provider
  - provider_user_id
  - user_email
3. Set up your CivicPatch Server URL. This is a public URL your server can be reached by.

  3.a. Example Setup (local):
    - Download [tailscale](https://tailscale.com/download)
      and follow setup instructions.
    - From the "civicpatch" directory, run `docker compose up`
    - Run `tailscale funnel 80`
    - Verify you can reach this page:
      https://example.example-name.ts.net/docs
    - Update `CivicPatch Server URL` to `https://fedora.dropbear-minnow.ts.net`
    - Generate the API key. This is your `CRUDDER_SHARED_TOKEN`
    - Update your environment variables and restart your server.
## TODOS

- [ ] 
- [ ] Add logger for each step
  - [ ] collect
- [ ] Update token variables on github
- [ ] Add logger for search engine costs

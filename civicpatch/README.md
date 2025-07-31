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
- `mise integration`

## Environment Setup

Add a .env file with the following variables:

```dotenv
GOOGLE_GEMINI_TOKEN=
OPENAI_TOKEN=
BRAVE_SEARCH_TOKEN=
GOOGLE_SEARCH_TOKEN=
SERP_SEARCH_TOKEN=
```

Optional environment variables:

- GOOGLE_SHEETS_TOKEN and GOOGLE_SHEETS_ID are used to log
  calculated operating costs of running each scrape job.

```dotenv
GOOGLE_SHEETS_TOKEN=
GOOGLE_SHEETS_ID=
```

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

## Setup (Run)

### Windows

1. Download [docker](https://www.docker.com/products/docker-desktop/)
  1.a Set up Docker with WSL Integration. Guide [here](https://docs.docker.com/desktop/features/wsl/)
2. Copy the files from [civicpatch/examples/setup_project](./examples/setup_project/) onto your computer
2. Set up the necessary environment variables under a new `civicpatch/.env` file.
   See [.env.example] for the necessary variables.
   You will need to collaborate with the crudder maintainer to use the `API_CIVICPATCH_ORG_TOKEN`.
   See: [API_CIVICPATCH_ORG_TOKEN](#API_CIVICPATCH_ORG_TOKEN)
3. Under the `civicpatch` directory, run:
  a. (with powershell), run: `docker pull ghcr.io/civicpatch/civicpatch:latest`
    This may take a while.
  b. (with powershell), run: `docker compose up`
4. You're done. Open up a browser at `http://localhost:8000`

### MacOS/Linux
1. Download [docker](https://www.docker.com/products/docker-desktop/)
2. Copy the files from [civicpatch/examples/setup_project](./examples/setup_project/) onto your computer
2. Set up the necessary environment variables under a new `civicpatch/.env` file.
   See [.env.example] for the necessary variables.
   You will need to collaborate with the crudder maintainer to use the `API_CIVICPATCH_ORG_TOKEN`.
   See: [API_CIVICPATCH_ORG_TOKEN](#API_CIVICPATCH_ORG_TOKEN)
3. Under the `civicpatch` directory, run:
  a. (with a terminal), run: `docker pull ghcr.io/civicpatch/civicpatch:latest`
    This may take a while.
  b. (with terminal), run: `docker compose up`
4. You're done. Open up a browser at `http://localhost:8000`

## Setup (Development)

### MacOS/Linux
1. Download [docker](https://www.docker.com/products/docker-desktop/)
2. Download [mise](https://mise.jdx.dev/getting-started.html)
  2.a. Run mise install under the `civicpatch` directory
3. Set up the necessar environment variables under a new `civicpatch/.env` file.
   See [.env.example] for the necessary variables.
   You will need to collaborate with the crudder maintainer to use the `API_CIVICPATCH_ORG_TOKEN`.
   See: [API_CIVICPATCH_ORG_TOKEN](#API_CIVICPATCH_ORG_TOKEN)
4. Under the `civicpatch/` directory, run `mise dev`. This will take a while if it's the first time.
5. You're done. yOpen up a browser at `http://localhost:8000`

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

### API_CIVICPATCH_ORG_TOKEN
1. Go to api.civicpatch.org and generate an API token.
2. Email the repo maintainer (michelle@civicpatch.org) about your new account. Provide the following details:
  - provider
  - provider_user_id
  - user_email
3. Set up your CivicPatch Server URL. This is a public URL your server can be reached by.
  NOTE: this step is optional if you're just testing -- you should be able to generate PRs without this.
  Let me know if it skipping it doesn't work -- you could try putting a garbage link in the form.
  3.a. Example Setup (local):
    - Download [tailscale](https://tailscale.com/download)
      and follow setup instructions.
    - From the "civicpatch" directory, run `docker compose up`
    - Run `tailscale funnel 80`
    - Verify you can reach this page:
      https://example.example-name.ts.net/docs
    - Update `CivicPatch Server URL` to `https://fedora.dropbear-minnow.ts.net`
    - Generate the API key. This is your `API_CIVICPATCH_ORG_TOKEN`
    - Update your environment variables and restart your server.
## TODOS

- [ ] 
- [ ] Add logger for each step
  - [ ] collect
- [ ] Update token variables on github
- [ ] Add logger for search engine costs

# civicpatch-tools

Set of projects that support the collection of elected municipal officials across
the United States.

To see the entire set of data, check the [open-data](https://github.com/CivicPatch/open-data/) repo.

## Projects

- [civicpatch](./civicpatch/README.md)
  The main project. Scrapes websites for contact information on elected officials.
  Scrape jobs are run on either GitHub Actions or by volunteers running scrapes on their own servers.
- [crudder](./crudder/README.md)
  Helper project that sits civicpatch volunteer servers & GitHub Actions.

## Development

### Requirements

- Docker
  You will need this to run anything here. Tested on OSX, should work on Linux, might work
  on Windows but you may need to do extra tweaking with user permissions.
- [mise](https://mise.jdx.dev/getting-started.html).
  Under each project there will be mise.toml files that should make development easier (test scripts, starting projects, etc).

### Steps
1. Run `mise install` to set up your environment.
2. Run `pre-commit install` to set up gitleaks.
3. Go into individual projects (civicpatch, mainly) for further setup steps

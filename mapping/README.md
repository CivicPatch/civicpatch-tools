# Geocoding

POC project for generating hyperlocal maps

## Getting Started

1. Run `npm install`
2. Run `npm run crawl <state> <geoid>`

Note: don't try to run this on municipalities that have NO divisions listed under `data_source/<state>/municipalities.yaml`.
We use the divisions length to determine the proper number of features a geojson file should have.

Example:

to crawl seattle, wa:

```bash
npm run crawl wa 5363000
```
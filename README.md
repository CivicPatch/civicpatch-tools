# OpenData

## Pipeline Setup
* Join civicpatch-tools repo
* Set up environment variables under environment: `env-<github-username>`
  * Google Search
  * Brave Search
  * OpenAI
  * Google Gemini
* Actions -> Run "Municipal Officials - Scrape"

## Contribute
### Run Scrapes
1. Download latest [release](https://github.com/CivicPatch/civicpatch-tools/releases)
2. Set environment variables:
  * OPENAI_TOKEN
  * GOOGLE_GEMINI_TOKEN
3. Find a GEOID to scrape under data_source/[state]/municipalities.json
4. Run the command
```sh
./civpatch scrape -run -state wa -geoid 5335940
```

This will start a docker container, run the scrape, and when the scrapes are complete, output to the /output folder.

####

## Development
### Requirements
* Docker
* [Go](https://go.dev/doc/install)
* [Air](https://github.com/air-verse/air?tab=readme-ov-file#via-go-install-recommended)

## Sources
* All populations & municipalities are pulled primarily from US Census
  * Population
    * [CENSUS_POPULATION_API](https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=place:*&in=state:43)
  * Codes (fips & gnis codes)
    * [CENSUS_MUNICIPALITIES_CODES](https://www2.census.gov/geo/docs/reference/codes2020/place/st53_wa_place2020.txt)
* [https://docs.google.com/spreadsheets/d/1QtcMQV85HUxTayyk8mVO5Eqr8bWiNEdGc12RuoWuLpM/edit?gid=646812149#gid=646812149](List of state-level municipal officials)
### Washington
- **State local officials directory (unofficial)**: https://mrsc.org/mrsctools/officials-directory/city.aspx
  - Contains city council members
### Oregon
- **State local officials directory (unofficial)**: https://www.orcities.org/resources/reference/city-directory
### California
- **State local officials directory (official SOS)**: 
  - https://www.sos.ca.gov/administration/california-roster (2024 only)
### Idaho (TBD)
- **State local officials directory (unofficial)**:
  - https://idahocities.org/store/ListProducts.aspx?catid=440197 (not scrapeable -- must be a member)
### New Hampshire
- Combo of
  - [Community Profiles](https://www.nhes.nh.gov/elmi/products/cp/)
    - TIL -- what are Selectmen???
    - Gives you government type, website, general email, general phone #
    - More data than below
  - [List of municipalities](https://www.nheconomy.com/office-of-planning-and-development/what-we-do/state-data-center-(census-data)/municipalities,-counties-and-regions)
    - Contains websites & counties, easier to scrape
  - For officials -- do a google search
### Michigan
- For townships: https://michigantownships.org/find-a-township#aftersearch
  - Contains city council members!
  - This looks SUPER well maintained; haven't verified data
- For cities/etc -- do a google search
  
### FIPS examples
* https://www2.census.gov/geo/docs/reference/codes2020/place/st41_or_place2020.txt

### Playwright Setup
* npm install playwright
* ./node_modules/.bin/playwright install

### Services
* Search Services
  * Google Search - free tier only
    * [Manage](https://console.cloud.google.com/apis/api/customsearch.googleapis.com)
    * Free Tier - 100 req/day
      * (should error out)
    * Paid Tier - $5.00 per 1000 requests
  * Brave - free tier only
    * [Manage](https://api-dashboard.search.brave.com/app/dashboard)
    * Free Tier - 2000 req/month
* Google Gemini 2.5 Flash (used with scraping) - Paid Tier 1
  * [Manage](https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/metrics)
  * [Pricing](https://ai.google.dev/gemini-api/docs/pricing)
  * Input: $0.15 Per Million
  * Output: $0.60 Per Million
* OpenAI API - GPT 4.1 Mini (used with scraping)
  * [Pricing](https://platform.openai.com/docs/pricing)
  * Input: $0.40 Per Million
  * Output: $1.60 Per Million
* Digital Ocean
  * Host images under spaces

### Links
* https://editor.dicebear.com/

### Misc Setup
* Set up gitleaks
  * Move [this](https://raw.githubusercontent.com/gitleaks/gitleaks/958f55ac629b5351bb7b9c80f00c10823fef64d3/scripts/pre-commit.py) to .git/hooks/pre-commit.py



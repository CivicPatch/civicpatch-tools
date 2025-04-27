# OpenData

## Rules
* Cities can be in two counties (ex: King/Snohomish -> Bothell)
* A county can have the same name as a city (ex: Spokane/Spokane)

## Commands

```bash
rake 'city_scrape:get_places[mi]'
```

## Sources
* All populations & municipalities are pulled primarily from US Census
  * Population
    * [CENSUS_POPULATION_API](https://api.census.gov/data/2020/dec/pl?get=P1_001N,NAME&for=place:*&in=state:43)
  * Codes (fips & gnis codes)
    * [CENSUS_MUNICIPALITIES_CODES](https://www2.census.gov/geo/docs/reference/codes2020/place/st53_wa_place2020.txt)
### Washington
- **State local officials directory (unofficial)**: https://mrsc.org/mrsctools/officials-directory/city.aspx
### Oregon
- **State local officials directory (unofficial)**: https://www.orcities.org/resources/reference/city-directory
### California
- **State local officials directory (official SOS)**: 
  - https://www.sos.ca.gov/administration/california-roster (2024 only)
### Idaho (TBD)
- **State local officials directory (unofficial)**:
  - https://idahocities.org/store/ListProducts.aspx?catid=440197 (not scrapeable -- must be a member)
  
### FIPS examples
* https://www2.census.gov/geo/docs/reference/codes2020/place/st41_or_place2020.txt

### Scratch
```bash
gh pr list --state open --json headRefName --search "head:pipeline-city-scrapes-wa-" --template '{{range .}}{{.headRefName}} {{end}}'
```

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
  * Pricing Page - https://ai.google.dev/gemini-api/docs/pricing
  * Input: $0.15 Per Million
  * Output: $0.60 Per Million
* OpenAI API - GPT 4.1 Mini (used with scraping)
  * Input: $0.40 Per Million
  * Output: $1.60 Per Million
  * https://platform.openai.com/docs/pricing 
* Digital Ocean
  * Host images under spaces

### Links
* https://editor.dicebear.com/

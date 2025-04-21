# OpenData

## Rules
* Cities can be in two counties (ex: King/Snohomish -> Bothell)
* A county can have the same name as a city (ex: Spokane/Spokane)

## Commands

```bash
rake 'city_scrape:get_places[mi]'
```

## Priorities
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

### Country Directory
- [ ] Maps of states

### Scratch
```bash
gh pr list --state open --json headRefName --search "head:pipeline-city-scrapes-wa-" --template '{{range .}}{{.headRefName}} {{end}}'
```

### Services
* Google Gemini 2.0 Flash (used with scraping) - Paid Tier 1
  * Pricing Page - https://ai.google.dev/gemini-api/docs/pricing
  * Input: $0.10 Per Million
  * Output: $0.40 Per Million
* OpenAI API - GPT 4.1 Mini (used only with scraping)
  * Input: $0.40 Per Million
  * Output: $1.60 Per Million
  * https://platform.openai.com/docs/pricing 
* Digital Ocean
  * Host images under spaces

### Links
* https://editor.dicebear.com/

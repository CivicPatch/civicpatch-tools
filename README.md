# OpenData

## How this works

```mermaid
flowchart TD;
    A[Manual Pipeline: Grab a list of cities from STATE/places.yml] --> B[Scrape City Data for people -- council members, mayor, etc.]
    B --> C[Bot opens a Pull Request for Review]
    C --> D[Contributors Review and Merge Changes]
    %% Pull Request Link: https://github.com/CivicPatch/open-data/pull/17
    D.special[/You, the volunteer/] --> D
    D --> F[Data coverage improves]
```

## Rules
* Cities can be in two counties (ex: King/Snohomish -> Bothell)
* A county can have the same name as a city (ex: Spokane/Spokane)

## Commands

```bash
rake 'city_scrape:get_places[mi]'
```

## Priorities
### Washington
- [ ] Top 10 cities by population
- [ ] Bottom 10 cities by population
- [ ] Executive branch officials
- [ ] CD Map

### City Directory
- [ ] Grab council members & city leaders for:
  - [ ] Washington
    - [ ] Top 20 cities by population
  - [ ] Alabama
    - [ ] Top 20 cities by population

### State Directory
- [ ] Grab info for:
  - [ ] Washington
    - [ ] Executive branch officials
    - [ ] CD Maps
  - [ ] California
    - [ ] Executive branch officials
    - [ ] CD Maps
  - [ ] Texas
    - [ ] Executive branch officials
    - [ ] CD Map 
  - [ ] Florida
    - [ ] Executive branch officials
    - [ ] CD Map
  - [ ] New York
    - [ ] Executive branch officials
    - [ ] CD Map

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

### Links
* https://editor.dicebear.com/

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
  - [x] Washington
    - [x] Top 20 cities by population
      - [x] seattle
      - [x] spokane
      - [x] tacoma
      - [x] vancouver
      - [x] bellevue
      - [x] kent
      - [x] everett
      - [x] spokane_valley
      - [x] renton
      - [ ] federal_way
      - [x] yakima
      - [ ] bellingham
      - [ ] kirkland
      - [ ] auburn
      - [ ] kennewick
      - [ ] pasco
      - [ ] redmond
      - [ ] marysville
      - [ ] sammamish
      - [ ] lakewood
  - [ ] Michigan
    - [ ] Top 10 cities by population

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

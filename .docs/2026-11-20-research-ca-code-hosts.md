# California: where each place's code is published

Step 1.4 of the `state-offices` skill. Layers: [2026-11-20-research-ca-layers.md](2026-11-20-research-ca-layers.md).

## Sources, 2026-11-20

- **ICC Code Solutions**, https://www.icccodesolutions.org/text-library/ (`div.state CA`): 321 entries, fetched plain.
- **Municode**, https://api.municode.com/Clients/stateAbbr?stateAbbr=CA, opened in a browser and pasted into the
  session (not kept in either repo): 237 clients. The code url below is built from `ClientName`
  (`library.municode.com/ca/<name>`) and is not checked.

Matched to `data_source/ca/{local,counties}/jurisdictions.yml` with pipeline 1's `charter_title_matches`
(`pipelines/src/runners/pipeline01_governing_law_collector/finders/state_index.py`): ICC titles "{lsad} of {place}"
and "{place} {lsad}"; Municode "{place}", plus "{place} {lsad}" and "{lsad} of {place}" for clients named "Alameda
County" or "City of Calabasas". Scripts in the session scratchpad, not kept.

| Directory | Entries | Matched | Ambiguous | Unmatched |
|---|---|---|---|---|
| ICC | 321 | 286 (261 cities, 5 towns, 20 counties) | 0 | 35 |
| Municode | 237 | 217 (166 cities, 14 towns, 37 counties), 6 of them settled by `ClassificationId` | 0 | 20 |

Together: 501 of 541 places have a listed code, 446 of 483 cities and towns and 55 of 58 counties. Two counties are
in both (Madera, San Joaquin). No code in either: Glenn, Tuolumne and San Francisco counties, and 37 cities and towns.

By host, matched: 217 Municode, 203 eCode360, 55 American Legal, 17 `*.municipal.codes`, 9 codepublishing.com,
2 `*.county.codes`.

### Settled

Municode, a bare name that fits a city and its county: Alameda, Colusa, Fresno, Merced, Riverside, Tehama. Settled by
the client's `ClassificationId`, read as 2 city, 4 county, 6 town from the unambiguous clients (Agoura Hills 2, Alameda
County 4, Apple Valley town 6); all six are 2, so the city. That reading is an inference, not documented by Municode.

### Unmatched, by name form

- "City" in the place's own name, so the Census name repeats it (ICC): Cathedral City, Crescent City, King City, Sand
  City, Union City (Census "Cathedral City city").
- Another spelling: City of Angels Camp (Census "Angels city"), City of La Canada Flintridge ("La Cañada Flintridge
  city"), City of Mt. Shasta ("Mount Shasta city"), City of San Buenaventura ("San Buenaventura (Ventura) city"),
  City of Temple ("Temple City city"), Municode El Paso de Robles ("El Paso de Robles (Paso Robles) city").
- The place's own word against the Census suffix: Town of Yountville ("Yountville city"), City of Yucca Valley
  ("Yucca Valley town"), Municode City of Mountain House ("Mountain House CDP", cities doc).
- One government in two records: City and County of San Francisco (ICC).
- A body's own code: Municode "LA County - BOS", the Los Angeles County Board of Supervisors' (Los Angeles County has
  its own client too).
- Not a city's or county's code: ICC 22 (special districts, the Los Angeles County Metropolitan Transportation
  Authority, the Sacramento County Water Agency code, the Los Angeles city and county "Local Building Codes" on
  codes.iccsafe.org); Municode 17 (special districts, Port of Oakland, BART, two tribes, Nipomo Community Services
  District filed as a city).

## What a fetch allowed, by host

Pipeline 1's `plain.fetch` (robots.txt and its pace), one try per host on this run, the whole list for eCode360.
Municode refuses agents (the skill), so its codes were not tried.

| Host | Result | Charter check |
|---|---|---|
| eCode360 | served 193 of 203; every 20th request answered 429 | 40 show a charter in their contents, 153 none, 10 not checked |
| American Legal | 200, a 229-character script shell | not checked |
| `*.municipal.codes`, codepublishing.com, `*.county.codes` | 403 | not checked |
| Municode | not tried | not checked |

"Shows a charter" is a line naming a charter in the code's front page or contents ("The Charter", "Charter of the
City of Carlsbad"). Two need a second look: Fortuna ("Charter Chapter 23 – City of Fortuna") and Los Alamitos (one
bare "Charter" line). The 40: Albany, Bellflower, Burbank, Carlsbad, Cerritos, Compton, Desert Hot Springs, Downey,
Folsom, Fortuna, Gilroy, Glendale, Huntington Beach, Loma Linda, Los Alamitos, Marysville, Napa, Newport Beach,
Oroville, Pacific Grove, Palm Desert, Palm Springs, Palmdale, Rancho Mirage, Redondo Beach, Roseville, San Leandro,
Santa Barbara, Santa Clara, Santa Cruz, Santa Monica, Santee, Seal Beach, Stockton, Sunnyvale, Torrance, Vernon,
Watsonville, and Placer and Sacramento counties.

Raw results beside the plan: `plans/research/california-state-offices/icc-ca-matched-2026-11-20.tsv`,
`ecode360-charter-check-2026-11-20.tsv`.

## Per place

| Place | Host | Code | Charter in the code |
|---|---|---|---|
| Adelanto city | amlegal.com | https://codelibrary.amlegal.com/codes/adelanto/latest/overview | not checked (script shell) |
| Agoura Hills city | municode.com | https://library.municode.com/ca/agoura_hills | not checked (Municode) |
| Alameda city | municode.com | https://library.municode.com/ca/alameda | not checked (Municode) |
| Alameda County | municode.com | https://library.municode.com/ca/alameda_county | not checked (Municode) |
| Albany city | ecode360.com | https://ecode360.com/AL4074 | yes |
| Alhambra city | amlegal.com | https://codelibrary.amlegal.com/codes/alhambra/latest/overview | not checked (script shell) |
| Aliso Viejo city | ecode360.com | https://ecode360.com/AL4336 | no |
| Alpine County | codepublishing.com | https://www.codepublishing.com/CA/AlpineCounty/ | not checked (403) |
| Alturas city | municode.com | https://library.municode.com/ca/alturas | not checked (Municode) |
| Amador City city | municode.com | https://library.municode.com/ca/amador_city | not checked (Municode) |
| Amador County | ecode360.com | https://ecode360.com/AM4323 | no |
| Anaheim city | amlegal.com | https://codelibrary.amlegal.com/codes/anaheim/latest/overview | not checked (script shell) |
| Anderson city | municode.com | https://library.municode.com/ca/anderson | not checked (Municode) |
| Antioch city | amlegal.com | https://codelibrary.amlegal.com/codes/antioch/latest/overview | not checked (script shell) |
| Apple Valley town | municode.com | https://library.municode.com/ca/apple_valley | not checked (Municode) |
| Arcadia city | municode.com | https://library.municode.com/ca/arcadia | not checked (Municode) |
| Arcata city | codepublishing.com | https://www.codepublishing.com/CA/Arcata/ | not checked (403) |
| Arroyo Grande city | municode.com | https://library.municode.com/ca/arroyo_grande | not checked (Municode) |
| Artesia city | ecode360.com | https://ecode360.com/AR4900 | no |
| Arvin city | municode.com | https://library.municode.com/ca/arvin | not checked (Municode) |
| Atascadero city | ecode360.com | https://ecode360.com/AT4901 | no |
| Atherton town | municipal.codes | https://atherton.municipal.codes/ | not checked (403) |
| Atwater city | municode.com | https://library.municode.com/ca/atwater | not checked (Municode) |
| Auburn city | municode.com | https://library.municode.com/ca/auburn | not checked (Municode) |
| Avalon city | ecode360.com | https://ecode360.com/AV4054 | no |
| Azusa city | municode.com | https://library.municode.com/ca/azusa | not checked (Municode) |
| Bakersfield city | municipal.codes | https://bakersfield.municipal.codes/ | not checked (403) |
| Baldwin Park city | amlegal.com | https://codelibrary.amlegal.com/codes/baldwinpark/latest/overview | not checked (script shell) |
| Banning city | municode.com | https://library.municode.com/ca/banning | not checked (Municode) |
| Barstow city | municode.com | https://library.municode.com/ca/barstow | not checked (Municode) |
| Beaumont city | municode.com | https://library.municode.com/ca/beaumont | not checked (Municode) |
| Bell city | ecode360.com | https://ecode360.com/BE4903 | no |
| Bell Gardens city | ecode360.com | https://ecode360.com/BE4350 | no |
| Bellflower city | ecode360.com | https://ecode360.com/BE4904 | yes |
| Belmont city | municode.com | https://library.municode.com/ca/belmont | not checked (Municode) |
| Belvedere city | municipal.codes | https://belvedere.municipal.codes | not checked (403) |
| Benicia city | ecode360.com | https://ecode360.com/BE4354 | no |
| Berkeley city | codepublishing.com | https://www.codepublishing.com/CA/Berkeley/ | not checked (403) |
| Beverly Hills city | amlegal.com | https://codelibrary.amlegal.com/codes/beverlyhillsca/latest/overview | not checked (script shell) |
| Big Bear Lake city | municode.com | https://library.municode.com/ca/big_bear_lake | not checked (Municode) |
| Biggs city | ecode360.com | https://ecode360.com/BI4357 | no |
| Bishop city | municode.com | https://library.municode.com/ca/bishop | not checked (Municode) |
| Blue Lake city | ecode360.com | https://ecode360.com/BL4905 | no |
| Blythe city | municode.com | https://library.municode.com/ca/blythe | not checked (Municode) |
| Bradbury city | municode.com | https://library.municode.com/ca/bradbury | not checked (Municode) |
| Brawley city | municode.com | https://library.municode.com/ca/brawley | not checked (Municode) |
| Brea city | ecode360.com | https://ecode360.com/BR6949 | no |
| Brentwood city | ecode360.com | https://ecode360.com/BR4906 | not checked (429) |
| Brisbane city | municode.com | https://library.municode.com/ca/brisbane | not checked (Municode) |
| Buellton city | ecode360.com | https://ecode360.com/BU4908 | no |
| Buena Park city | ecode360.com | https://ecode360.com/BU4909 | no |
| Burbank city | ecode360.com | https://ecode360.com/BU4369 | yes |
| Burlingame city | ecode360.com | https://ecode360.com/BU4910 | no |
| Butte County | municode.com | https://library.municode.com/ca/butte_county | not checked (Municode) |
| Calabasas city | municode.com | https://library.municode.com/ca/city_of_calabasas | not checked (Municode) |
| Calaveras County | municode.com | https://library.municode.com/ca/calaveras_county | not checked (Municode) |
| Calexico city | municode.com | https://library.municode.com/ca/calexico | not checked (Municode) |
| California City city | municode.com | https://library.municode.com/ca/california_city | not checked (Municode) |
| Calimesa city | ecode360.com | https://ecode360.com/CA4374 | no |
| Calistoga city | ecode360.com | https://ecode360.com/CA1828 | no |
| Camarillo city | municode.com | https://library.municode.com/ca/camarillo | not checked (Municode) |
| Campbell city | municode.com | https://library.municode.com/ca/campbell | not checked (Municode) |
| Canyon Lake city | amlegal.com | https://codelibrary.amlegal.com/codes/canyonlakeca/latest/overview | not checked (script shell) |
| Capitola city | codepublishing.com | https://www.codepublishing.com/CA/Capitola/ | not checked (403) |
| Carlsbad city | ecode360.com | https://ecode360.com/CA4913 | yes |
| Carmel-by-the-Sea city | ecode360.com | https://ecode360.com/CA4376 | no |
| Carpinteria city | municode.com | https://library.municode.com/ca/carpinteria | not checked (Municode) |
| Carson city | ecode360.com | https://ecode360.com/CA4377 | no |
| Ceres city | municode.com | https://library.municode.com/ca/ceres | not checked (Municode) |
| Cerritos city | ecode360.com | https://ecode360.com/CE4381 | yes |
| Chico city | amlegal.com | https://codelibrary.amlegal.com/codes/chico/latest/overview | not checked (script shell) |
| Chino city | municode.com | https://library.municode.com/ca/chino | not checked (Municode) |
| Chino Hills city | municode.com | https://library.municode.com/ca/chino_hills | not checked (Municode) |
| Chowchilla city | municode.com | https://library.municode.com/ca/chowchilla_city | not checked (Municode) |
| Chula Vista city | municipal.codes | https://chulavista.municipal.codes/ | not checked (403) |
| Citrus Heights city | municode.com | https://library.municode.com/ca/citrus_heights | not checked (Municode) |
| Claremont city | ecode360.com | https://ecode360.com/CL4916 | no |
| Clayton city | municode.com | https://library.municode.com/ca/clayton | not checked (Municode) |
| Clearlake city | municipal.codes | https://clearlake.municipal.codes/ | not checked (403) |
| Cloverdale city | ecode360.com | https://ecode360.com/CL4387 | no |
| Clovis city | ecode360.com | https://ecode360.com/CL4388 | no |
| Coachella city | municode.com | https://library.municode.com/ca/coachella | not checked (Municode) |
| Coalinga city | municode.com | https://library.municode.com/ca/coalinga | not checked (Municode) |
| Colfax city | municode.com | https://library.municode.com/ca/colfax | not checked (Municode) |
| Colma town | municode.com | https://library.municode.com/ca/colma | not checked (Municode) |
| Colton city | municode.com | https://library.municode.com/ca/colton | not checked (Municode) |
| Colusa city | municode.com | https://library.municode.com/ca/colusa | not checked (Municode) |
| Colusa County | ecode360.com | https://ecode360.com/CO4709 | no |
| Commerce city | municode.com | https://library.municode.com/ca/commerce | not checked (Municode) |
| Compton city | ecode360.com | https://ecode360.com/CO4057 | yes |
| Concord city | codepublishing.com | https://www.codepublishing.com/CA/Concord/ | not checked (403) |
| Contra Costa County | municode.com | https://library.municode.com/ca/contra_costa_county | not checked (Municode) |
| Corcoran city | amlegal.com | https://codelibrary.amlegal.com/codes/corcoranca/latest/overview | not checked (script shell) |
| Corning city | municode.com | https://library.municode.com/ca/corning | not checked (Municode) |
| Corona city | amlegal.com | https://codelibrary.amlegal.com/codes/corona/latest/overview | not checked (script shell) |
| Coronado city | municipal.codes | https://coronado.municipal.codes/ | not checked (403) |
| Corte Madera town | municode.com | https://library.municode.com/ca/corte_madera | not checked (Municode) |
| Costa Mesa city | ecode360.com | https://ecode360.com/CO4918 | no |
| Cotati city | ecode360.com | https://ecode360.com/CO4398 | no |
| Covina city | ecode360.com | https://ecode360.com/CO4400 | no |
| Cudahy city | municipal.codes | https://cudahy.municipal.codes/ | not checked (403) |
| Culver City city | amlegal.com | https://codelibrary.amlegal.com/codes/culvercity/latest/overview | not checked (script shell) |
| Cypress city | ecode360.com | https://ecode360.com/CY4920 | no |
| Daly City city | municode.com | https://library.municode.com/ca/daly_city | not checked (Municode) |
| Dana Point city | ecode360.com | https://ecode360.com/DA4921 | not checked (429) |
| Danville town | amlegal.com | https://codelibrary.amlegal.com/codes/danvilleca/latest/overview | not checked (script shell) |
| Davis city | ecode360.com | https://ecode360.com/DA4922 | no |
| Del Mar city | municode.com | https://library.municode.com/ca/del_mar | not checked (Municode) |
| Del Norte County | municode.com | https://library.municode.com/ca/del_norte_county | not checked (Municode) |
| Del Rey Oaks city | municode.com | https://library.municode.com/ca/del_rey_oaks | not checked (Municode) |
| Delano city | municode.com | https://library.municode.com/ca/delano | not checked (Municode) |
| Desert Hot Springs city | ecode360.com | https://ecode360.com/DE4923 | yes |
| Diamond Bar city | municode.com | https://library.municode.com/ca/diamond_bar | not checked (Municode) |
| Dinuba city | ecode360.com | https://ecode360.com/DI4410 | no |
| Dixon city | ecode360.com | https://ecode360.com/DI4411 | no |
| Downey city | ecode360.com | https://ecode360.com/DO4924 | yes |
| Duarte city | municode.com | https://library.municode.com/ca/duarte | not checked (Municode) |
| Dublin city | ecode360.com | https://ecode360.com/DU4414 | no |
| Dunsmuir city | municode.com | https://library.municode.com/ca/dunsmuir | not checked (Municode) |
| East Palo Alto city | municode.com | https://library.municode.com/ca/east_palo_alto | not checked (Municode) |
| Eastvale city | municode.com | https://library.municode.com/ca/eastvale | not checked (Municode) |
| El Cajon city | ecode360.com | https://ecode360.com/EL4925 | no |
| El Centro city | municode.com | https://library.municode.com/ca/el_centro | not checked (Municode) |
| El Cerrito city | municode.com | https://library.municode.com/ca/el_cerrito | not checked (Municode) |
| El Dorado County | municode.com | https://library.municode.com/ca/el_dorado_county | not checked (Municode) |
| El Monte city | municode.com | https://library.municode.com/ca/el_monte | not checked (Municode) |
| El Segundo city | amlegal.com | https://codelibrary.amlegal.com/codes/elsegundoca/latest/overview | not checked (script shell) |
| Elk Grove city | ecode360.com | https://ecode360.com/EL4423 | no |
| Emeryville city | ecode360.com | https://ecode360.com/EM4426 | no |
| Encinitas city | ecode360.com | https://ecode360.com/EN5042 | no |
| Escalon city | ecode360.com | https://ecode360.com/ES4431 | no |
| Escondido city | ecode360.com | https://ecode360.com/ES4926 | no |
| Etna city | ecode360.com | https://ecode360.com/ET4432 | no |
| Eureka city | amlegal.com | https://codelibrary.amlegal.com/codes/eureka/latest/overview | not checked (script shell) |
| Exeter city | municode.com | https://library.municode.com/ca/exeter | not checked (Municode) |
| Fairfax town | amlegal.com | https://codelibrary.amlegal.com/codes/fairfax/latest/overview | not checked (script shell) |
| Fairfield city | ecode360.com | https://ecode360.com/FA4438 | no |
| Farmersville city | municode.com | https://library.municode.com/ca/farmersville | not checked (Municode) |
| Fillmore city | municode.com | https://library.municode.com/ca/fillmore | not checked (Municode) |
| Firebaugh city | ecode360.com | https://ecode360.com/FI4072 | no |
| Folsom city | ecode360.com | https://ecode360.com/FO4445 | yes |
| Fontana city | municode.com | https://library.municode.com/ca/fontana | not checked (Municode) |
| Fort Bragg city | codepublishing.com | https://www.codepublishing.com/CA/FortBragg/ | not checked (403) |
| Fort Jones city | municode.com | https://library.municode.com/ca/fort_jones | not checked (Municode) |
| Fortuna city | ecode360.com | https://ecode360.com/FO4448 | yes |
| Foster City city | ecode360.com | https://ecode360.com/FO4449 | no |
| Fountain Valley city | ecode360.com | https://ecode360.com/FO4927 | no |
| Fowler city | municode.com | https://library.municode.com/ca/fowler | not checked (Municode) |
| Fremont city | codepublishing.com | https://www.codepublishing.com/CA/Fremont/ | not checked (403) |
| Fresno city | municode.com | https://library.municode.com/ca/fresno | not checked (Municode) |
| Fresno County | municode.com | https://library.municode.com/ca/fresno_county | not checked (Municode) |
| Fullerton city | amlegal.com | https://codelibrary.amlegal.com/codes/fullerton/latest/overview | not checked (script shell) |
| Galt city | ecode360.com | https://ecode360.com/GA4451 | not checked (429) |
| Garden Grove city | ecode360.com | https://ecode360.com/GA4928 | no |
| Gardena city | ecode360.com | https://ecode360.com/GA4453 | no |
| Gilroy city | ecode360.com | https://ecode360.com/GI4458 | yes |
| Glendale city | ecode360.com | https://ecode360.com/GL4929 | yes |
| Glendora city | ecode360.com | https://ecode360.com/GL4930 | no |
| Goleta city | ecode360.com | https://ecode360.com/GO4931 | no |
| Gonzales city | ecode360.com | https://ecode360.com/GO4462 | no |
| Grand Terrace city | municode.com | https://library.municode.com/ca/grand_terrace | not checked (Municode) |
| Grass Valley city | municode.com | https://library.municode.com/ca/grass_valley | not checked (Municode) |
| Greenfield city | ecode360.com | https://ecode360.com/GR4468 | no |
| Gridley city | amlegal.com | https://codelibrary.amlegal.com/codes/gridley/latest/overview | not checked (script shell) |
| Grover Beach city | amlegal.com | https://codelibrary.amlegal.com/codes/groverbeachca/latest/overview | not checked (script shell) |
| Guadalupe city | ecode360.com | https://ecode360.com/GU4932 | no |
| Gustine city | municode.com | https://library.municode.com/ca/gustine | not checked (Municode) |
| Half Moon Bay city | ecode360.com | https://ecode360.com/HA4470 | no |
| Hanford city | ecode360.com | https://ecode360.com/HA4933 | no |
| Hawaiian Gardens city | municode.com | https://library.municode.com/ca/hawaiian_gardens | not checked (Municode) |
| Hawthorne city | ecode360.com | https://ecode360.com/HA4935 | no |
| Hayward city | municode.com | https://library.municode.com/ca/hayward | not checked (Municode) |
| Healdsburg city | ecode360.com | https://ecode360.com/HE4475 | no |
| Hemet city | municode.com | https://library.municode.com/ca/hemet | not checked (Municode) |
| Hercules city | ecode360.com | https://ecode360.com/HE4476 | no |
| Hermosa Beach city | codepublishing.com | https://www.codepublishing.com/CA/HermosaBeach/ | not checked (403) |
| Hesperia city | municode.com | https://library.municode.com/ca/hesperia | not checked (Municode) |
| Hidden Hills city | municode.com | https://library.municode.com/ca/hidden_hills | not checked (Municode) |
| Highland city | ecode360.com | https://ecode360.com/HI4479 | no |
| Hillsborough town | municode.com | https://library.municode.com/ca/hillsborough | not checked (Municode) |
| Hollister city | municode.com | https://library.municode.com/ca/hollister | not checked (Municode) |
| Holtville city | ecode360.com | https://ecode360.com/HO4480 | no |
| Hughson city | ecode360.com | https://ecode360.com/HU4486 | no |
| Humboldt County | county.codes | https://humboldt.county.codes/ | not checked (403) |
| Huntington Beach city | ecode360.com | https://ecode360.com/HU4937 | yes |
| Huntington Park city | ecode360.com | https://ecode360.com/HU4938 | no |
| Huron city | municode.com | https://library.municode.com/ca/huron | not checked (Municode) |
| Imperial Beach city | ecode360.com | https://ecode360.com/IM4939 | not checked (429) |
| Imperial County | municode.com | https://library.municode.com/ca/imperial_county | not checked (Municode) |
| Indian Wells city | ecode360.com | https://ecode360.com/IN4940 | no |
| Indio city | ecode360.com | https://ecode360.com/IN6951 | no |
| Industry city | ecode360.com | https://ecode360.com/IN4941 | no |
| Inglewood city | ecode360.com | https://ecode360.com/IN4942 | no |
| Inyo County | ecode360.com | https://ecode360.com/IN4943 | no |
| Ione city | municode.com | https://library.municode.com/ca/ione | not checked (Municode) |
| Irvine city | municode.com | https://library.municode.com/ca/irvine | not checked (Municode) |
| Irwindale city | municode.com | https://library.municode.com/ca/irwindale | not checked (Municode) |
| Isleton city | municode.com | https://library.municode.com/ca/isleton | not checked (Municode) |
| Jackson city | ecode360.com | https://ecode360.com/JA4944 | no |
| Jurupa Valley city | municode.com | https://library.municode.com/ca/jurupa_valley | not checked (Municode) |
| Kerman city | ecode360.com | https://ecode360.com/KE4495 | no |
| Kern County | municode.com | https://library.municode.com/ca/kern_county | not checked (Municode) |
| Kings County | municode.com | https://library.municode.com/ca/kings_county | not checked (Municode) |
| Kingsburg city | municode.com | https://library.municode.com/ca/kingsburg | not checked (Municode) |
| La Habra city | ecode360.com | https://ecode360.com/LA4951 | no |
| La Habra Heights city | ecode360.com | https://ecode360.com/LA4503 | no |
| La Mesa city | municode.com | https://library.municode.com/ca/la_mesa | not checked (Municode) |
| La Mirada city | amlegal.com | https://codelibrary.amlegal.com/codes/lamirada/latest/overview | not checked (script shell) |
| La Palma city | municode.com | https://library.municode.com/ca/la_palma | not checked (Municode) |
| La Puente city | amlegal.com | https://codelibrary.amlegal.com/codes/lapuente/latest/overview | not checked (script shell) |
| La Quinta city | municode.com | https://library.municode.com/ca/la_quinta | not checked (Municode) |
| La Verne city | ecode360.com | https://ecode360.com/LA6633 | no |
| Lafayette city | municode.com | https://library.municode.com/ca/lafayette | not checked (Municode) |
| Laguna Beach city | ecode360.com | https://ecode360.com/LA4953 | no |
| Laguna Hills city | ecode360.com | https://ecode360.com/LA4505 | no |
| Laguna Niguel city | amlegal.com | https://codelibrary.amlegal.com/codes/lagunaniguelca/latest/overview | not checked (script shell) |
| Laguna Woods city | municode.com | https://library.municode.com/ca/laguna_woods | not checked (Municode) |
| Lake County | municode.com | https://library.municode.com/ca/lake_county | not checked (Municode) |
| Lake Elsinore city | ecode360.com | https://ecode360.com/LA4506 | no |
| Lake Forest city | ecode360.com | https://ecode360.com/LA4954 | no |
| Lakeport city | ecode360.com | https://ecode360.com/LA4510 | no |
| Lakewood city | ecode360.com | https://ecode360.com/LA6869 | no |
| Lancaster city | municode.com | https://library.municode.com/ca/lancaster | not checked (Municode) |
| Larkspur city | municipal.codes | https://larkspur.municipal.codes/ | not checked (403) |
| Lassen County | ecode360.com | https://ecode360.com/LA4955 | no |
| Lathrop city | ecode360.com | https://ecode360.com/LA4956 | no |
| Lawndale city | ecode360.com | https://ecode360.com/LA4957 | no |
| Lemon Grove city | ecode360.com | https://ecode360.com/LE4958 | not checked (429) |
| Lemoore city | amlegal.com | https://codelibrary.amlegal.com/codes/lemooreca/latest/overview | not checked (script shell) |
| Lincoln city | municode.com | https://library.municode.com/ca/lincoln | not checked (Municode) |
| Lindsay city | municode.com | https://library.municode.com/ca/lindsay | not checked (Municode) |
| Live Oak city | ecode360.com | https://ecode360.com/LI4959 | no |
| Livermore city | ecode360.com | https://ecode360.com/LI2656 | no |
| Livingston city | amlegal.com | https://codelibrary.amlegal.com/codes/livingstonca/latest/overview | not checked (script shell) |
| Lodi city | municode.com | https://library.municode.com/ca/lodi | not checked (Municode) |
| Loma Linda city | ecode360.com | https://ecode360.com/LO4960 | yes |
| Lomita city | municode.com | https://library.municode.com/ca/lomita | not checked (Municode) |
| Lompoc city | ecode360.com | https://ecode360.com/LO4961 | no |
| Long Beach city | municode.com | https://library.municode.com/ca/long_beach | not checked (Municode) |
| Loomis town | ecode360.com | https://ecode360.com/LO4962 | no |
| Los Alamitos city | ecode360.com | https://ecode360.com/LO4963 | yes |
| Los Altos city | municode.com | https://library.municode.com/ca/los_altos | not checked (Municode) |
| Los Altos Hills town | ecode360.com | https://ecode360.com/LO4964 | no |
| Los Angeles city | amlegal.com | https://codelibrary.amlegal.com/codes/los_angeles/latest/overview | not checked (script shell) |
| Los Angeles County | municode.com | https://library.municode.com/ca/los_angeles_county | not checked (Municode) |
| Los Banos city | ecode360.com | https://ecode360.com/LO4965 | no |
| Los Gatos town | municode.com | https://library.municode.com/ca/los_gatos | not checked (Municode) |
| Lynwood city | ecode360.com | https://ecode360.com/LY4521 | no |
| Madera County | amlegal.com | https://codelibrary.amlegal.com/codes/madera/latest/overview | not checked (script shell) |
| Madera County | municode.com | https://library.municode.com/ca/madera_county | not checked (Municode) |
| Malibu city | ecode360.com | https://ecode360.com/MA5043 | no |
| Mammoth Lakes town | municode.com | https://library.municode.com/ca/mammoth_lakes | not checked (Municode) |
| Manhattan Beach city | municode.com | https://library.municode.com/ca/manhattan_beach | not checked (Municode) |
| Manteca city | ecode360.com | https://ecode360.com/MA4966 | no |
| Marin County | municode.com | https://library.municode.com/ca/marin_county | not checked (Municode) |
| Marina city | municipal.codes | https://marina.municipal.codes/ | not checked (403) |
| Mariposa County | municode.com | https://library.municode.com/ca/mariposa_county | not checked (Municode) |
| Martinez city | ecode360.com | https://ecode360.com/MA6944 | no |
| Marysville city | ecode360.com | https://ecode360.com/MA4528 | yes |
| Maywood city | municode.com | https://library.municode.com/ca/maywood | not checked (Municode) |
| McFarland city | municode.com | https://library.municode.com/ca/mcfarland | not checked (Municode) |
| Mendocino County | municode.com | https://library.municode.com/ca/mendocino_county | not checked (Municode) |
| Mendota city | municode.com | https://library.municode.com/ca/mendota | not checked (Municode) |
| Menifee city | amlegal.com | https://codelibrary.amlegal.com/codes/menifee/latest/overview | not checked (script shell) |
| Menlo Park city | ecode360.com | https://ecode360.com/ME4536 | no |
| Merced city | municode.com | https://library.municode.com/ca/merced | not checked (Municode) |
| Merced County | ecode360.com | https://ecode360.com/ME4967 | no |
| Mill Valley city | ecode360.com | https://ecode360.com/MI4968 | no |
| Millbrae city | ecode360.com | https://ecode360.com/MI4538 | no |
| Milpitas city | municode.com | https://library.municode.com/ca/milpitas | not checked (Municode) |
| Mission Viejo city | municode.com | https://library.municode.com/ca/mission_viejo | not checked (Municode) |
| Modesto city | municode.com | https://library.municode.com/ca/modesto | not checked (Municode) |
| Modoc County | municode.com | https://library.municode.com/ca/modoc_county | not checked (Municode) |
| Mono County | municode.com | https://library.municode.com/ca/mono_county | not checked (Municode) |
| Monrovia city | amlegal.com | https://codelibrary.amlegal.com/codes/monrovia/latest/overview | not checked (script shell) |
| Montague city | municipal.codes | https://montague.municipal.codes/ | not checked (403) |
| Montclair city | municode.com | https://library.municode.com/ca/montclair | not checked (Municode) |
| Monte Sereno city | municode.com | https://library.municode.com/ca/monte_sereno | not checked (Municode) |
| Montebello city | municode.com | https://library.municode.com/ca/montebello | not checked (Municode) |
| Monterey city | municipal.codes | https://monterey.municipal.codes/ | not checked (403) |
| Monterey County | municode.com | https://library.municode.com/ca/monterey_county | not checked (Municode) |
| Monterey Park city | ecode360.com | https://ecode360.com/MO4971 | no |
| Moorpark city | ecode360.com | https://ecode360.com/MO4972 | no |
| Moraga town | municode.com | https://library.municode.com/ca/moraga | not checked (Municode) |
| Moreno Valley city | ecode360.com | https://ecode360.com/MO4973 | not checked (429) |
| Morgan Hill city | municode.com | https://library.municode.com/ca/morgan_hill | not checked (Municode) |
| Morro Bay city | municode.com | https://library.municode.com/ca/morro_bay | not checked (Municode) |
| Mountain View city | municode.com | https://library.municode.com/ca/mountain_view | not checked (Municode) |
| Murrieta city | amlegal.com | https://codelibrary.amlegal.com/codes/murrieta/latest/overview | not checked (script shell) |
| Napa city | ecode360.com | https://ecode360.com/NA4976 | yes |
| Napa County | municode.com | https://library.municode.com/ca/napa_county | not checked (Municode) |
| National City city | municode.com | https://library.municode.com/ca/national_city | not checked (Municode) |
| Nevada City city | municode.com | https://library.municode.com/ca/nevada_city | not checked (Municode) |
| Nevada County | municode.com | https://library.municode.com/ca/nevada_county | not checked (Municode) |
| Newark city | municode.com | https://library.municode.com/ca/newark | not checked (Municode) |
| Newman city | ecode360.com | https://ecode360.com/NE4557 | no |
| Newport Beach city | ecode360.com | https://ecode360.com/NE4559 | yes |
| Norco city | ecode360.com | https://ecode360.com/NO4562 | no |
| Norwalk city | ecode360.com | https://ecode360.com/NO4978 | no |
| Novato city | municode.com | https://library.municode.com/ca/novato | not checked (Municode) |
| Oakdale city | ecode360.com | https://ecode360.com/OA4108 | no |
| Oakland city | municode.com | https://library.municode.com/ca/oakland | not checked (Municode) |
| Oakley city | ecode360.com | https://ecode360.com/OA4568 | no |
| Oceanside city | municode.com | https://library.municode.com/ca/oceanside | not checked (Municode) |
| Ojai city | ecode360.com | https://ecode360.com/OJ4979 | no |
| Ontario city | amlegal.com | https://codelibrary.amlegal.com/codes/ontarioca/latest/overview | not checked (script shell) |
| Orange city | ecode360.com | https://ecode360.com/OR5214 | no |
| Orange County | municode.com | https://library.municode.com/ca/orange_county | not checked (Municode) |
| Orange Cove city | municode.com | https://library.municode.com/ca/orange_cove | not checked (Municode) |
| Orinda city | municode.com | https://library.municode.com/ca/orinda | not checked (Municode) |
| Orland city | municode.com | https://library.municode.com/ca/orland | not checked (Municode) |
| Oroville city | ecode360.com | https://ecode360.com/OR4980 | yes |
| Oxnard city | amlegal.com | https://codelibrary.amlegal.com/codes/oxnard/latest/overview | not checked (script shell) |
| Pacific Grove city | ecode360.com | https://ecode360.com/PA4577 | yes |
| Pacifica city | municode.com | https://library.municode.com/ca/pacifica | not checked (Municode) |
| Palm Desert city | ecode360.com | https://ecode360.com/PA4981 | yes |
| Palm Springs city | ecode360.com | https://ecode360.com/PA4982 | yes |
| Palmdale city | ecode360.com | https://ecode360.com/PA4578 | yes |
| Palo Alto city | amlegal.com | https://codelibrary.amlegal.com/codes/paloalto/latest/overview | not checked (script shell) |
| Palos Verdes Estates city | ecode360.com | https://ecode360.com/PA4580 | no |
| Paradise town | municode.com | https://library.municode.com/ca/paradise | not checked (Municode) |
| Paramount city | ecode360.com | https://ecode360.com/PA4983 | no |
| Parlier city | municode.com | https://library.municode.com/ca/parlier | not checked (Municode) |
| Pasadena city | municode.com | https://library.municode.com/ca/pasadena | not checked (Municode) |
| Patterson city | ecode360.com | https://ecode360.com/PA4584 | no |
| Perris city | municode.com | https://library.municode.com/ca/perris | not checked (Municode) |
| Petaluma city | municipal.codes | https://petaluma.municipal.codes/ | not checked (403) |
| Pico Rivera city | ecode360.com | https://ecode360.com/PI4985 | no |
| Pinole city | amlegal.com | https://codelibrary.amlegal.com/codes/pinole/latest/overview | not checked (script shell) |
| Pismo Beach city | amlegal.com | https://codelibrary.amlegal.com/codes/pismobeach/latest/overview | not checked (script shell) |
| Pittsburg city | ecode360.com | https://ecode360.com/PI4590 | no |
| Placentia city | ecode360.com | https://ecode360.com/PL4986 | not checked (429) |
| Placer County | ecode360.com | https://ecode360.com/PL4987 | yes |
| Placerville city | amlegal.com | https://codelibrary.amlegal.com/codes/placervilleca/latest/overview | not checked (script shell) |
| Pleasant Hill city | ecode360.com | https://ecode360.com/PL4591 | no |
| Pleasanton city | ecode360.com | https://ecode360.com/PL4988 | no |
| Plumas County | municode.com | https://library.municode.com/ca/plumas_county | not checked (Municode) |
| Plymouth city | ecode360.com | https://ecode360.com/PL4989 | no |
| Point Arena city | ecode360.com | https://ecode360.com/PO4990 | no |
| Pomona city | municode.com | https://library.municode.com/ca/pomona | not checked (Municode) |
| Port Hueneme city | municode.com | https://library.municode.com/ca/port_hueneme | not checked (Municode) |
| Porterville city | amlegal.com | https://codelibrary.amlegal.com/codes/portervilleca/latest/overview | not checked (script shell) |
| Portola city | municode.com | https://library.municode.com/ca/portola | not checked (Municode) |
| Portola Valley town | municode.com | https://library.municode.com/ca/portola_valley | not checked (Municode) |
| Poway city | ecode360.com | https://ecode360.com/PO4597 | no |
| Rancho Cordova city | ecode360.com | https://ecode360.com/RA4605 | no |
| Rancho Cucamonga city | ecode360.com | https://ecode360.com/RA4992 | no |
| Rancho Mirage city | ecode360.com | https://ecode360.com/RA4993 | yes |
| Rancho Palos Verdes city | municode.com | https://library.municode.com/ca/rancho_palos_verdes | not checked (Municode) |
| Rancho Santa Margarita city | municode.com | https://library.municode.com/ca/rancho_santa_margarita | not checked (Municode) |
| Red Bluff city | amlegal.com | https://codelibrary.amlegal.com/codes/redbluff/latest/overview | not checked (script shell) |
| Redding city | municode.com | https://library.municode.com/ca/redding | not checked (Municode) |
| Redlands city | amlegal.com | https://codelibrary.amlegal.com/codes/redlandsca/latest/overview | not checked (script shell) |
| Redondo Beach city | ecode360.com | https://ecode360.com/RE4995 | yes |
| Redwood City city | municode.com | https://library.municode.com/ca/redwood_city | not checked (Municode) |
| Reedley city | amlegal.com | https://codelibrary.amlegal.com/codes/reedleyca/latest/overview | not checked (script shell) |
| Rialto city | municode.com | https://library.municode.com/ca/rialto | not checked (Municode) |
| Richmond city | municode.com | https://library.municode.com/ca/richmond | not checked (Municode) |
| Ridgecrest city | municode.com | https://library.municode.com/ca/ridgecrest | not checked (Municode) |
| Rio Dell city | ecode360.com | https://ecode360.com/RI4611 | no |
| Rio Vista city | ecode360.com | https://ecode360.com/RI4996 | no |
| Riverbank city | amlegal.com | https://codelibrary.amlegal.com/codes/riverbank/latest/overview | not checked (script shell) |
| Riverside city | municode.com | https://library.municode.com/ca/riverside | not checked (Municode) |
| Riverside County | municode.com | https://library.municode.com/ca/riverside_county | not checked (Municode) |
| Rocklin city | municode.com | https://library.municode.com/ca/rocklin | not checked (Municode) |
| Rohnert Park city | municode.com | https://library.municode.com/ca/rohnert_park | not checked (Municode) |
| Rolling Hills city | municode.com | https://library.municode.com/ca/rolling_hills | not checked (Municode) |
| Rolling Hills Estates city | municode.com | https://library.municode.com/ca/rolling_hills_estates | not checked (Municode) |
| Rosemead city | municode.com | https://library.municode.com/ca/rosemead | not checked (Municode) |
| Roseville city | ecode360.com | https://ecode360.com/RO4998 | yes |
| Sacramento city | amlegal.com | https://codelibrary.amlegal.com/codes/sacramentoca/latest/overview | not checked (script shell) |
| Sacramento County | ecode360.com | https://ecode360.com/SA4999 | yes |
| Salinas city | municode.com | https://library.municode.com/ca/salinas | not checked (Municode) |
| San Anselmo town | municode.com | https://library.municode.com/ca/san_anselmo | not checked (Municode) |
| San Benito County | amlegal.com | https://codelibrary.amlegal.com/codes/sanbenitocounty/latest/overview | not checked (script shell) |
| San Bernardino city | amlegal.com | https://codelibrary.amlegal.com/codes/sanbernardinoca/latest/overview | not checked (script shell) |
| San Bernardino County | amlegal.com | https://codelibrary.amlegal.com/codes/sanbernardino/latest/overview | not checked (script shell) |
| San Bruno city | ecode360.com | https://ecode360.com/SA5001 | no |
| San Carlos city | ecode360.com | https://ecode360.com/SA4620 | no |
| San Clemente city | municode.com | https://library.municode.com/ca/san_clemente | not checked (Municode) |
| San Diego County | amlegal.com | https://codelibrary.amlegal.com/codes/san_diego/latest/overview | not checked (script shell) |
| San Dimas city | ecode360.com | https://ecode360.com/SA5002 | no |
| San Fernando city | municode.com | https://library.municode.com/ca/san_fernando | not checked (Municode) |
| San Gabriel city | amlegal.com | https://codelibrary.amlegal.com/codes/sangabriel/latest/overview | not checked (script shell) |
| San Jacinto city | ecode360.com | https://ecode360.com/SA4621 | no |
| San Joaquin County | amlegal.com | https://codelibrary.amlegal.com/codes/sanjoaquin/latest/overview | not checked (script shell) |
| San Joaquin County | municode.com | https://library.municode.com/ca/san_joaquin_county | not checked (Municode) |
| San Jose city | municode.com | https://library.municode.com/ca/san_jose | not checked (Municode) |
| San Juan Bautista city | ecode360.com | https://ecode360.com/SA4622 | no |
| San Juan Capistrano city | ecode360.com | https://ecode360.com/SA5003 | not checked (429) |
| San Leandro city | ecode360.com | https://ecode360.com/SA5044 | yes |
| San Luis Obispo city | municipal.codes | https://sanluisobispo.municipal.codes/ | not checked (403) |
| San Luis Obispo County | municode.com | https://library.municode.com/ca/san_luis_obispo_county | not checked (Municode) |
| San Marcos city | municode.com | https://library.municode.com/ca/san_marcos | not checked (Municode) |
| San Marino city | amlegal.com | https://codelibrary.amlegal.com/codes/sanmarinoca/latest/overview | not checked (script shell) |
| San Mateo County | municode.com | https://library.municode.com/ca/san_mateo_county | not checked (Municode) |
| San Pablo city | ecode360.com | https://ecode360.com/SA4625 | no |
| San Rafael city | municode.com | https://library.municode.com/ca/san_rafael | not checked (Municode) |
| Sanger city | municode.com | https://library.municode.com/ca/sanger | not checked (Municode) |
| Santa Ana city | municode.com | https://library.municode.com/ca/santa_ana | not checked (Municode) |
| Santa Barbara city | ecode360.com | https://ecode360.com/SA5006 | yes |
| Santa Barbara County | municode.com | https://library.municode.com/ca/santa_barbara_county | not checked (Municode) |
| Santa Clara city | ecode360.com | https://ecode360.com/SA4626 | yes |
| Santa Clara County | municode.com | https://library.municode.com/ca/santa_clara_county | not checked (Municode) |
| Santa Clarita city | ecode360.com | https://ecode360.com/SA4627 | no |
| Santa Cruz city | ecode360.com | https://ecode360.com/SA4628 | yes |
| Santa Cruz County | ecode360.com | https://ecode360.com/SA4770 | no |
| Santa Fe Springs city | municode.com | https://library.municode.com/ca/santa_fe_springs | not checked (Municode) |
| Santa Maria city | ecode360.com | https://ecode360.com/SA5007 | no |
| Santa Monica city | ecode360.com | https://ecode360.com/SA5008 | yes |
| Santa Paula city | amlegal.com | https://codelibrary.amlegal.com/codes/santapaula/latest/overview | not checked (script shell) |
| Santa Rosa city | ecode360.com | https://ecode360.com/SA5009 | no |
| Santee city | ecode360.com | https://ecode360.com/SA5010 | yes |
| Saratoga city | municode.com | https://library.municode.com/ca/saratoga | not checked (Municode) |
| Sausalito city | ecode360.com | https://ecode360.com/SA4880 | no |
| Scotts Valley city | municode.com | https://library.municode.com/ca/scotts_valley | not checked (Municode) |
| Seal Beach city | ecode360.com | https://ecode360.com/SE5012 | yes |
| Seaside city | ecode360.com | https://ecode360.com/SE4632 | no |
| Sebastopol city | municipal.codes | https://sebastopol.municipal.codes/ | not checked (403) |
| Selma city | amlegal.com | https://codelibrary.amlegal.com/codes/selmaca/latest/overview | not checked (script shell) |
| Shafter city | municode.com | https://library.municode.com/ca/shafter | not checked (Municode) |
| Shasta County | municode.com | https://library.municode.com/ca/shasta_county | not checked (Municode) |
| Shasta Lake city | municode.com | https://library.municode.com/ca/shasta_lake | not checked (Municode) |
| Sierra County | county.codes | https://sierra.county.codes/ | not checked (403) |
| Sierra Madre city | municode.com | https://library.municode.com/ca/sierra_madre | not checked (Municode) |
| Signal Hill city | amlegal.com | https://codelibrary.amlegal.com/codes/signalhill/latest/overview | not checked (script shell) |
| Simi Valley city | municode.com | https://library.municode.com/ca/simi_valley | not checked (Municode) |
| Siskiyou County | municode.com | https://library.municode.com/ca/siskiyou_county | not checked (Municode) |
| Solana Beach city | codepublishing.com | https://www.codepublishing.com/CA/SolanaBeach/ | not checked (403) |
| Solano County | ecode360.com | https://ecode360.com/SO4784 | no |
| Soledad city | municode.com | https://library.municode.com/ca/soledad | not checked (Municode) |
| Solvang city | ecode360.com | https://ecode360.com/SO5014 | no |
| Sonoma city | municipal.codes | https://sonoma.municipal.codes/ | not checked (403) |
| Sonoma County | municode.com | https://library.municode.com/ca/sonoma_county | not checked (Municode) |
| Sonora city | municode.com | https://library.municode.com/ca/sonora | not checked (Municode) |
| South El Monte city | ecode360.com | https://ecode360.com/SO5015 | no |
| South Gate city | ecode360.com | https://ecode360.com/SO4650 | no |
| South Lake Tahoe city | ecode360.com | https://ecode360.com/SO4651 | no |
| South Pasadena city | ecode360.com | https://ecode360.com/SO4652 | not checked (429) |
| South San Francisco city | ecode360.com | https://ecode360.com/SO5016 | no |
| St. Helena city | municipal.codes | https://sthelena.municipal.codes/ | not checked (403) |
| Stanislaus County | ecode360.com | https://ecode360.com/ST5017 | no |
| Stanton city | ecode360.com | https://ecode360.com/ST5018 | no |
| Stockton city | ecode360.com | https://ecode360.com/ST5019 | yes |
| Suisun City city | municode.com | https://library.municode.com/ca/suisun_city | not checked (Municode) |
| Sunnyvale city | ecode360.com | https://ecode360.com/SU5020 | yes |
| Susanville city | ecode360.com | https://ecode360.com/SU5021 | no |
| Sutter County | municode.com | https://library.municode.com/ca/sutter_county | not checked (Municode) |
| Sutter Creek city | municode.com | https://library.municode.com/ca/sutter_creek | not checked (Municode) |
| Taft city | amlegal.com | https://codelibrary.amlegal.com/codes/taftca/latest/overview | not checked (script shell) |
| Tehachapi city | municode.com | https://library.municode.com/ca/tehachapi | not checked (Municode) |
| Tehama city | municode.com | https://library.municode.com/ca/tehama | not checked (Municode) |
| Tehama County | municode.com | https://library.municode.com/ca/tehama_county | not checked (Municode) |
| Temecula city | ecode360.com | https://ecode360.com/TE5022 | no |
| Thousand Oaks city | amlegal.com | https://codelibrary.amlegal.com/codes/thousandoaks/latest/overview | not checked (script shell) |
| Tiburon town | municode.com | https://library.municode.com/ca/tiburon | not checked (Municode) |
| Torrance city | ecode360.com | https://ecode360.com/TO4671 | yes |
| Tracy city | municode.com | https://library.municode.com/ca/tracy | not checked (Municode) |
| Trinidad city | ecode360.com | https://ecode360.com/TR4672 | no |
| Trinity County | municode.com | https://library.municode.com/ca/trinity_county | not checked (Municode) |
| Truckee town | municode.com | https://library.municode.com/ca/truckee | not checked (Municode) |
| Tulare city | amlegal.com | https://codelibrary.amlegal.com/codes/tulare/latest/overview | not checked (script shell) |
| Tulare County | ecode360.com | https://ecode360.com/TU4850 | no |
| Turlock city | ecode360.com | https://ecode360.com/TU4675 | no |
| Tustin city | municode.com | https://library.municode.com/ca/tustin | not checked (Municode) |
| Twentynine Palms city | municode.com | https://library.municode.com/ca/twentynine_palms | not checked (Municode) |
| Ukiah city | ecode360.com | https://ecode360.com/UK4676 | no |
| Upland city | ecode360.com | https://ecode360.com/UP5026 | no |
| Vacaville city | ecode360.com | https://ecode360.com/VA4679 | no |
| Vallejo city | municode.com | https://library.municode.com/ca/vallejo | not checked (Municode) |
| Ventura County | municode.com | https://library.municode.com/ca/ventura_county | not checked (Municode) |
| Vernon city | ecode360.com | https://ecode360.com/VE5027 | yes |
| Victorville city | municode.com | https://library.municode.com/ca/victorville | not checked (Municode) |
| Villa Park city | municode.com | https://library.municode.com/ca/villa_park | not checked (Municode) |
| Visalia city | amlegal.com | https://codelibrary.amlegal.com/codes/visalia/latest/overview | not checked (script shell) |
| Walnut city | ecode360.com | https://ecode360.com/WA5028 | no |
| Walnut Creek city | ecode360.com | https://ecode360.com/WA4684 | no |
| Wasco city | municipal.codes | https://wasco.municipal.codes/ | not checked (403) |
| Waterford city | ecode360.com | https://ecode360.com/WA5030 | no |
| Watsonville city | ecode360.com | https://ecode360.com/WA4689 | yes |
| Weed city | municode.com | https://library.municode.com/ca/weed | not checked (Municode) |
| West Covina city | municode.com | https://library.municode.com/ca/west_covina | not checked (Municode) |
| West Hollywood city | ecode360.com | https://ecode360.com/WE5031 | not checked (429) |
| West Sacramento city | ecode360.com | https://ecode360.com/WE5032 | no |
| Westlake Village city | municode.com | https://library.municode.com/ca/westlake_village | not checked (Municode) |
| Westminster city | ecode360.com | https://ecode360.com/WE5033 | no |
| Wheatland city | ecode360.com | https://ecode360.com/WH5034 | no |
| Whittier city | municode.com | https://library.municode.com/ca/whittier | not checked (Municode) |
| Wildomar city | ecode360.com | https://ecode360.com/WI5035 | no |
| Williams city | municode.com | https://library.municode.com/ca/williams | not checked (Municode) |
| Willits city | municode.com | https://library.municode.com/ca/willits | not checked (Municode) |
| Willows city | ecode360.com | https://ecode360.com/WI4695 | no |
| Windsor town | municode.com | https://library.municode.com/ca/windsor | not checked (Municode) |
| Winters city | ecode360.com | https://ecode360.com/WI4698 | no |
| Woodlake city | municode.com | https://library.municode.com/ca/woodlake | not checked (Municode) |
| Woodland city | ecode360.com | https://ecode360.com/WO5036 | no |
| Woodside town | municode.com | https://library.municode.com/ca/woodside | not checked (Municode) |
| Yolo County | amlegal.com | https://codelibrary.amlegal.com/codes/yolocounty/latest/overview | not checked (script shell) |
| Yorba Linda city | ecode360.com | https://ecode360.com/YO5039 | no |
| Yreka city | municode.com | https://library.municode.com/ca/yreka | not checked (Municode) |
| Yuba City city | municode.com | https://library.municode.com/ca/yuba_city | not checked (Municode) |
| Yuba County | municode.com | https://library.municode.com/ca/yuba_county | not checked (Municode) |
| Yucaipa city | ecode360.com | https://ecode360.com/YU5041 | no |

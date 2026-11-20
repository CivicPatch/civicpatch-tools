# New York: where each place's code is published

Step 1.4 of the `state-offices` skill. Layers: [2026-11-20-research-ny-layers.md](2026-11-20-research-ny-layers.md).

## Sources, 2026-11-20

- **ICC Code Solutions**, https://www.icccodesolutions.org/text-library/ (`div.state NY`): 725 entries, 723
  eCode360 and 2 American Legal. The page refused a plain curl (403) and served pipeline 1's `plain.fetch`.
- **Municode**, https://api.municode.com/Clients/stateAbbr?stateAbbr=NY, opened in a browser and saved:
  `plans/research/new-york-state-offices/municode-ny-2026-11-20.json`, 16 clients. The code url below is built from
  `ClientName` (`library.municode.com/ny/<name>`) and is not checked.

Matched to `data_source/ny/{local,counties}/jurisdictions.yml` with pipeline 1's `charter_title_matches`
(`pipelines/src/runners/pipeline01_governing_law_collector/finders/state_index.py`): ICC titles "{lsad} of {place}"
and "{place} {lsad}", Municode "{place}". Script: Maine's matcher with the state as an argument (session
scratchpad, not kept).

| Directory | Entries | Matched | Ambiguous | Unmatched |
|---|---|---|---|---|
| ICC | 725 | 704 (52 cities, 327 towns, 314 villages, 11 counties) | 7 | 14 |
| Municode | 16 | 9, plus 5 settled by `ClassificationId` | 5 | 2 |

### Ambiguous

- ICC, two towns of one name in different counties: Town of Albion, Brighton, Chester, Clinton, Dickinson,
  Greenville (twice). The title doesn't name the county; a person picks.
- Municode, a bare name that fits a town and a city or village: Elmira, Goshen, Greenwich, Lewiston, Tonawanda.
  Settled in the table by the client's `ClassificationId`, read as 2 city, 4 county, 6 town, 9 village from the
  unambiguous clients (Syracuse 2, Westchester County 4, Vestal 6, Kenmore 9): Elmira city, Goshen village,
  Greenwich town, Lewiston village, Tonawanda city. That reading is an inference, not documented by Municode.

### Unmatched, by name form

- Spacing and case: Town of DeWitt (De Witt town), Town of LeRay (Le Ray town), Town and Village of LeRoy (Le Roy),
  Village of The Branch, Village of Head-of-the-Harbor, Village of Dering Harbor.
- Coterminous town-villages titled "Town/Village of": East Rochester, Harrison, Mount Kisco.
- Not a place's code: Fairport OCED, Town of Hempstead BZO, City of New York Local Building Codes.
- Village of South Nyack: dissolved, not in the Census list.
- Municode "Orange County", "Westchester County": the "{place}" title doesn't fit a county's name.

## What a fetch allowed

| Host | Places | Plain fetch (`plain.fetch`) | Charter checked |
|---|---|---|---|
| eCode360 | 702 | served, until 429 (rate limit) after about 50 in a row | 51 cities: 50 yes, Olean refused 429 |
| American Legal | 2 | served | New York City: yes |
| Municode | 14 | not tried (refuses agents) | none |

"Charter in the code" means the code's front page mentions "charter": a substring check of the converted table of
contents, results in `plans/research/new-york-state-offices/city-charters-ecode360-2026-11-20.tsv`. Towns have no
charter (layers doc); villages and counties weren't checked (12 charter villages unnamed; 23 charter counties are in
the counties doc). eCode360 let the fetch through for New York on 2026-11-20; it refused Maine's that morning.

Of 1,593 places (with 5 boroughs), 716 are in a directory (Bellport village and Greenwich town in both); 877 are in neither. 57 of the 62 cities are.

## Places

| Place | Host | Code url | Charter in the code |
|---|---|---|---|
| Adams village | ecode360.com | https://ecode360.com/AD4005 | not checked (Village Law; 12 charter villages unnamed) |
| Airmont village | ecode360.com | https://ecode360.com/AI1857 | not checked (Village Law; 12 charter villages unnamed) |
| Akron village | ecode360.com | https://ecode360.com/AK1601 | not checked (Village Law; 12 charter villages unnamed) |
| Albany County | ecode360.com | https://ecode360.com/AL3660 | not checked |
| Albany city | ecode360.com | https://ecode360.com/AL0934 | yes |
| Albion village | ecode360.com | https://ecode360.com/AL0001 | not checked (Village Law; 12 charter villages unnamed) |
| Alden town | ecode360.com | https://ecode360.com/AL0002 | n/a (a town has no charter) |
| Alexandria Bay village | ecode360.com | https://ecode360.com/AL1193 | not checked (Village Law; 12 charter villages unnamed) |
| Altamont village | ecode360.com | https://ecode360.com/AL2859 | not checked (Village Law; 12 charter villages unnamed) |
| Amenia town | ecode360.com | https://ecode360.com/AM1016 | n/a (a town has no charter) |
| Amherst town | ecode360.com | https://ecode360.com/AM0003 | n/a (a town has no charter) |
| Amityville village | ecode360.com | https://ecode360.com/AM0762 | not checked (Village Law; 12 charter villages unnamed) |
| Amsterdam city | ecode360.com | https://ecode360.com/AM0234 | yes |
| Ancram town | ecode360.com | https://ecode360.com/AN3065 | n/a (a town has no charter) |
| Angola village | ecode360.com | https://ecode360.com/AN2625 | not checked (Village Law; 12 charter villages unnamed) |
| Ardsley village | ecode360.com | https://ecode360.com/AR0005 | not checked (Village Law; 12 charter villages unnamed) |
| Asharoken village | ecode360.com | https://ecode360.com/AS1230 | not checked (Village Law; 12 charter villages unnamed) |
| Athens town | ecode360.com | https://ecode360.com/AT1724 | n/a (a town has no charter) |
| Athens village | ecode360.com | https://ecode360.com/AT0523 | not checked (Village Law; 12 charter villages unnamed) |
| Atlantic Beach village | ecode360.com | https://ecode360.com/AT1401 | not checked (Village Law; 12 charter villages unnamed) |
| Auburn city | ecode360.com | https://ecode360.com/AU1877 | yes |
| Aurora town | ecode360.com | https://ecode360.com/AU1109 | n/a (a town has no charter) |
| Austerlitz town | ecode360.com | https://ecode360.com/AU3009 | n/a (a town has no charter) |
| Avon town | ecode360.com | https://ecode360.com/AV1136 | n/a (a town has no charter) |
| Avon village | ecode360.com | https://ecode360.com/AV0006 | not checked (Village Law; 12 charter villages unnamed) |
| Babylon town | ecode360.com | https://ecode360.com/BA0924 | n/a (a town has no charter) |
| Babylon village | ecode360.com | https://ecode360.com/BA0592 | not checked (Village Law; 12 charter villages unnamed) |
| Bainbridge village | ecode360.com | https://ecode360.com/BA1457 | not checked (Village Law; 12 charter villages unnamed) |
| Baldwinsville village | ecode360.com | https://ecode360.com/BA0380 | not checked (Village Law; 12 charter villages unnamed) |
| Ballston Spa village | ecode360.com | https://ecode360.com/BA0385 | not checked (Village Law; 12 charter villages unnamed) |
| Ballston town | ecode360.com | https://ecode360.com/BA1734 | n/a (a town has no charter) |
| Barre town | ecode360.com | https://ecode360.com/BA2836 | n/a (a town has no charter) |
| Barton town | ecode360.com | https://ecode360.com/BA1404 | n/a (a town has no charter) |
| Batavia city | ecode360.com | https://ecode360.com/BA1824 | yes |
| Batavia town | ecode360.com | https://ecode360.com/BA1901 | n/a (a town has no charter) |
| Bath town | ecode360.com | https://ecode360.com/BA1080 | n/a (a town has no charter) |
| Bath village | ecode360.com | https://ecode360.com/BA0734 | not checked (Village Law; 12 charter villages unnamed) |
| Baxter Estates village | ecode360.com | https://ecode360.com/BA1157 | not checked (Village Law; 12 charter villages unnamed) |
| Bayville village | ecode360.com | https://ecode360.com/BA0509 | not checked (Village Law; 12 charter villages unnamed) |
| Beacon city | ecode360.com | https://ecode360.com/BE0803 | yes |
| Bedford town | ecode360.com | https://ecode360.com/BE0790 | n/a (a town has no charter) |
| Beekman town | ecode360.com | https://ecode360.com/BE1259 | n/a (a town has no charter) |
| Belle Terre village | ecode360.com | https://ecode360.com/BE1338 | not checked (Village Law; 12 charter villages unnamed) |
| Bellerose village | ecode360.com | https://ecode360.com/BE0584 | not checked (Village Law; 12 charter villages unnamed) |
| Bellport village | ecode360.com | https://ecode360.com/BE0526 | not checked (Village Law; 12 charter villages unnamed) |
| Bellport village | municode | https://library.municode.com/ny/bellport | not checked (Village Law; 12 charter villages unnamed) |
| Bergen town | ecode360.com | https://ecode360.com/BE2866 | n/a (a town has no charter) |
| Berne town | ecode360.com | https://ecode360.com/BE2069 | n/a (a town has no charter) |
| Bethel town | ecode360.com | https://ecode360.com/BE0597 | n/a (a town has no charter) |
| Bethlehem town | ecode360.com | https://ecode360.com/BE1011 | n/a (a town has no charter) |
| Big Flats town | municode | https://library.municode.com/ny/big_flats | n/a (a town has no charter) |
| Binghamton city | ecode360.com | https://ecode360.com/BI1506 | yes |
| Binghamton town | ecode360.com | https://ecode360.com/BI0332 | n/a (a town has no charter) |
| Blasdell village | ecode360.com | https://ecode360.com/BL0009 | not checked (Village Law; 12 charter villages unnamed) |
| Bloomfield village | ecode360.com | https://ecode360.com/BL4201 | not checked (Village Law; 12 charter villages unnamed) |
| Blooming Grove town | ecode360.com | https://ecode360.com/BL1669 | n/a (a town has no charter) |
| Bloomingburg village | ecode360.com | https://ecode360.com/BL4000 | not checked (Village Law; 12 charter villages unnamed) |
| Bolton town | ecode360.com | https://ecode360.com/BO1894 | n/a (a town has no charter) |
| Boonville village | ecode360.com | https://ecode360.com/BO0378 | not checked (Village Law; 12 charter villages unnamed) |
| Boston town | ecode360.com | https://ecode360.com/BO0557 | n/a (a town has no charter) |
| Brant town | ecode360.com | https://ecode360.com/BR0349 | n/a (a town has no charter) |
| Brewster village | ecode360.com | https://ecode360.com/BR1329 | not checked (Village Law; 12 charter villages unnamed) |
| Briarcliff Manor village | ecode360.com | https://ecode360.com/BR1701 | not checked (Village Law; 12 charter villages unnamed) |
| Brightwaters village | ecode360.com | https://ecode360.com/BR0326 | not checked (Village Law; 12 charter villages unnamed) |
| Bristol town | ecode360.com | https://ecode360.com/BR4013 | n/a (a town has no charter) |
| Brockport village | ecode360.com | https://ecode360.com/BR0227 | not checked (Village Law; 12 charter villages unnamed) |
| Bronxville village | ecode360.com | https://ecode360.com/BR1468 | not checked (Village Law; 12 charter villages unnamed) |
| Brookhaven town | ecode360.com | https://ecode360.com/BR0012 | n/a (a town has no charter) |
| Brownville town | ecode360.com | https://ecode360.com/BR0500 | n/a (a town has no charter) |
| Brownville village | ecode360.com | https://ecode360.com/BR0916 | not checked (Village Law; 12 charter villages unnamed) |
| Brutus town | ecode360.com | https://ecode360.com/BR1361 | n/a (a town has no charter) |
| Buchanan village | ecode360.com | https://ecode360.com/BU0230 | not checked (Village Law; 12 charter villages unnamed) |
| Buffalo city | ecode360.com | https://ecode360.com/BU1237 | yes |
| Busti town | ecode360.com | https://ecode360.com/BU3048 | n/a (a town has no charter) |
| Caledonia town | ecode360.com | https://ecode360.com/CA0014 | n/a (a town has no charter) |
| Caledonia village | ecode360.com | https://ecode360.com/CA0015 | not checked (Village Law; 12 charter villages unnamed) |
| Cambria town | ecode360.com | https://ecode360.com/CA6686 | n/a (a town has no charter) |
| Camden town | ecode360.com | https://ecode360.com/CA4157 | n/a (a town has no charter) |
| Camillus village | ecode360.com | https://ecode360.com/CA1012 | not checked (Village Law; 12 charter villages unnamed) |
| Canajoharie village | ecode360.com | https://ecode360.com/CA0018 | not checked (Village Law; 12 charter villages unnamed) |
| Canandaigua city | ecode360.com | https://ecode360.com/CA2661 | yes |
| Canandaigua town | ecode360.com | https://ecode360.com/CA0614 | n/a (a town has no charter) |
| Canastota village | ecode360.com | https://ecode360.com/CA0356 | not checked (Village Law; 12 charter villages unnamed) |
| Canisteo village | ecode360.com | https://ecode360.com/CA0946 | not checked (Village Law; 12 charter villages unnamed) |
| Canton town | ecode360.com | https://ecode360.com/CA0632 | n/a (a town has no charter) |
| Canton village | ecode360.com | https://ecode360.com/CA0020 | not checked (Village Law; 12 charter villages unnamed) |
| Carmel town | ecode360.com | https://ecode360.com/CA0321 | n/a (a town has no charter) |
| Carthage village | ecode360.com | https://ecode360.com/CA0146 | not checked (Village Law; 12 charter villages unnamed) |
| Castleton-on-Hudson village | ecode360.com | https://ecode360.com/CA1654 | not checked (Village Law; 12 charter villages unnamed) |
| Cato town | ecode360.com | https://ecode360.com/CA1278 | n/a (a town has no charter) |
| Catskill town | ecode360.com | https://ecode360.com/CA0628 | n/a (a town has no charter) |
| Cayuga County | ecode360.com | https://ecode360.com/CA2794 | not checked |
| Cayuga Heights village | ecode360.com | https://ecode360.com/CA3773 | not checked (Village Law; 12 charter villages unnamed) |
| Cazenovia town | ecode360.com | https://ecode360.com/CA0021 | n/a (a town has no charter) |
| Cazenovia village | ecode360.com | https://ecode360.com/CA1699 | not checked (Village Law; 12 charter villages unnamed) |
| Cedarhurst village | ecode360.com | https://ecode360.com/CE1549 | not checked (Village Law; 12 charter villages unnamed) |
| Celoron village | ecode360.com | https://ecode360.com/CE0023 | not checked (Village Law; 12 charter villages unnamed) |
| Central Square village | ecode360.com | https://ecode360.com/CE1952 | not checked (Village Law; 12 charter villages unnamed) |
| Centre Island village | ecode360.com | https://ecode360.com/CE1185 | not checked (Village Law; 12 charter villages unnamed) |
| Champlain town | ecode360.com | https://ecode360.com/CH1029 | n/a (a town has no charter) |
| Chatham town | ecode360.com | https://ecode360.com/CH1668 | n/a (a town has no charter) |
| Chatham village | ecode360.com | https://ecode360.com/CH1066 | not checked (Village Law; 12 charter villages unnamed) |
| Chautauqua town | ecode360.com | https://ecode360.com/CH1389 | n/a (a town has no charter) |
| Cheektowaga town | ecode360.com | https://ecode360.com/CH0381 | n/a (a town has no charter) |
| Chemung town | ecode360.com | https://ecode360.com/CH6855 | n/a (a town has no charter) |
| Chenango town | ecode360.com | https://ecode360.com/CH0439 | n/a (a town has no charter) |
| Chester village | ecode360.com | https://ecode360.com/CH0667 | not checked (Village Law; 12 charter villages unnamed) |
| Chestnut Ridge village | ecode360.com | https://ecode360.com/CH3561 | not checked (Village Law; 12 charter villages unnamed) |
| Chili town | ecode360.com | https://ecode360.com/CH0024 | n/a (a town has no charter) |
| Chittenango village | ecode360.com | https://ecode360.com/CH0025 | not checked (Village Law; 12 charter villages unnamed) |
| Churchville village | ecode360.com | https://ecode360.com/CH0874 | not checked (Village Law; 12 charter villages unnamed) |
| Cicero town | ecode360.com | https://ecode360.com/CI1861 | n/a (a town has no charter) |
| Clarence town | ecode360.com | https://ecode360.com/CL0026 | n/a (a town has no charter) |
| Clarkson town | ecode360.com | https://ecode360.com/CL0027 | n/a (a town has no charter) |
| Clarkstown town | ecode360.com | https://ecode360.com/CL0028 | n/a (a town has no charter) |
| Claverack town | ecode360.com | https://ecode360.com/CL3187 | n/a (a town has no charter) |
| Clay town | ecode360.com | https://ecode360.com/CL1598 | n/a (a town has no charter) |
| Clayton town | ecode360.com | https://ecode360.com/CL3056 | n/a (a town has no charter) |
| Clayton village | ecode360.com | https://ecode360.com/CL0983 | not checked (Village Law; 12 charter villages unnamed) |
| Clifton Park town | ecode360.com | https://ecode360.com/CL1051 | n/a (a town has no charter) |
| Clifton Springs village | ecode360.com | https://ecode360.com/CL0029 | not checked (Village Law; 12 charter villages unnamed) |
| Clinton village | ecode360.com | https://ecode360.com/CL0030 | not checked (Village Law; 12 charter villages unnamed) |
| Clyde village | ecode360.com | https://ecode360.com/CL2787 | not checked (Village Law; 12 charter villages unnamed) |
| Cobleskill town | ecode360.com | https://ecode360.com/CO2116 | n/a (a town has no charter) |
| Cobleskill village | ecode360.com | https://ecode360.com/CO0031 | not checked (Village Law; 12 charter villages unnamed) |
| Cochecton town | ecode360.com | https://ecode360.com/CO3144 | n/a (a town has no charter) |
| Coeymans town | ecode360.com | https://ecode360.com/CO0785 | n/a (a town has no charter) |
| Cohoes city | ecode360.com | https://ecode360.com/CO0376 | yes |
| Colden town | ecode360.com | https://ecode360.com/CO0951 | n/a (a town has no charter) |
| Collins town | ecode360.com | https://ecode360.com/CO2912 | n/a (a town has no charter) |
| Colonie town | ecode360.com | https://ecode360.com/CO0780 | n/a (a town has no charter) |
| Colonie village | ecode360.com | https://ecode360.com/CO0033 | not checked (Village Law; 12 charter villages unnamed) |
| Colton town | ecode360.com | https://ecode360.com/CO2138 | n/a (a town has no charter) |
| Concord town | ecode360.com | https://ecode360.com/CO1501 | n/a (a town has no charter) |
| Conesus town | ecode360.com | https://ecode360.com/CO1949 | n/a (a town has no charter) |
| Cooperstown village | ecode360.com | https://ecode360.com/CO2139 | not checked (Village Law; 12 charter villages unnamed) |
| Copake town | ecode360.com | https://ecode360.com/CO1534 | n/a (a town has no charter) |
| Corinth town | ecode360.com | https://ecode360.com/CO1533 | n/a (a town has no charter) |
| Corinth village | ecode360.com | https://ecode360.com/CO0733 | not checked (Village Law; 12 charter villages unnamed) |
| Corning city | ecode360.com | https://ecode360.com/CO1368 | yes |
| Corning town | ecode360.com | https://ecode360.com/CO3940 | n/a (a town has no charter) |
| Cornwall town | ecode360.com | https://ecode360.com/CO0034 | n/a (a town has no charter) |
| Cornwall-on-Hudson village | ecode360.com | https://ecode360.com/CO0152 | not checked (Village Law; 12 charter villages unnamed) |
| Cortland city | ecode360.com | https://ecode360.com/CO0935 | yes |
| Cortlandt town | ecode360.com | https://ecode360.com/CO0244 | n/a (a town has no charter) |
| Cortlandville town | ecode360.com | https://ecode360.com/CO1314 | n/a (a town has no charter) |
| Cove Neck village | ecode360.com | https://ecode360.com/CO1946 | not checked (Village Law; 12 charter villages unnamed) |
| Coxsackie town | ecode360.com | https://ecode360.com/CO1196 | n/a (a town has no charter) |
| Coxsackie village | ecode360.com | https://ecode360.com/CO0740 | not checked (Village Law; 12 charter villages unnamed) |
| Crawford town | ecode360.com | https://ecode360.com/CR0817 | n/a (a town has no charter) |
| Croton-on-Hudson village | ecode360.com | https://ecode360.com/CR0035 | not checked (Village Law; 12 charter villages unnamed) |
| Cuba village | ecode360.com | https://ecode360.com/CU0649 | not checked (Village Law; 12 charter villages unnamed) |
| Dannemora village | ecode360.com | https://ecode360.com/DA1007 | not checked (Village Law; 12 charter villages unnamed) |
| Dansville village | ecode360.com | https://ecode360.com/DA0036 | not checked (Village Law; 12 charter villages unnamed) |
| Deerpark town | ecode360.com | https://ecode360.com/DE0596 | n/a (a town has no charter) |
| Delaware town | ecode360.com | https://ecode360.com/DE3566 | n/a (a town has no charter) |
| Delhi village | ecode360.com | https://ecode360.com/DE0305 | not checked (Village Law; 12 charter villages unnamed) |
| Depew village | ecode360.com | https://ecode360.com/DE1925 | not checked (Village Law; 12 charter villages unnamed) |
| Deposit village | ecode360.com | https://ecode360.com/DE0037 | not checked (Village Law; 12 charter villages unnamed) |
| Dobbs Ferry village | ecode360.com | https://ecode360.com/DO0599 | not checked (Village Law; 12 charter villages unnamed) |
| Dover town | ecode360.com | https://ecode360.com/DO1139 | n/a (a town has no charter) |
| Dryden town | ecode360.com | https://ecode360.com/DR3901 | n/a (a town has no charter) |
| Dryden village | ecode360.com | https://ecode360.com/DR6598 | not checked (Village Law; 12 charter villages unnamed) |
| Dundee village | ecode360.com | https://ecode360.com/DU1149 | not checked (Village Law; 12 charter villages unnamed) |
| Dutchess County | ecode360.com | https://ecode360.com/DU1148 | not checked |
| East Aurora village | ecode360.com | https://ecode360.com/EA0398 | not checked (Village Law; 12 charter villages unnamed) |
| East Bloomfield town | ecode360.com | https://ecode360.com/EA1606 | n/a (a town has no charter) |
| East Fishkill town | ecode360.com | https://ecode360.com/EA0495 | n/a (a town has no charter) |
| East Greenbush town | ecode360.com | https://ecode360.com/EA0039 | n/a (a town has no charter) |
| East Hampton town | ecode360.com | https://ecode360.com/EA0658 | n/a (a town has no charter) |
| East Hampton village | ecode360.com | https://ecode360.com/EA0361 | not checked (Village Law; 12 charter villages unnamed) |
| East Hills village | ecode360.com | https://ecode360.com/EA0847 | not checked (Village Law; 12 charter villages unnamed) |
| East Rockaway village | ecode360.com | https://ecode360.com/EA0899 | not checked (Village Law; 12 charter villages unnamed) |
| East Syracuse village | ecode360.com | https://ecode360.com/EA1636 | not checked (Village Law; 12 charter villages unnamed) |
| East Williston village | ecode360.com | https://ecode360.com/EA1896 | not checked (Village Law; 12 charter villages unnamed) |
| Eaton town | ecode360.com | https://ecode360.com/EA1670 | n/a (a town has no charter) |
| Eden town | ecode360.com | https://ecode360.com/ED1729 | n/a (a town has no charter) |
| Elbridge town | ecode360.com | https://ecode360.com/EL1801 | n/a (a town has no charter) |
| Ellenville village | ecode360.com | https://ecode360.com/EL0977 | not checked (Village Law; 12 charter villages unnamed) |
| Ellicott town | ecode360.com | https://ecode360.com/EL0042 | n/a (a town has no charter) |
| Elma town | ecode360.com | https://ecode360.com/EL0765 | n/a (a town has no charter) |
| Elmira Heights village | ecode360.com | https://ecode360.com/EL1528 | not checked (Village Law; 12 charter villages unnamed) |
| Elmira city | municode | https://library.municode.com/ny/elmira | not checked (Municode refuses agents) |
| Elmira town | ecode360.com | https://ecode360.com/EL2935 | n/a (a town has no charter) |
| Elmsford village | ecode360.com | https://ecode360.com/EL0274 | not checked (Village Law; 12 charter villages unnamed) |
| Endicott village | ecode360.com | https://ecode360.com/EN1075 | not checked (Village Law; 12 charter villages unnamed) |
| Esopus town | ecode360.com | https://ecode360.com/ES0782 | n/a (a town has no charter) |
| Evans town | ecode360.com | https://ecode360.com/EV0044 | n/a (a town has no charter) |
| Fabius town | ecode360.com | https://ecode360.com/FA3977 | n/a (a town has no charter) |
| Fair Haven village | ecode360.com | https://ecode360.com/FA0347 | not checked (Village Law; 12 charter villages unnamed) |
| Fairport village | ecode360.com | https://ecode360.com/FA0327 | not checked (Village Law; 12 charter villages unnamed) |
| Falconer village | ecode360.com | https://ecode360.com/FA0045 | not checked (Village Law; 12 charter villages unnamed) |
| Fallsburg town | ecode360.com | https://ecode360.com/FA1866 | n/a (a town has no charter) |
| Farmingdale village | ecode360.com | https://ecode360.com/FA0311 | not checked (Village Law; 12 charter villages unnamed) |
| Farmington town | ecode360.com | https://ecode360.com/FA0309 | n/a (a town has no charter) |
| Fayetteville village | ecode360.com | https://ecode360.com/FA0988 | not checked (Village Law; 12 charter villages unnamed) |
| Fenton town | ecode360.com | https://ecode360.com/FE1565 | n/a (a town has no charter) |
| Fishkill town | ecode360.com | https://ecode360.com/FI0709 | n/a (a town has no charter) |
| Fishkill village | ecode360.com | https://ecode360.com/FI0778 | not checked (Village Law; 12 charter villages unnamed) |
| Floral Park village | ecode360.com | https://ecode360.com/FL0046 | not checked (Village Law; 12 charter villages unnamed) |
| Florida village | ecode360.com | https://ecode360.com/FL0922 | not checked (Village Law; 12 charter villages unnamed) |
| Flower Hill village | ecode360.com | https://ecode360.com/FL0568 | not checked (Village Law; 12 charter villages unnamed) |
| Fonda village | ecode360.com | https://ecode360.com/FO3609 | not checked (Village Law; 12 charter villages unnamed) |
| Forestburgh town | ecode360.com | https://ecode360.com/FO0593 | n/a (a town has no charter) |
| Fort Edward town | ecode360.com | https://ecode360.com/FO0047 | n/a (a town has no charter) |
| Fort Edward village | ecode360.com | https://ecode360.com/FO0976 | not checked (Village Law; 12 charter villages unnamed) |
| Fort Plain village | ecode360.com | https://ecode360.com/FO1511 | not checked (Village Law; 12 charter villages unnamed) |
| Frankfort town | ecode360.com | https://ecode360.com/FR0933 | n/a (a town has no charter) |
| Franklinville town | codelibrary.amlegal.com | https://codelibrary.amlegal.com/codes/franklinville/latest/overview | n/a (a town has no charter) |
| Freeport village | ecode360.com | https://ecode360.com/FR0651 | not checked (Village Law; 12 charter villages unnamed) |
| Fulton city | ecode360.com | https://ecode360.com/FU0049 | yes |
| Fultonville village | ecode360.com | https://ecode360.com/FU1650 | not checked (Village Law; 12 charter villages unnamed) |
| Galway town | ecode360.com | https://ecode360.com/GA1504 | n/a (a town has no charter) |
| Garden City village | ecode360.com | https://ecode360.com/GA0634 | not checked (Village Law; 12 charter villages unnamed) |
| Gardiner town | ecode360.com | https://ecode360.com/GA1939 | n/a (a town has no charter) |
| Gates town | ecode360.com | https://ecode360.com/GA0050 | n/a (a town has no charter) |
| Geddes town | ecode360.com | https://ecode360.com/GE0377 | n/a (a town has no charter) |
| Geneseo town | ecode360.com | https://ecode360.com/GE1141 | n/a (a town has no charter) |
| Geneseo village | ecode360.com | https://ecode360.com/GE0051 | not checked (Village Law; 12 charter villages unnamed) |
| Geneva city | ecode360.com | https://ecode360.com/GE1846 | yes |
| Geneva town | ecode360.com | https://ecode360.com/GE1637 | n/a (a town has no charter) |
| Ghent town | ecode360.com | https://ecode360.com/GH1743 | n/a (a town has no charter) |
| Glen Cove city | ecode360.com | https://ecode360.com/GL1564 | yes |
| Glens Falls city | ecode360.com | https://ecode360.com/GL0215 | yes |
| Glenville town | ecode360.com | https://ecode360.com/GL0172 | n/a (a town has no charter) |
| Gloversville city | ecode360.com | https://ecode360.com/GL0052 | yes |
| Goshen town | ecode360.com | https://ecode360.com/GO0551 | n/a (a town has no charter) |
| Goshen village | municode | https://library.municode.com/ny/goshen | not checked (Village Law; 12 charter villages unnamed) |
| Grafton town | ecode360.com | https://ecode360.com/GR1745 | n/a (a town has no charter) |
| Grand Island town | ecode360.com | https://ecode360.com/GR0053 | n/a (a town has no charter) |
| Great Neck Estates village | ecode360.com | https://ecode360.com/GR0716 | not checked (Village Law; 12 charter villages unnamed) |
| Great Neck Plaza village | ecode360.com | https://ecode360.com/GR1040 | not checked (Village Law; 12 charter villages unnamed) |
| Great Neck village | ecode360.com | https://ecode360.com/GR0590 | not checked (Village Law; 12 charter villages unnamed) |
| Greece town | ecode360.com | https://ecode360.com/GR0054 | n/a (a town has no charter) |
| Green Island village | ecode360.com | https://ecode360.com/GR1167 | not checked (Village Law; 12 charter villages unnamed) |
| Greenburgh town | ecode360.com | https://ecode360.com/GR0237 | n/a (a town has no charter) |
| Greene village | ecode360.com | https://ecode360.com/GR1302 | not checked (Village Law; 12 charter villages unnamed) |
| Greenfield town | ecode360.com | https://ecode360.com/GR1147 | n/a (a town has no charter) |
| Greenport town | ecode360.com | https://ecode360.com/GR0644 | n/a (a town has no charter) |
| Greenport village | ecode360.com | https://ecode360.com/GR0542 | not checked (Village Law; 12 charter villages unnamed) |
| Greenwich town | ecode360.com | https://ecode360.com/GR2077 | n/a (a town has no charter) |
| Greenwich town | municode | https://library.municode.com/ny/greenwich | n/a (a town has no charter) |
| Greenwood Lake village | ecode360.com | https://ecode360.com/GR0881 | not checked (Village Law; 12 charter villages unnamed) |
| Groton village | ecode360.com | https://ecode360.com/GR1261 | not checked (Village Law; 12 charter villages unnamed) |
| Guilderland town | ecode360.com | https://ecode360.com/GU1600 | n/a (a town has no charter) |
| Hague town | ecode360.com | https://ecode360.com/HA1590 | n/a (a town has no charter) |
| Halfmoon town | ecode360.com | https://ecode360.com/HA2075 | n/a (a town has no charter) |
| Hamburg town | ecode360.com | https://ecode360.com/HA0055 | n/a (a town has no charter) |
| Hamburg village | ecode360.com | https://ecode360.com/HA1542 | not checked (Village Law; 12 charter villages unnamed) |
| Hamilton village | ecode360.com | https://ecode360.com/HA1177 | not checked (Village Law; 12 charter villages unnamed) |
| Hamlin town | ecode360.com | https://ecode360.com/HA0223 | n/a (a town has no charter) |
| Hammondsport village | ecode360.com | https://ecode360.com/HA0982 | not checked (Village Law; 12 charter villages unnamed) |
| Hamptonburgh town | ecode360.com | https://ecode360.com/HA0701 | n/a (a town has no charter) |
| Hancock town | ecode360.com | https://ecode360.com/HA6727 | n/a (a town has no charter) |
| Hancock village | ecode360.com | https://ecode360.com/HA0277 | not checked (Village Law; 12 charter villages unnamed) |
| Harriman village | ecode360.com | https://ecode360.com/HA1129 | not checked (Village Law; 12 charter villages unnamed) |
| Hartford town | ecode360.com | https://ecode360.com/HA3152 | n/a (a town has no charter) |
| Hartland town | ecode360.com | https://ecode360.com/HA0923 | n/a (a town has no charter) |
| Hastings-on-Hudson village | ecode360.com | https://ecode360.com/HA0290 | not checked (Village Law; 12 charter villages unnamed) |
| Haverstraw town | ecode360.com | https://ecode360.com/HA0214 | n/a (a town has no charter) |
| Haverstraw village | ecode360.com | https://ecode360.com/HA0171 | not checked (Village Law; 12 charter villages unnamed) |
| Hempstead town | ecode360.com | https://ecode360.com/HE0207 | n/a (a town has no charter) |
| Hempstead village | ecode360.com | https://ecode360.com/HE0909 | not checked (Village Law; 12 charter villages unnamed) |
| Henrietta town | ecode360.com | https://ecode360.com/HE0056 | n/a (a town has no charter) |
| Hewlett Bay Park village | ecode360.com | https://ecode360.com/HE1222 | not checked (Village Law; 12 charter villages unnamed) |
| Hewlett Harbor village | ecode360.com | https://ecode360.com/HE0942 | not checked (Village Law; 12 charter villages unnamed) |
| Hewlett Neck village | ecode360.com | https://ecode360.com/HE1652 | not checked (Village Law; 12 charter villages unnamed) |
| Highland Falls village | ecode360.com | https://ecode360.com/HI0369 | not checked (Village Law; 12 charter villages unnamed) |
| Highland town | ecode360.com | https://ecode360.com/HI2985 | n/a (a town has no charter) |
| Highlands town | ecode360.com | https://ecode360.com/HI1566 | n/a (a town has no charter) |
| Hillburn village | ecode360.com | https://ecode360.com/HI0336 | not checked (Village Law; 12 charter villages unnamed) |
| Hillsdale town | ecode360.com | https://ecode360.com/HI4009 | n/a (a town has no charter) |
| Hilton village | ecode360.com | https://ecode360.com/HI0057 | not checked (Village Law; 12 charter villages unnamed) |
| Holland town | ecode360.com | https://ecode360.com/HO1067 | n/a (a town has no charter) |
| Holley village | ecode360.com | https://ecode360.com/HO1513 | not checked (Village Law; 12 charter villages unnamed) |
| Homer village | ecode360.com | https://ecode360.com/HO1264 | not checked (Village Law; 12 charter villages unnamed) |
| Honeoye Falls village | ecode360.com | https://ecode360.com/HO0058 | not checked (Village Law; 12 charter villages unnamed) |
| Hoosick Falls village | ecode360.com | https://ecode360.com/HO3619 | not checked (Village Law; 12 charter villages unnamed) |
| Hoosick town | ecode360.com | https://ecode360.com/HO4174 | n/a (a town has no charter) |
| Hornell city | ecode360.com | https://ecode360.com/HO1346 | yes |
| Horseheads town | ecode360.com | https://ecode360.com/HO1494 | n/a (a town has no charter) |
| Horseheads village | ecode360.com | https://ecode360.com/HO0600 | not checked (Village Law; 12 charter villages unnamed) |
| Hudson Falls village | ecode360.com | https://ecode360.com/HU0194 | not checked (Village Law; 12 charter villages unnamed) |
| Hudson city | ecode360.com | https://ecode360.com/HU0410 | yes |
| Huntington Bay village | ecode360.com | https://ecode360.com/HU0601 | not checked (Village Law; 12 charter villages unnamed) |
| Huntington town | ecode360.com | https://ecode360.com/HU0566 | n/a (a town has no charter) |
| Hurley town | ecode360.com | https://ecode360.com/HU1421 | n/a (a town has no charter) |
| Hyde Park town | ecode360.com | https://ecode360.com/HY0660 | n/a (a town has no charter) |
| Inlet town | ecode360.com | https://ecode360.com/IN2254 | n/a (a town has no charter) |
| Interlaken village | ecode360.com | https://ecode360.com/IN1614 | not checked (Village Law; 12 charter villages unnamed) |
| Irondequoit town | ecode360.com | https://ecode360.com/IR0059 | n/a (a town has no charter) |
| Irvington village | ecode360.com | https://ecode360.com/IR0187 | not checked (Village Law; 12 charter villages unnamed) |
| Island Park village | ecode360.com | https://ecode360.com/IS1102 | not checked (Village Law; 12 charter villages unnamed) |
| Islandia village | ecode360.com | https://ecode360.com/IS1122 | not checked (Village Law; 12 charter villages unnamed) |
| Islip town | ecode360.com | https://ecode360.com/IS0324 | n/a (a town has no charter) |
| Italy town | ecode360.com | https://ecode360.com/IT2877 | n/a (a town has no charter) |
| Ithaca city | ecode360.com | https://ecode360.com/IT1348 | yes |
| Ithaca town | ecode360.com | https://ecode360.com/IT1944 | n/a (a town has no charter) |
| Jamestown city | ecode360.com | https://ecode360.com/JA1371 | yes |
| Jerusalem town | ecode360.com | https://ecode360.com/JE1224 | n/a (a town has no charter) |
| Johnson City village | ecode360.com | https://ecode360.com/JO1382 | not checked (Village Law; 12 charter villages unnamed) |
| Johnstown city | ecode360.com | https://ecode360.com/JO1910 | yes |
| Johnstown town | ecode360.com | https://ecode360.com/JO0834 | n/a (a town has no charter) |
| Kendall town | ecode360.com | https://ecode360.com/KE2973 | n/a (a town has no charter) |
| Kenmore village | municode | https://library.municode.com/ny/kenmore | not checked (Village Law; 12 charter villages unnamed) |
| Kensington village | ecode360.com | https://ecode360.com/KE1161 | not checked (Village Law; 12 charter villages unnamed) |
| Kent town | ecode360.com | https://ecode360.com/KE0418 | n/a (a town has no charter) |
| Kinderhook town | ecode360.com | https://ecode360.com/KI0583 | n/a (a town has no charter) |
| Kinderhook village | ecode360.com | https://ecode360.com/KI0572 | not checked (Village Law; 12 charter villages unnamed) |
| Kings Point village | ecode360.com | https://ecode360.com/KI0771 | not checked (Village Law; 12 charter villages unnamed) |
| Kingsbury town | ecode360.com | https://ecode360.com/KI0871 | n/a (a town has no charter) |
| Kingston city | ecode360.com | https://ecode360.com/KI0280 | yes |
| Kingston town | ecode360.com | https://ecode360.com/KI2847 | n/a (a town has no charter) |
| Kiryas Joel village | ecode360.com | https://ecode360.com/KI1464 | not checked (Village Law; 12 charter villages unnamed) |
| LaFayette town | ecode360.com | https://ecode360.com/LA3588 | n/a (a town has no charter) |
| LaGrange town | ecode360.com | https://ecode360.com/LA0563 | n/a (a town has no charter) |
| Lackawanna city | ecode360.com | https://ecode360.com/LA1978 | yes |
| Lake George town | ecode360.com | https://ecode360.com/LA1393 | n/a (a town has no charter) |
| Lake George village | ecode360.com | https://ecode360.com/LA0343 | not checked (Village Law; 12 charter villages unnamed) |
| Lake Grove village | ecode360.com | https://ecode360.com/LA0625 | not checked (Village Law; 12 charter villages unnamed) |
| Lake Placid village | ecode360.com | https://ecode360.com/LA2988 | not checked (Village Law; 12 charter villages unnamed) |
| Lake Success village | ecode360.com | https://ecode360.com/LA0844 | not checked (Village Law; 12 charter villages unnamed) |
| Lancaster town | ecode360.com | https://ecode360.com/LA0177 | n/a (a town has no charter) |
| Lancaster village | ecode360.com | https://ecode360.com/LA0609 | not checked (Village Law; 12 charter villages unnamed) |
| Lansing town | ecode360.com | https://ecode360.com/LA2647 | n/a (a town has no charter) |
| Larchmont village | ecode360.com | https://ecode360.com/LA0851 | not checked (Village Law; 12 charter villages unnamed) |
| Lattingtown village | ecode360.com | https://ecode360.com/LA2687 | not checked (Village Law; 12 charter villages unnamed) |
| Laurel Hollow village | ecode360.com | https://ecode360.com/LA0693 | not checked (Village Law; 12 charter villages unnamed) |
| Lawrence village | ecode360.com | https://ecode360.com/LA1034 | not checked (Village Law; 12 charter villages unnamed) |
| Lenox town | ecode360.com | https://ecode360.com/LE0354 | n/a (a town has no charter) |
| Lewisboro town | ecode360.com | https://ecode360.com/LE1300 | n/a (a town has no charter) |
| Lewiston town | ecode360.com | https://ecode360.com/LE0061 | n/a (a town has no charter) |
| Lewiston village | municode | https://library.municode.com/ny/lewiston | not checked (Village Law; 12 charter villages unnamed) |
| Liberty town | ecode360.com | https://ecode360.com/LI0552 | n/a (a town has no charter) |
| Liberty village | ecode360.com | https://ecode360.com/LI0200 | not checked (Village Law; 12 charter villages unnamed) |
| Lima town | ecode360.com | https://ecode360.com/LI1605 | n/a (a town has no charter) |
| Lima village | ecode360.com | https://ecode360.com/LI0154 | not checked (Village Law; 12 charter villages unnamed) |
| Lindenhurst village | ecode360.com | https://ecode360.com/LI0062 | not checked (Village Law; 12 charter villages unnamed) |
| Little Valley town | ecode360.com | https://ecode360.com/LI3091 | n/a (a town has no charter) |
| Little Valley village | ecode360.com | https://ecode360.com/LI4138 | not checked (Village Law; 12 charter villages unnamed) |
| Liverpool village | ecode360.com | https://ecode360.com/LI1108 | not checked (Village Law; 12 charter villages unnamed) |
| Livonia town | ecode360.com | https://ecode360.com/LI0308 | n/a (a town has no charter) |
| Livonia village | ecode360.com | https://ecode360.com/LI1607 | not checked (Village Law; 12 charter villages unnamed) |
| Lloyd Harbor village | ecode360.com | https://ecode360.com/LL1341 | not checked (Village Law; 12 charter villages unnamed) |
| Lloyd town | ecode360.com | https://ecode360.com/LL0645 | n/a (a town has no charter) |
| Lockport city | ecode360.com | https://ecode360.com/LO0777 | yes |
| Lockport town | ecode360.com | https://ecode360.com/LO1992 | n/a (a town has no charter) |
| Lowville town | ecode360.com | https://ecode360.com/LO1448 | n/a (a town has no charter) |
| Lowville village | ecode360.com | https://ecode360.com/LO1526 | not checked (Village Law; 12 charter villages unnamed) |
| Lumberland town | ecode360.com | https://ecode360.com/LU3128 | n/a (a town has no charter) |
| Lynbrook village | ecode360.com | https://ecode360.com/LY0558 | not checked (Village Law; 12 charter villages unnamed) |
| Lyndonville village | municode | https://library.municode.com/ny/lyndonville | not checked (Village Law; 12 charter villages unnamed) |
| Lyons town | ecode360.com | https://ecode360.com/LY3853 | n/a (a town has no charter) |
| Lysander town | ecode360.com | https://ecode360.com/LY0932 | n/a (a town has no charter) |
| Macedon town | ecode360.com | https://ecode360.com/MA1436 | n/a (a town has no charter) |
| Maine town | ecode360.com | https://ecode360.com/MA2200 | n/a (a town has no charter) |
| Malone village | ecode360.com | https://ecode360.com/MA0063 | not checked (Village Law; 12 charter villages unnamed) |
| Malta town | ecode360.com | https://ecode360.com/MA1379 | n/a (a town has no charter) |
| Malverne village | ecode360.com | https://ecode360.com/MA0211 | not checked (Village Law; 12 charter villages unnamed) |
| Mamakating town | ecode360.com | https://ecode360.com/MA1270 | n/a (a town has no charter) |
| Mamaroneck town | ecode360.com | https://ecode360.com/MA0239 | n/a (a town has no charter) |
| Mamaroneck village | ecode360.com | https://ecode360.com/MA0954 | not checked (Village Law; 12 charter villages unnamed) |
| Manchester town | ecode360.com | https://ecode360.com/MA1025 | n/a (a town has no charter) |
| Manchester village | ecode360.com | https://ecode360.com/MA0793 | not checked (Village Law; 12 charter villages unnamed) |
| Manlius town | ecode360.com | https://ecode360.com/MA1592 | n/a (a town has no charter) |
| Manlius village | ecode360.com | https://ecode360.com/MA0818 | not checked (Village Law; 12 charter villages unnamed) |
| Manorhaven village | ecode360.com | https://ecode360.com/MA0580 | not checked (Village Law; 12 charter villages unnamed) |
| Marbletown town | ecode360.com | https://ecode360.com/MA1321 | n/a (a town has no charter) |
| Marcellus town | ecode360.com | https://ecode360.com/MA3903 | n/a (a town has no charter) |
| Marilla town | ecode360.com | https://ecode360.com/MA1758 | n/a (a town has no charter) |
| Marion town | ecode360.com | https://ecode360.com/MA3574 | n/a (a town has no charter) |
| Marlborough town | ecode360.com | https://ecode360.com/MA0587 | n/a (a town has no charter) |
| Martinsburg town | ecode360.com | https://ecode360.com/MA3054 | n/a (a town has no charter) |
| Massapequa Park village | ecode360.com | https://ecode360.com/MA0905 | not checked (Village Law; 12 charter villages unnamed) |
| Massena town | ecode360.com | https://ecode360.com/MA0639 | n/a (a town has no charter) |
| Massena village | ecode360.com | https://ecode360.com/MA0064 | not checked (Village Law; 12 charter villages unnamed) |
| Matinecock village | ecode360.com | https://ecode360.com/MA1760 | not checked (Village Law; 12 charter villages unnamed) |
| Maybrook village | ecode360.com | https://ecode360.com/MA1267 | not checked (Village Law; 12 charter villages unnamed) |
| McGraw village | ecode360.com | https://ecode360.com/MC1516 | not checked (Village Law; 12 charter villages unnamed) |
| Mechanicville city | ecode360.com | https://ecode360.com/ME0065 | yes |
| Medina village | ecode360.com | https://ecode360.com/ME0066 | not checked (Village Law; 12 charter villages unnamed) |
| Menands village | ecode360.com | https://ecode360.com/ME1106 | not checked (Village Law; 12 charter villages unnamed) |
| Mendon town | ecode360.com | https://ecode360.com/ME0067 | n/a (a town has no charter) |
| Middleport village | ecode360.com | https://ecode360.com/MI1694 | not checked (Village Law; 12 charter villages unnamed) |
| Middletown city | ecode360.com | https://ecode360.com/MI0232 | yes |
| Milan town | ecode360.com | https://ecode360.com/MI1453 | n/a (a town has no charter) |
| Mill Neck village | ecode360.com | https://ecode360.com/MI0853 | not checked (Village Law; 12 charter villages unnamed) |
| Millbrook village | ecode360.com | https://ecode360.com/MI1586 | not checked (Village Law; 12 charter villages unnamed) |
| Millerton village | ecode360.com | https://ecode360.com/MI0663 | not checked (Village Law; 12 charter villages unnamed) |
| Milo town | ecode360.com | https://ecode360.com/MI1633 | n/a (a town has no charter) |
| Milton town | ecode360.com | https://ecode360.com/MI1539 | n/a (a town has no charter) |
| Minden town | ecode360.com | https://ecode360.com/MI1862 | n/a (a town has no charter) |
| Mineola village | ecode360.com | https://ecode360.com/MI0069 | not checked (Village Law; 12 charter villages unnamed) |
| Minoa village | ecode360.com | https://ecode360.com/MI1181 | not checked (Village Law; 12 charter villages unnamed) |
| Monroe County | ecode360.com | https://ecode360.com/MO0860 | not checked |
| Monroe town | ecode360.com | https://ecode360.com/MO0402 | n/a (a town has no charter) |
| Monroe village | ecode360.com | https://ecode360.com/MO0222 | not checked (Village Law; 12 charter villages unnamed) |
| Montebello village | ecode360.com | https://ecode360.com/MO1927 | not checked (Village Law; 12 charter villages unnamed) |
| Montgomery town | ecode360.com | https://ecode360.com/MO0967 | n/a (a town has no charter) |
| Montgomery village | ecode360.com | https://ecode360.com/MO0887 | not checked (Village Law; 12 charter villages unnamed) |
| Monticello village | ecode360.com | https://ecode360.com/MO0528 | not checked (Village Law; 12 charter villages unnamed) |
| Montour Falls village | ecode360.com | https://ecode360.com/MO1461 | not checked (Village Law; 12 charter villages unnamed) |
| Montour town | ecode360.com | https://ecode360.com/MO3644 | n/a (a town has no charter) |
| Moreau town | ecode360.com | https://ecode360.com/MO0071 | n/a (a town has no charter) |
| Morrisville village | ecode360.com | https://ecode360.com/MO1477 | not checked (Village Law; 12 charter villages unnamed) |
| Mount Hope town | ecode360.com | https://ecode360.com/MO3540 | n/a (a town has no charter) |
| Mount Morris town | ecode360.com | https://ecode360.com/MO1094 | n/a (a town has no charter) |
| Mount Morris village | ecode360.com | https://ecode360.com/MO0072 | not checked (Village Law; 12 charter villages unnamed) |
| Mount Pleasant town | ecode360.com | https://ecode360.com/MO0299 | n/a (a town has no charter) |
| Mount Vernon city | ecode360.com | https://ecode360.com/MO0742 | yes |
| Munsey Park village | ecode360.com | https://ecode360.com/MU1617 | not checked (Village Law; 12 charter villages unnamed) |
| Murray town | ecode360.com | https://ecode360.com/MU6823 | n/a (a town has no charter) |
| Muttontown village | ecode360.com | https://ecode360.com/MU1779 | not checked (Village Law; 12 charter villages unnamed) |
| Naples town | ecode360.com | https://ecode360.com/NA1863 | n/a (a town has no charter) |
| Naples village | ecode360.com | https://ecode360.com/NA2763 | not checked (Village Law; 12 charter villages unnamed) |
| Nassau village | ecode360.com | https://ecode360.com/NA1113 | not checked (Village Law; 12 charter villages unnamed) |
| Neversink town | ecode360.com | https://ecode360.com/NE0768 | n/a (a town has no charter) |
| New Berlin town | ecode360.com | https://ecode360.com/NE1483 | n/a (a town has no charter) |
| New Castle town | ecode360.com | https://ecode360.com/NE0395 | n/a (a town has no charter) |
| New Hartford town | ecode360.com | https://ecode360.com/NE0673 | n/a (a town has no charter) |
| New Hartford village | ecode360.com | https://ecode360.com/NE0320 | not checked (Village Law; 12 charter villages unnamed) |
| New Hempstead village | ecode360.com | https://ecode360.com/NE1212 | not checked (Village Law; 12 charter villages unnamed) |
| New Hyde Park village | ecode360.com | https://ecode360.com/NE1037 | not checked (Village Law; 12 charter villages unnamed) |
| New Lebanon town | ecode360.com | https://ecode360.com/NE1814 | n/a (a town has no charter) |
| New Paltz town | ecode360.com | https://ecode360.com/NE1058 | n/a (a town has no charter) |
| New Paltz village | ecode360.com | https://ecode360.com/NE0076 | not checked (Village Law; 12 charter villages unnamed) |
| New Rochelle city | ecode360.com | https://ecode360.com/NE0964 | yes |
| New Windsor town | ecode360.com | https://ecode360.com/NE0078 | n/a (a town has no charter) |
| New York Mills village | ecode360.com | https://ecode360.com/NE1938 | not checked (Village Law; 12 charter villages unnamed) |
| New York city | codelibrary.amlegal.com | https://codelibrary.amlegal.com/codes/newyorkcity/latest/overview | yes |
| Newark Valley village | ecode360.com | https://ecode360.com/NE1405 | not checked (Village Law; 12 charter villages unnamed) |
| Newark village | ecode360.com | https://ecode360.com/NE0073 | not checked (Village Law; 12 charter villages unnamed) |
| Newburgh city | ecode360.com | https://ecode360.com/NE1082 | yes |
| Newburgh town | ecode360.com | https://ecode360.com/NE0074 | n/a (a town has no charter) |
| Newfane town | ecode360.com | https://ecode360.com/NE0384 | n/a (a town has no charter) |
| Newstead town | ecode360.com | https://ecode360.com/NE1143 | n/a (a town has no charter) |
| Niagara town | ecode360.com | https://ecode360.com/NI0431 | n/a (a town has no charter) |
| Nichols town | ecode360.com | https://ecode360.com/NI2943 | n/a (a town has no charter) |
| Niles town | ecode360.com | https://ecode360.com/NI1781 | n/a (a town has no charter) |
| Niskayuna town | ecode360.com | https://ecode360.com/NI0974 | n/a (a town has no charter) |
| Nissequogue village | ecode360.com | https://ecode360.com/NI0891 | not checked (Village Law; 12 charter villages unnamed) |
| North Castle town | ecode360.com | https://ecode360.com/NO0492 | n/a (a town has no charter) |
| North Collins town | ecode360.com | https://ecode360.com/NO1305 | n/a (a town has no charter) |
| North Collins village | ecode360.com | https://ecode360.com/NO0080 | not checked (Village Law; 12 charter villages unnamed) |
| North East town | ecode360.com | https://ecode360.com/NO0666 | n/a (a town has no charter) |
| North Greenbush town | ecode360.com | https://ecode360.com/NO0677 | n/a (a town has no charter) |
| North Haven village | ecode360.com | https://ecode360.com/NO1009 | not checked (Village Law; 12 charter villages unnamed) |
| North Hempstead town | ecode360.com | https://ecode360.com/NO0081 | n/a (a town has no charter) |
| North Hills village | ecode360.com | https://ecode360.com/NO0839 | not checked (Village Law; 12 charter villages unnamed) |
| North Hornell village | ecode360.com | https://ecode360.com/NO0082 | not checked (Village Law; 12 charter villages unnamed) |
| North Salem town | ecode360.com | https://ecode360.com/NO1178 | n/a (a town has no charter) |
| North Syracuse village | ecode360.com | https://ecode360.com/NO1279 | not checked (Village Law; 12 charter villages unnamed) |
| North Tonawanda city | ecode360.com | https://ecode360.com/NO0216 | yes |
| Northport village | ecode360.com | https://ecode360.com/NO0083 | not checked (Village Law; 12 charter villages unnamed) |
| Norwich city | ecode360.com | https://ecode360.com/NO0235 | yes |
| Norwood village | ecode360.com | https://ecode360.com/NO1576 | not checked (Village Law; 12 charter villages unnamed) |
| Nyack village | ecode360.com | https://ecode360.com/NY0087 | not checked (Village Law; 12 charter villages unnamed) |
| Oakfield village | ecode360.com | https://ecode360.com/OA3797 | not checked (Village Law; 12 charter villages unnamed) |
| Ocean Beach village | ecode360.com | https://ecode360.com/OC0808 | not checked (Village Law; 12 charter villages unnamed) |
| Ogden town | ecode360.com | https://ecode360.com/OG0089 | n/a (a town has no charter) |
| Ogdensburg city | ecode360.com | https://ecode360.com/OG1342 | yes |
| Old Brookville village | ecode360.com | https://ecode360.com/OL1722 | not checked (Village Law; 12 charter villages unnamed) |
| Old Field village | ecode360.com | https://ecode360.com/OL0629 | not checked (Village Law; 12 charter villages unnamed) |
| Old Westbury village | ecode360.com | https://ecode360.com/OL0821 | not checked (Village Law; 12 charter villages unnamed) |
| Olean city | ecode360.com | https://ecode360.com/OL2074 | not checked (refused 429) |
| Olive town | ecode360.com | https://ecode360.com/OL1834 | n/a (a town has no charter) |
| Oneida city | ecode360.com | https://ecode360.com/ON1850 | yes |
| Oneonta city | ecode360.com | https://ecode360.com/ON1737 | yes |
| Oneonta town | ecode360.com | https://ecode360.com/ON0907 | n/a (a town has no charter) |
| Onondaga town | ecode360.com | https://ecode360.com/ON0090 | n/a (a town has no charter) |
| Ontario town | ecode360.com | https://ecode360.com/ON0420 | n/a (a town has no charter) |
| Orangetown town | ecode360.com | https://ecode360.com/OR0091 | n/a (a town has no charter) |
| Orchard Park town | ecode360.com | https://ecode360.com/OR0980 | n/a (a town has no charter) |
| Orchard Park village | ecode360.com | https://ecode360.com/OR2827 | not checked (Village Law; 12 charter villages unnamed) |
| Ossining town | ecode360.com | https://ecode360.com/OS0797 | n/a (a town has no charter) |
| Ossining village | ecode360.com | https://ecode360.com/OS1500 | not checked (Village Law; 12 charter villages unnamed) |
| Oswego city | ecode360.com | https://ecode360.com/OS0092 | yes |
| Otego village | ecode360.com | https://ecode360.com/OT2046 | not checked (Village Law; 12 charter villages unnamed) |
| Owasco town | ecode360.com | https://ecode360.com/OW0921 | n/a (a town has no charter) |
| Owego town | ecode360.com | https://ecode360.com/OW0781 | n/a (a town has no charter) |
| Owego village | ecode360.com | https://ecode360.com/OW1583 | not checked (Village Law; 12 charter villages unnamed) |
| Oxford village | ecode360.com | https://ecode360.com/OX1411 | not checked (Village Law; 12 charter villages unnamed) |
| Oyster Bay Cove village | ecode360.com | https://ecode360.com/OY1780 | not checked (Village Law; 12 charter villages unnamed) |
| Oyster Bay town | ecode360.com | https://ecode360.com/OY1221 | n/a (a town has no charter) |
| Palmyra village | ecode360.com | https://ecode360.com/PA0094 | not checked (Village Law; 12 charter villages unnamed) |
| Parma town | ecode360.com | https://ecode360.com/PA0391 | n/a (a town has no charter) |
| Patchogue village | ecode360.com | https://ecode360.com/PA0323 | not checked (Village Law; 12 charter villages unnamed) |
| Pawling town | ecode360.com | https://ecode360.com/PA0446 | n/a (a town has no charter) |
| Peekskill city | ecode360.com | https://ecode360.com/PE0161 | yes |
| Pelham Manor village | ecode360.com | https://ecode360.com/PE1838 | not checked (Village Law; 12 charter villages unnamed) |
| Pelham village | ecode360.com | https://ecode360.com/PE0553 | not checked (Village Law; 12 charter villages unnamed) |
| Pendleton town | ecode360.com | https://ecode360.com/PE1345 | n/a (a town has no charter) |
| Penfield town | ecode360.com | https://ecode360.com/PE0095 | n/a (a town has no charter) |
| Penn Yan village | ecode360.com | https://ecode360.com/PE0096 | not checked (Village Law; 12 charter villages unnamed) |
| Perinton town | ecode360.com | https://ecode360.com/PE0097 | n/a (a town has no charter) |
| Perry village | ecode360.com | https://ecode360.com/PE2218 | not checked (Village Law; 12 charter villages unnamed) |
| Phelps town | ecode360.com | https://ecode360.com/PH1430 | n/a (a town has no charter) |
| Phelps village | ecode360.com | https://ecode360.com/PH1306 | not checked (Village Law; 12 charter villages unnamed) |
| Philipstown town | ecode360.com | https://ecode360.com/PH1134 | n/a (a town has no charter) |
| Phoenix village | ecode360.com | https://ecode360.com/PH0099 | not checked (Village Law; 12 charter villages unnamed) |
| Piermont village | ecode360.com | https://ecode360.com/PI0612 | not checked (Village Law; 12 charter villages unnamed) |
| Pierrepont town | ecode360.com | https://ecode360.com/PI6589 | n/a (a town has no charter) |
| Pine Plains town | ecode360.com | https://ecode360.com/PI3655 | n/a (a town has no charter) |
| Pittsford town | ecode360.com | https://ecode360.com/PI1657 | n/a (a town has no charter) |
| Pittsford village | ecode360.com | https://ecode360.com/PI1146 | not checked (Village Law; 12 charter villages unnamed) |
| Plandome Heights village | ecode360.com | https://ecode360.com/PL1989 | not checked (Village Law; 12 charter villages unnamed) |
| Plandome Manor village | ecode360.com | https://ecode360.com/PL2903 | not checked (Village Law; 12 charter villages unnamed) |
| Plandome village | ecode360.com | https://ecode360.com/PL0883 | not checked (Village Law; 12 charter villages unnamed) |
| Plattekill town | ecode360.com | https://ecode360.com/PL1069 | n/a (a town has no charter) |
| Plattsburgh city | ecode360.com | https://ecode360.com/PL0920 | yes |
| Pleasant Valley town | ecode360.com | https://ecode360.com/PL0575 | n/a (a town has no charter) |
| Pleasantville village | ecode360.com | https://ecode360.com/PL1550 | not checked (Village Law; 12 charter villages unnamed) |
| Poestenkill town | ecode360.com | https://ecode360.com/PO0866 | n/a (a town has no charter) |
| Pomona village | ecode360.com | https://ecode360.com/PO1095 | not checked (Village Law; 12 charter villages unnamed) |
| Pompey town | ecode360.com | https://ecode360.com/PO1491 | n/a (a town has no charter) |
| Poquott village | ecode360.com | https://ecode360.com/PO2249 | not checked (Village Law; 12 charter villages unnamed) |
| Port Chester village | ecode360.com | https://ecode360.com/PO0100 | not checked (Village Law; 12 charter villages unnamed) |
| Port Jefferson village | ecode360.com | https://ecode360.com/PO0346 | not checked (Village Law; 12 charter villages unnamed) |
| Port Jervis city | ecode360.com | https://ecode360.com/PO0478 | yes |
| Port Washington North village | ecode360.com | https://ecode360.com/PO1921 | not checked (Village Law; 12 charter villages unnamed) |
| Porter town | ecode360.com | https://ecode360.com/PO2986 | n/a (a town has no charter) |
| Potsdam town | ecode360.com | https://ecode360.com/PO1013 | n/a (a town has no charter) |
| Potsdam village | ecode360.com | https://ecode360.com/PO0885 | not checked (Village Law; 12 charter villages unnamed) |
| Poughkeepsie city | ecode360.com | https://ecode360.com/PO1408 | yes |
| Poughkeepsie town | ecode360.com | https://ecode360.com/PO1462 | n/a (a town has no charter) |
| Pound Ridge town | ecode360.com | https://ecode360.com/PO0893 | n/a (a town has no charter) |
| Pulaski village | ecode360.com | https://ecode360.com/PU1979 | not checked (Village Law; 12 charter villages unnamed) |
| Putnam County | ecode360.com | https://ecode360.com/PU1531 | not checked |
| Putnam Valley town | ecode360.com | https://ecode360.com/PU0242 | n/a (a town has no charter) |
| Queensbury town | ecode360.com | https://ecode360.com/QU1252 | n/a (a town has no charter) |
| Quogue village | ecode360.com | https://ecode360.com/QU1026 | not checked (Village Law; 12 charter villages unnamed) |
| Ramapo town | ecode360.com | https://ecode360.com/RA0101 | n/a (a town has no charter) |
| Ravena village | ecode360.com | https://ecode360.com/RA1187 | not checked (Village Law; 12 charter villages unnamed) |
| Red Creek village | ecode360.com | https://ecode360.com/RE3617 | not checked (Village Law; 12 charter villages unnamed) |
| Red Hook town | ecode360.com | https://ecode360.com/RE0424 | n/a (a town has no charter) |
| Red Hook village | ecode360.com | https://ecode360.com/RE1449 | not checked (Village Law; 12 charter villages unnamed) |
| Rensselaer city | ecode360.com | https://ecode360.com/RE1014 | yes |
| Rhinebeck town | ecode360.com | https://ecode360.com/RH0960 | n/a (a town has no charter) |
| Rhinebeck village | ecode360.com | https://ecode360.com/RH1002 | not checked (Village Law; 12 charter villages unnamed) |
| Richmond town | ecode360.com | https://ecode360.com/RI1771 | n/a (a town has no charter) |
| Riga town | ecode360.com | https://ecode360.com/RI0725 | n/a (a town has no charter) |
| Riverhead town | ecode360.com | https://ecode360.com/RI0508 | n/a (a town has no charter) |
| Rochester city | ecode360.com | https://ecode360.com/RO0104 | yes |
| Rochester town | ecode360.com | https://ecode360.com/RO1435 | n/a (a town has no charter) |
| Rockland County | ecode360.com | https://ecode360.com/RO1021 | not checked |
| Rockland town | ecode360.com | https://ecode360.com/RO1679 | n/a (a town has no charter) |
| Rockville Centre village | ecode360.com | https://ecode360.com/RO0303 | not checked (Village Law; 12 charter villages unnamed) |
| Rome city | municode | https://library.municode.com/ny/rome | not checked (Municode refuses agents) |
| Rosendale town | ecode360.com | https://ecode360.com/RO0511 | n/a (a town has no charter) |
| Roslyn Estates village | ecode360.com | https://ecode360.com/RO1775 | not checked (Village Law; 12 charter villages unnamed) |
| Roslyn Harbor village | ecode360.com | https://ecode360.com/RO0789 | not checked (Village Law; 12 charter villages unnamed) |
| Roslyn village | ecode360.com | https://ecode360.com/RO1402 | not checked (Village Law; 12 charter villages unnamed) |
| Rotterdam town | ecode360.com | https://ecode360.com/RO0175 | n/a (a town has no charter) |
| Round Lake village | ecode360.com | https://ecode360.com/RO1591 | not checked (Village Law; 12 charter villages unnamed) |
| Rouses Point village | ecode360.com | https://ecode360.com/RO0588 | not checked (Village Law; 12 charter villages unnamed) |
| Royalton town | ecode360.com | https://ecode360.com/RO3169 | n/a (a town has no charter) |
| Rush town | ecode360.com | https://ecode360.com/RU0105 | n/a (a town has no charter) |
| Russell Gardens village | ecode360.com | https://ecode360.com/RU0545 | not checked (Village Law; 12 charter villages unnamed) |
| Rye Brook village | ecode360.com | https://ecode360.com/RY1192 | not checked (Village Law; 12 charter villages unnamed) |
| Rye city | ecode360.com | https://ecode360.com/RY0730 | yes |
| Rye town | ecode360.com | https://ecode360.com/RY0107 | n/a (a town has no charter) |
| Saddle Rock village | ecode360.com | https://ecode360.com/SA0943 | not checked (Village Law; 12 charter villages unnamed) |
| Sag Harbor village | ecode360.com | https://ecode360.com/SA0314 | not checked (Village Law; 12 charter villages unnamed) |
| Sagaponack village | ecode360.com | https://ecode360.com/SA2797 | not checked (Village Law; 12 charter villages unnamed) |
| Salamanca city | ecode360.com | https://ecode360.com/SA1603 | yes |
| Salina town | ecode360.com | https://ecode360.com/SA0325 | n/a (a town has no charter) |
| Sand Lake town | ecode360.com | https://ecode360.com/SA1559 | n/a (a town has no charter) |
| Sands Point village | ecode360.com | https://ecode360.com/SA0704 | not checked (Village Law; 12 charter villages unnamed) |
| Saranac Lake village | ecode360.com | https://ecode360.com/SA0109 | not checked (Village Law; 12 charter villages unnamed) |
| Saratoga County | ecode360.com | https://ecode360.com/SA2068 | not checked |
| Saratoga Springs city | ecode360.com | https://ecode360.com/SA0110 | yes |
| Saratoga town | ecode360.com | https://ecode360.com/SA2195 | n/a (a town has no charter) |
| Sardinia town | ecode360.com | https://ecode360.com/SA1170 | n/a (a town has no charter) |
| Saugerties town | ecode360.com | https://ecode360.com/SA2874 | n/a (a town has no charter) |
| Saugerties village | ecode360.com | https://ecode360.com/SA0824 | not checked (Village Law; 12 charter villages unnamed) |
| Scarsdale village | ecode360.com | https://ecode360.com/SC0993 | not checked (Village Law; 12 charter villages unnamed) |
| Schaghticoke town | ecode360.com | https://ecode360.com/SC1145 | n/a (a town has no charter) |
| Schenectady city | ecode360.com | https://ecode360.com/SC0901 | yes |
| Schodack town | ecode360.com | https://ecode360.com/SC1190 | n/a (a town has no charter) |
| Schroeppel town | ecode360.com | https://ecode360.com/SC0491 | n/a (a town has no charter) |
| Scotia village | ecode360.com | https://ecode360.com/SC1344 | not checked (Village Law; 12 charter villages unnamed) |
| Scottsville village | ecode360.com | https://ecode360.com/SC1216 | not checked (Village Law; 12 charter villages unnamed) |
| Sea Cliff village | ecode360.com | https://ecode360.com/SE0543 | not checked (Village Law; 12 charter villages unnamed) |
| Seneca Falls town | ecode360.com | https://ecode360.com/SE1298 | n/a (a town has no charter) |
| Shandaken town | ecode360.com | https://ecode360.com/SH1022 | n/a (a town has no charter) |
| Shelter Island town | ecode360.com | https://ecode360.com/SH0746 | n/a (a town has no charter) |
| Shortsville village | ecode360.com | https://ecode360.com/SH0676 | not checked (Village Law; 12 charter villages unnamed) |
| Sidney village | ecode360.com | https://ecode360.com/SI0279 | not checked (Village Law; 12 charter villages unnamed) |
| Skaneateles town | ecode360.com | https://ecode360.com/SK0895 | n/a (a town has no charter) |
| Skaneateles village | ecode360.com | https://ecode360.com/SK1975 | not checked (Village Law; 12 charter villages unnamed) |
| Sleepy Hollow village | ecode360.com | https://ecode360.com/SL0084 | not checked (Village Law; 12 charter villages unnamed) |
| Sloan village | ecode360.com | https://ecode360.com/SL0113 | not checked (Village Law; 12 charter villages unnamed) |
| Sloatsburg village | ecode360.com | https://ecode360.com/SL0114 | not checked (Village Law; 12 charter villages unnamed) |
| Smithtown town | ecode360.com | https://ecode360.com/SM0115 | n/a (a town has no charter) |
| Sodus town | ecode360.com | https://ecode360.com/SO0501 | n/a (a town has no charter) |
| Solvay village | ecode360.com | https://ecode360.com/SO1086 | not checked (Village Law; 12 charter villages unnamed) |
| Somers town | ecode360.com | https://ecode360.com/SO0406 | n/a (a town has no charter) |
| Somerset town | ecode360.com | https://ecode360.com/SO1409 | n/a (a town has no charter) |
| South Bristol town | ecode360.com | https://ecode360.com/SO1384 | n/a (a town has no charter) |
| South Floral Park village | ecode360.com | https://ecode360.com/SO0984 | not checked (Village Law; 12 charter villages unnamed) |
| South Glens Falls village | ecode360.com | https://ecode360.com/SO0117 | not checked (Village Law; 12 charter villages unnamed) |
| Southampton town | ecode360.com | https://ecode360.com/SO0286 | n/a (a town has no charter) |
| Southampton village | ecode360.com | https://ecode360.com/SO0841 | not checked (Village Law; 12 charter villages unnamed) |
| Southeast town | ecode360.com | https://ecode360.com/SO1053 | n/a (a town has no charter) |
| Southold town | ecode360.com | https://ecode360.com/SO0452 | n/a (a town has no charter) |
| Southport town | ecode360.com | https://ecode360.com/SO2246 | n/a (a town has no charter) |
| Spafford town | ecode360.com | https://ecode360.com/SP6729 | n/a (a town has no charter) |
| Speculator village | ecode360.com | https://ecode360.com/SP6573 | not checked (Village Law; 12 charter villages unnamed) |
| Spencer town | ecode360.com | https://ecode360.com/SP1416 | n/a (a town has no charter) |
| Spencerport village | ecode360.com | https://ecode360.com/SP0233 | not checked (Village Law; 12 charter villages unnamed) |
| Spring Valley village | ecode360.com | https://ecode360.com/SP1480 | not checked (Village Law; 12 charter villages unnamed) |
| Springville village | ecode360.com | https://ecode360.com/SP0643 | not checked (Village Law; 12 charter villages unnamed) |
| Stafford town | ecode360.com | https://ecode360.com/ST2888 | n/a (a town has no charter) |
| Stanford town | ecode360.com | https://ecode360.com/ST0938 | n/a (a town has no charter) |
| Steuben town | ecode360.com | https://ecode360.com/ST1913 | n/a (a town has no charter) |
| Stewart Manor village | ecode360.com | https://ecode360.com/ST1174 | not checked (Village Law; 12 charter villages unnamed) |
| Stillwater town | ecode360.com | https://ecode360.com/ST2761 | n/a (a town has no charter) |
| Stockport town | ecode360.com | https://ecode360.com/ST1577 | n/a (a town has no charter) |
| Stony Point town | ecode360.com | https://ecode360.com/ST0120 | n/a (a town has no charter) |
| Suffern village | ecode360.com | https://ecode360.com/SU0121 | not checked (Village Law; 12 charter villages unnamed) |
| Suffolk County | ecode360.com | https://ecode360.com/SU0867 | not checked |
| Sullivan County | ecode360.com | https://ecode360.com/SU1732 | not checked |
| Sullivan town | ecode360.com | https://ecode360.com/SU2838 | n/a (a town has no charter) |
| Sweden town | ecode360.com | https://ecode360.com/SW0122 | n/a (a town has no charter) |
| Sylvan Beach village | ecode360.com | https://ecode360.com/SY1091 | not checked (Village Law; 12 charter villages unnamed) |
| Syracuse city | municode | https://library.municode.com/ny/syracuse | not checked (Municode refuses agents) |
| Taghkanic town | ecode360.com | https://ecode360.com/TA2981 | n/a (a town has no charter) |
| Tarrytown village | ecode360.com | https://ecode360.com/TA1273 | not checked (Village Law; 12 charter villages unnamed) |
| Thomaston village | ecode360.com | https://ecode360.com/TH0685 | not checked (Village Law; 12 charter villages unnamed) |
| Thompson town | ecode360.com | https://ecode360.com/TH0750 | n/a (a town has no charter) |
| Tivoli village | ecode360.com | https://ecode360.com/TI1599 | not checked (Village Law; 12 charter villages unnamed) |
| Tompkins County | ecode360.com | https://ecode360.com/TO1768 | not checked |
| Tonawanda city | municode | https://library.municode.com/ny/tonawanda | not checked (Municode refuses agents) |
| Tonawanda town | ecode360.com | https://ecode360.com/TO0123 | n/a (a town has no charter) |
| Trenton town | ecode360.com | https://ecode360.com/TR1112 | n/a (a town has no charter) |
| Troy city | ecode360.com | https://ecode360.com/TR1767 | yes |
| Tuckahoe village | ecode360.com | https://ecode360.com/TU1441 | not checked (Village Law; 12 charter villages unnamed) |
| Tully town | ecode360.com | https://ecode360.com/TU2238 | n/a (a town has no charter) |
| Tusten town | ecode360.com | https://ecode360.com/TU3790 | n/a (a town has no charter) |
| Tuxedo Park village | ecode360.com | https://ecode360.com/TU0190 | not checked (Village Law; 12 charter villages unnamed) |
| Tuxedo town | ecode360.com | https://ecode360.com/TU0460 | n/a (a town has no charter) |
| Ulster County | ecode360.com | https://ecode360.com/UL2774 | not checked |
| Ulysses town | ecode360.com | https://ecode360.com/UL3512 | n/a (a town has no charter) |
| Unadilla village | ecode360.com | https://ecode360.com/UN1008 | not checked (Village Law; 12 charter villages unnamed) |
| Union Vale town | ecode360.com | https://ecode360.com/UN0671 | n/a (a town has no charter) |
| Union town | ecode360.com | https://ecode360.com/UN0126 | n/a (a town has no charter) |
| Upper Brookville village | ecode360.com | https://ecode360.com/UP1750 | not checked (Village Law; 12 charter villages unnamed) |
| Upper Nyack village | municode | https://library.municode.com/ny/upper_nyack | not checked (Village Law; 12 charter villages unnamed) |
| Urbana town | ecode360.com | https://ecode360.com/UR1262 | n/a (a town has no charter) |
| Utica city | ecode360.com | https://ecode360.com/UT2994 | yes |
| Valatie village | ecode360.com | https://ecode360.com/VA0616 | not checked (Village Law; 12 charter villages unnamed) |
| Valley Stream village | ecode360.com | https://ecode360.com/VA0219 | not checked (Village Law; 12 charter villages unnamed) |
| Van Buren town | ecode360.com | https://ecode360.com/VA1619 | n/a (a town has no charter) |
| Vernon town | ecode360.com | https://ecode360.com/VE1144 | n/a (a town has no charter) |
| Vernon village | ecode360.com | https://ecode360.com/VE1336 | not checked (Village Law; 12 charter villages unnamed) |
| Verona town | ecode360.com | https://ecode360.com/VE1663 | n/a (a town has no charter) |
| Vestal town | municode | https://library.municode.com/ny/vestal | n/a (a town has no charter) |
| Victor town | ecode360.com | https://ecode360.com/VI0236 | n/a (a town has no charter) |
| Victor village | ecode360.com | https://ecode360.com/VI0198 | not checked (Village Law; 12 charter villages unnamed) |
| Voorheesville village | ecode360.com | https://ecode360.com/VO2823 | not checked (Village Law; 12 charter villages unnamed) |
| Walden village | ecode360.com | https://ecode360.com/WA0823 | not checked (Village Law; 12 charter villages unnamed) |
| Wales town | ecode360.com | https://ecode360.com/WA1347 | n/a (a town has no charter) |
| Wallkill town | ecode360.com | https://ecode360.com/WA0513 | n/a (a town has no charter) |
| Walton town | ecode360.com | https://ecode360.com/WA3836 | n/a (a town has no charter) |
| Walton village | ecode360.com | https://ecode360.com/WA0231 | not checked (Village Law; 12 charter villages unnamed) |
| Walworth town | ecode360.com | https://ecode360.com/WA1363 | n/a (a town has no charter) |
| Wampsville village | ecode360.com | https://ecode360.com/WA6838 | not checked (Village Law; 12 charter villages unnamed) |
| Wappinger town | ecode360.com | https://ecode360.com/WA0691 | n/a (a town has no charter) |
| Wappingers Falls village | ecode360.com | https://ecode360.com/WA0129 | not checked (Village Law; 12 charter villages unnamed) |
| Warrensburg town | ecode360.com | https://ecode360.com/WA1545 | n/a (a town has no charter) |
| Warsaw village | ecode360.com | https://ecode360.com/WA0130 | not checked (Village Law; 12 charter villages unnamed) |
| Warwick town | ecode360.com | https://ecode360.com/WA1027 | n/a (a town has no charter) |
| Warwick village | ecode360.com | https://ecode360.com/WA0539 | not checked (Village Law; 12 charter villages unnamed) |
| Washington town | ecode360.com | https://ecode360.com/WA4180 | n/a (a town has no charter) |
| Washingtonville village | ecode360.com | https://ecode360.com/WA1295 | not checked (Village Law; 12 charter villages unnamed) |
| Waterford town | ecode360.com | https://ecode360.com/WA0791 | n/a (a town has no charter) |
| Waterford village | ecode360.com | https://ecode360.com/WA1892 | not checked (Village Law; 12 charter villages unnamed) |
| Waterloo village | ecode360.com | https://ecode360.com/WA0131 | not checked (Village Law; 12 charter villages unnamed) |
| Watertown city | ecode360.com | https://ecode360.com/WA0959 | yes |
| Watervliet city | ecode360.com | https://ecode360.com/WA1568 | yes |
| Waverly village | ecode360.com | https://ecode360.com/WA0132 | not checked (Village Law; 12 charter villages unnamed) |
| Wawarsing town | ecode360.com | https://ecode360.com/WA0802 | n/a (a town has no charter) |
| Wawayanda town | ecode360.com | https://ecode360.com/WA1265 | n/a (a town has no charter) |
| Webb town | ecode360.com | https://ecode360.com/WE2196 | n/a (a town has no charter) |
| Webster town | ecode360.com | https://ecode360.com/WE0220 | n/a (a town has no charter) |
| Webster village | ecode360.com | https://ecode360.com/WE0133 | not checked (Village Law; 12 charter villages unnamed) |
| Weedsport village | ecode360.com | https://ecode360.com/WE0134 | not checked (Village Law; 12 charter villages unnamed) |
| Wesley Hills village | ecode360.com | https://ecode360.com/WE3180 | not checked (Village Law; 12 charter villages unnamed) |
| West Bloomfield town | ecode360.com | https://ecode360.com/WE1705 | n/a (a town has no charter) |
| West Carthage village | ecode360.com | https://ecode360.com/WE0468 | not checked (Village Law; 12 charter villages unnamed) |
| West Hampton Dunes village | ecode360.com | https://ecode360.com/WE2990 | not checked (Village Law; 12 charter villages unnamed) |
| West Haverstraw village | ecode360.com | https://ecode360.com/WE1502 | not checked (Village Law; 12 charter villages unnamed) |
| West Seneca town | ecode360.com | https://ecode360.com/WE0417 | n/a (a town has no charter) |
| Westbury village | ecode360.com | https://ecode360.com/WE0136 | not checked (Village Law; 12 charter villages unnamed) |
| Westfield town | ecode360.com | https://ecode360.com/WE1631 | n/a (a town has no charter) |
| Westfield village | ecode360.com | https://ecode360.com/WE0661 | not checked (Village Law; 12 charter villages unnamed) |
| Westhampton Beach village | ecode360.com | https://ecode360.com/WE0779 | not checked (Village Law; 12 charter villages unnamed) |
| Wheatfield town | ecode360.com | https://ecode360.com/WH1495 | n/a (a town has no charter) |
| Wheatland town | ecode360.com | https://ecode360.com/WH0137 | n/a (a town has no charter) |
| White Plains city | municode | https://library.municode.com/ny/white_plains | not checked (Municode refuses agents) |
| Whitesboro village | ecode360.com | https://ecode360.com/WH0138 | not checked (Village Law; 12 charter villages unnamed) |
| Williamson town | ecode360.com | https://ecode360.com/WI0139 | n/a (a town has no charter) |
| Williamsville village | ecode360.com | https://ecode360.com/WI1015 | not checked (Village Law; 12 charter villages unnamed) |
| Williston Park village | ecode360.com | https://ecode360.com/WI1739 | not checked (Village Law; 12 charter villages unnamed) |
| Wilna town | ecode360.com | https://ecode360.com/WI3852 | n/a (a town has no charter) |
| Wilson town | ecode360.com | https://ecode360.com/WI0515 | n/a (a town has no charter) |
| Wilson village | ecode360.com | https://ecode360.com/WI0328 | not checked (Village Law; 12 charter villages unnamed) |
| Wilton town | ecode360.com | https://ecode360.com/WI1322 | n/a (a town has no charter) |
| Wolcott village | ecode360.com | https://ecode360.com/WO0142 | not checked (Village Law; 12 charter villages unnamed) |
| Woodbury town | ecode360.com | https://ecode360.com/WO0595 | n/a (a town has no charter) |
| Woodbury village | ecode360.com | https://ecode360.com/WO2925 | not checked (Village Law; 12 charter villages unnamed) |
| Woodridge village | ecode360.com | https://ecode360.com/WO1303 | not checked (Village Law; 12 charter villages unnamed) |
| Woodsburgh village | ecode360.com | https://ecode360.com/WO1199 | not checked (Village Law; 12 charter villages unnamed) |
| Woodstock town | ecode360.com | https://ecode360.com/WO2784 | n/a (a town has no charter) |
| Yates town | ecode360.com | https://ecode360.com/YA6634 | n/a (a town has no charter) |
| Yonkers city | ecode360.com | https://ecode360.com/YO0144 | yes |
| Yorktown town | ecode360.com | https://ecode360.com/YO1560 | n/a (a town has no charter) |
| Yorkville village | ecode360.com | https://ecode360.com/YO1205 | not checked (Village Law; 12 charter villages unnamed) |

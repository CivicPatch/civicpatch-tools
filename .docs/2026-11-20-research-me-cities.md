# Maine: cities

Step 2 of the `state-offices` skill. Layers: [2026-11-20-research-me-layers.md](2026-11-20-research-me-layers.md).
MMA: Maine Municipal Association,
[Local Government in Maine](https://www.memun.org/Documents?Command=Core_Download&EntryId=577), Aug. 1, 2016,
chapters 3 and 4.

## Every city has a charter

MMA: "All cities in Maine have local charters that provide for a representative form of government – meaning they
have a city council that serves as the legislative body." No Title 30-A section sets up a city's offices; the city
council is the legislative body by definition ([§ 2001(9)(B)](https://legislature.maine.gov/statutes/30-A/title30-Asec2001.html))
and "The mayor and aldermen or councillors of a city" are its municipal officers
([§ 2001(10)(B)](https://legislature.maine.gov/statutes/30-A/title30-Asec2001.html)). Where a charter is silent, the
general law fills it ([layers](2026-11-20-research-me-layers.md)).

## Forms and how many cities use each

MMA, 2016: "By 2016, 20 Maine cities and 24 towns had adopted the Council-Manager form", and "All of these cities
also employ city managers or administrators". The rest are mayor-council in some degree:

- **Westbrook**: "only the City of Westbrook has a 'strong mayor' in the classic sense"; administrative authority
  "granted entirely to the mayor by charter".
- **Lewiston**: "Mayor-Council-City Administrator" since 1980; the administrator, not the mayor, supervises
  departments.
- **Portland**: since 2010 the mayor is "elected to a four-year term by the voters at large"; "the manager oversees
  operations and the mayor oversees policy".
- **Biddeford, Waterville, Westbrook** still hold partisan elections and "began with 'strong' mayors"; Waterville's
  administrative authority moved off the mayor in 2005.

How a mayor is chosen varies by charter (MMA): directly elected in Augusta, Portland; chosen "among the membership
of the council" in Bangor and Rockland; Eastport has no mayor, its top official is the council chair. Wikipedia
pages (unverified against charters) add a directly elected mayor in Auburn, Gardiner, Hallowell and Sanford, and a
council-chosen one in South Portland.

**How a city's form is told:** only by its charter; every one is "X city".

## Organizations and roles

- **City Council**: legislative-executive, listed. Councillors elected (charter; MMA "five, seven or nine"). A mayor
  the council chooses is a member role on a councillor's post; a mayor the voters elect is a post of its own.
- **Mayor**: listed where the charter has voters elect one (`elected_by_voters`); a member role where the council
  chooses one.
- **City Manager or Administrator**: executive, listed, appointed by the council (charter; MMA).
- **Left out:** city clerk, treasurer, assessor (task offices, rule 5); school committee (special-purpose); boards
  of appeals and assessment review (quasi-judicial, MMA).

## Statute urls for `general_law`

None: a city reads its charter, with the town sections of
[2026-11-20-research-me-towns.md](2026-11-20-research-me-towns.md) behind it where it is silent.

## Net result

- **Forms:** `council_manager` (City Council with Council Member and Mayor; City Officers with City Manager) and
  `mayor_council` (City Council; Office of the Mayor; City Officers with City Manager), both on the suffix `city`, so
  a run's pick or a person saves each city's form. Westbrook is `mayor_council`; Portland, Lewiston and the
  directly-elected-mayor cities are decided per charter in step 6.
- **Left out:** clerk, treasurer, assessor, school committee, quasi-judicial boards.

## Open

- A per-city form list from each charter. Step 4's code-directory table gives the charter urls.

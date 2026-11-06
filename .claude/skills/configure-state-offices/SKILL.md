---
name: configure-state-offices
description: After a state's jurisdictions exist in open-data (its add-new-state skill), research the state's law and write the offices config that pipelines collect from, then bring the state online on civicpatch.org. Use when the user asks to configure a state's offices, research a state's local government law, or finish bringing a new state online.
tools: Read, Edit, Write, Bash, Glob, Grep
---

# Configure a State's Offices

Run open-data's `add-new-state` skill first: this one starts once the state's `jurisdictions.yml` files exist.

## What to collect

Only legislative and executive bodies (agreed 2026-10-30):

1. **Research lists the legislative and executive organizations the state's law establishes**
   (general law, then charter, then bylaws and ordinances) and only the roles the law names in
   them, each organization labelled `legislature` or `executive`. Courts and special-purpose or
   advisory boards (library, cemetery, parks, planning, budget) are not listed. Pipeline 2 asks
   about each listed role per place and records `established` and `filled_by`.
2. **Presiding offices the members choose** (council president, chair) are member roles on a
   member's post, not posts of their own.
3. **Every other role is a post that carries its selection method**, as the law read set it for
   the place: elected officials are the posts `elected_by_voters`; an appointed manager is a
   post `appointed`, kept in the data and filtered out of the elected view.
4. **The law names it but not how it is filled (`not_stated`): dropped.**
5. **Being named in the law, or even elected, is not enough: read what the office does** (added
   2026-11-03). An office that only carries out tasks is not listed, however old its title. Ask of
   its duties statute: does it decide policy, ordinances, budgets or taxes, or run the government
   day to day? Can a town simply vote to abolish it? Vermont's constable is named and usually
   elected, but its duties are serving papers and destroying animals (24 V.S.A. § 1936a(b)), a town
   may bar its law enforcement (§ 1936a(a)) and may eliminate it (17 V.S.A. § 2651a(d)): not listed.
   Keep its role in the config so its title still parses; just leave it out of every form.

State offices elected locally (district attorney) are not the jurisdiction's and are not listed.
Where an office is elected in some places and appointed in others, list it; the law read decides
per place.

Cite the statute or charter section for each organization and role in the config.

## Step 1: Research the law

List an office only if a statute or charter states it; nothing from memory or another state.
Research goes to `.docs/YYYY-MM-DD-research-<state>-<subject>.md`, one doc per classification
(cities, towns, counties) when they are governed differently, each quoting only the relevant
snippet of a source with a link to its section.

1. **The layers, once per state.** How the constitution, statutes, charters and ordinances rank,
   cited. Two answers decide the config's `governed_by`:
   - What a charter's silence means. Vermont: the general law fills it. Oregon: the office is not
     established, so a charter is read alone.
   - Which places run under general law at all. Oregon: every city has a charter; 27 of 36
     counties have none and read ORS 203 and 204.
2. **Forms of government per classification**: each form's organizations and the roles the law
   names in them, filtered by "What to collect". Count how many places use each form, and say how
   a place's form can be told (by suffix, or only by its own charter). A form no country form fits
   is the state's own (Oregon's county court).
3. **The statute urls** a general-law place reads, one per chapter (Oregon:
   `oregonlegislature.gov/bills_laws/ors/ors203.html`). These become `general_law`.
4. **Where each place's law is published.** Two directories list the places whose code a host
   publishes, and their links are real, unlike urls a search writes from memory:
   - **ICC Code Solutions**, https://www.icccodesolutions.org/text-library/ : fetch it yourself,
     one public page, plain fetch. Each state is a `div.state <XX>` (`div.state OR`) holding one
     `a.codeLink` per place, text like "City of Albany" or "Clatsop County". It covers eCode360,
     American Legal and Code Publishing (`*.municipal.codes`; codepublishing.com/<XX>/ now
     redirects here).
   - **Municode**, https://library.municode.com/<xx> , and the JSON behind it,
     https://api.municode.com/Clients/stateAbbr?stateAbbr=<XX> (`ClientName`, `ClassificationId`,
     `Website`): an agent cannot open it, plain or by browser (Cloudflare, 403). Stop and hand the
     api url over to be opened in a browser and the JSON saved; never work around the block.

   Match each entry to the state's places (`jurisdictions.yml` names, "Albany city") with pipeline
   1's own `charter_title_matches`
   (`pipelines/src/runners/pipeline01_governing_law_collector/finders/state_index.py`), titles
   "{lsad} of {place}" and "{place} {lsad}"; Municode's `ClientName` is the bare place, so
   "{place}". Don't write a new matcher. Report the matched, the ambiguous (more than one entry
   fits) and the unmatched by name form (Oregon: Dunes City, Lincoln City, Mt. Angel, Monroe).

   A listed code is a lead, not a charter: check its front page or table of contents for a charter
   heading, and record per host what a fetch allowed. Oregon, 2026-11-06:
   - eCode360: plain fetch works; 49 of 55 codes have a charter heading, the 4 without are
     statutory counties.
   - American Legal: browser only; 24 places.
   - `*.municipal.codes`: refuses plain and browser; 20 places, a person.
   - Municode: refuses us; 55 places, a person.

   Output: a table in the research doc of each place, its host, its code url and whether the
   charter is in the code (yes / no / not checked, and why), with counts per host. These are the
   urls a person uses for `source_blocked` and `governing_law_not_found` issues, and a lead for the
   planned code-directory finder. Where a Municode snapshot is kept for runs is not decided; until
   then it is recorded in the research doc.
5. **A "Net result" section** at the end: the forms, organizations and roles to configure, each
   with its citation, and what is left out and why (Oregon: elected recorder, judge and auditor,
   not legislative or executive).

### Ground truth for about five places

Current officers of a large city, a mid city, a small one, and one county per form, in
`.docs/YYYY-MM-DD-ground-truth-<state>-<subject>.yml`, in this shape:

```yaml
towns:
  ocd-jurisdiction/country:us/state:or/place:corvallis/government:
    - office: mayor
      holders: [Charles Maughan]
      method: E
      source: "https://www.corvallisoregon.gov/mc"
    - office: city-manager
      holders: [Mark Shepard]
      method: A
      basis: charter
      source: "..."
      as_of: "2026-02-21"
```

`method` is E (elected) or A (appointed). Every entry names its source; one that is not
current or not certain says `# not confirmed:` and why. Many city sites refuse plain reads
(403): use their reports, agendas and search results. A place with no website url in
`jurisdictions.yml` gets no own-site crawl in pipeline 1 (Oregon: 42 of 240 cities), so the
directory lookup in item 4 is often its only lead. The scrape is scored against this file.

## Step 2: Write the config

From the research's "Net result" only. Files in open-data, beside the state's `jurisdictions.yml`:
`data_source/<state>/local/config.yml` and `data_source/<state>/counties/config.yml`. Read
Oregon's two and `shared/src/shared/utils/layered_config.py` (the models) before writing.

1. **Roles.** A state file lists only roles the country level files (`data_source/local/config.yml`,
   `data_source/counties/config.yml`) lack, like Oregon's `sheriff`. A title the state writes
   differently is an alias on the country role, in the level file (`County Clerk`).
2. **`government_forms`**, keyed by `GovernmentForm` (`shared/src/shared/schemas.py`). Each lists
   its organizations with the role labels in them; `{lsad}` in a name takes the place's suffix
   ("{lsad} Council" is "Town Council" for a town).
   - `suffixes` offers the form to every place whose name ends in one; when several forms share a
     suffix, pipeline 2's law read decides per place (Oregon's two county forms).
   - A form with no `suffixes` applies only where it is saved on the jurisdiction in cp.org
     (Portland's `mayor_council`): set `extras_government_form` there, never by a PR.
   - Every suffix from `add-new-state`'s dry-run needs a form (`test_every_suffix_has_a_form_of_the_states_own`).
3. **`governing_law.classifications`**: per class, its `lsad`, `governed_by` (a `GovernedBy`
   value, from the research's layers) and `general_law` (the statute urls); `charter_terms` lists
   what the state calls a charter.
4. **Comments** cite the law for each form, organization and role, and say what is left out and
   why (top of Oregon's files).

**A form no `GovernmentForm` value fits** is a code change in civicpatch-tools first: the enum
value with a comment citing the law, a migration widening
`jurisdictions_extras_government_form_check`, `DATABASE.md`. Ship it to `main` and prod before
the open-data PR: open-data's CI installs `shared` from `main`, and prod's check constraint must
allow the value. (Oregon: `county_court`, migration 265.)

**Tests** in `tests/test_config.py`: add a label test like `OR_COUNTY_LABELS`, the titles the
state's own pages write mapped to the role each must parse to. Run against local `shared`:

```bash
cd ~/open-data && uv run --with-editable ~/civicpatch-tools/shared pytest -q tests/test_config.py
```

**Done when:** the tests pass and the open-data PR is open.

## Step 3: Bring the state online (maintainers)

Hand each command over as a full, pasteable block; never run a write to prod or a paid scrape
yourself.

1. **Full run** in open-data (free): `mise run setup-state -- --state <state>`.
2. **OCD-IDs**: `uv run python scripts/ocdids/fix.py --state <state> --dry-run` first, then
   without `--dry-run` to accept fixes.
3. **Merge** the jurisdictions and config to open-data's main. No manual sync: configs sync on
   merge (`.github/workflows/post_merge_config.yml`, level files first) and cp.org reads the
   jurisdictions within the hour (the `ReadOpenDataJurisdictionsWorkflow` schedule).
4. **Maps**: `mise run generate-maps -- prod <state>` in civicpatch-tools. Needed once per new
   state: it fills `meta_parent_ocdids`, so until it runs no place has its county.
5. **Prod check**: count each place's organizations against its form's, after the sync, with a
   read-only query against prod, handed over. **Done when:** every place holds its form's
   organizations.
6. **The ground-truth places first**: scrape them, score each against the ground truth, state the
   cost beforehand. **Done when:** every miss is explained and the cost per place recorded.
7. **The rest of the state.** **Done when:** most places hold their governing organization and
   the failures are counted by cause.

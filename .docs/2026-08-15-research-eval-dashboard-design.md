# Research: what view actually answers "did this prompt edit help?"

Date: 2026-08-15
Context: the eval dashboard (`pipelines/tests/prompts/tests/evals/dashboard.html`) shows
provider quality well and change-over-time poorly. 2.2 in the role-taxonomy plan rewrites
the officials prompt, and we currently cannot tell a real improvement from sampler noise.

## The goal, stated precisely

Three questions, in priority order:

1. **Did this prompt edit help?** — blocks 2.2. Not currently answerable.
2. **Is quality holding over time?** — partly answerable since run history landed.
3. **Which provider?** — already answered (see the plan's provider table).

Everything below is aimed at (1).

## The measured problem

Nine runs of the **identical** prompt (`ad464384`), identical fixtures, `temperature=0`
and a fixed seed, taken within 11 minutes:

| provider | metric | run 1 → 2 → 3 | swing |
|----------|--------|---------------|-------|
| DigitalOcean | end_date | 1.000 → 0.444 → 0.933 | **0.556** |
| AtlasCloud | image | 0.667 → 0.966 → 0.933 | 0.299 |
| DigitalOcean | phone | 0.571 → 0.810 → 0.740 | 0.238 |
| all | roles | 0.976–0.992 | 0.016 |
| all | district | 1.000 | 0.000 |

A prompt edit would have to move a metric by more than that to be visible at all. Most
won't.

## What the literature says

**Control charts are the standard tool for exactly this question** — separating
"special cause" (a real change) from "common cause" (noise):

> "Control charts plot sample statistics with ±3σ control limits, separating common-cause
> noise from special-cause signals."
> — [SPC Charts guide](https://www.invensislearning.com/blog/spc-charts-guide/)

**But they do not fit our sample size.** The same sources are explicit:

> "Very small datasets or irregular sampling intervals produce unstable charts that
> resemble noise rather than true process performance… success requires rational subgroups
> and ≥ 20 points."
> — [SPC Charts guide](https://www.invensislearning.com/blog/spc-charts-guide/)

We have 3 runs per provider and each run costs ~$0.039 and ~4 minutes. Getting to 20 is
~$0.80 and ~80 minutes *per prompt version*, and the limits would still be recomputed every
time a fixture changes. **Rejected on cost/benefit, not on principle.**

**The design that does fit is paired comparison**, because we hold the fixtures constant:

> "Paired analysis leverages correlation between model responses on identical inputs by
> analyzing per-example score differences… This method typically produces narrower
> confidence intervals and greater statistical precision by removing variability due to
> example-specific difficulty differences, which directly leads to increased statistical
> power."
> — [Confidence and Stability of Global and Pairwise Scores in NLP Evaluation](https://arxiv.org/pdf/2507.01633)

That is the whole game: the variance we are drowning in is *between-case difficulty*
variance, and pairing removes it. We already store per-case scores in `history.yml`, so the
data for this exists today.

## What our own data says — the decisive finding

Across 6 consecutive-run pairs (3 providers × 2 pairs), the **noise is concentrated in a
third of the corpus**:

| case | runs where it changed (of 6) |
|------|------------------------------|
| golinda_mixed_city_county | 4 |
| redundant_place_role | 4 |
| austin_district7_council_member | 3 |
| coleman_council | 3 |
| mixed_current_past | 3 |
| board_of_aldermen | 2 |
| inverted_name_format, la_porte_council, placeholder_name_council, raisin_township_clerk, vacant_positions_council | 1 |
| **austin_city_manager_staff, austin_council, nav_links_no_names, raisin_township_supervisor** | **0 — never moved** |

DigitalOcean's 0.556 swing on `end_date` was **9 of 15 cases moving**; DeepInfra's
second pair moved **0 cases**. The aggregate hides which of those happened, and they mean
opposite things.

**So the same five cases flap every time, and four never do.** That is a property of the
corpus, not of any prompt.

## Recommendation

### 1. A case × run stability grid — the highest-value addition

Rows = cases, columns = runs, cell = score. Small multiples, one grid per provider:

> "Small multiples use the same basic graphic or chart to display different slices of a
> data set… without trying to cram all that information into a single, overly-complex
> chart."
> — [Better Know a Visualization: Small Multiples](https://www.juiceanalytics.com/writing/better-know-visualization-small-multiples)

This makes the flapping cases self-identifying. Read a prompt change by looking at the
*stable* rows first — a move there is real; a move in `golinda_mixed_city_county` is not.

### 2. Paired per-case deltas for prompt A vs prompt B — the thing 2.2 needs

Not "F1 went from 0.85 to 0.88". Instead: of 15 cases, N improved, M regressed, K unchanged,
**restricted to cases that are stable across same-prompt runs**. A slopegraph or dumbbell is
the standard rendering:

> "A dumbbell chart emphasizes the size of the gap between two values, whereas a slope chart
> emphasizes direction and steepness."
> — [Dumbbell Chart best practices](https://www.domo.com/learn/charts/dumbbell-plot-chart)

Prefer the slopegraph: direction per case is what matters, magnitude is mostly noise.

### 3. Mark unstable cases in the main table

A metric whose score is dominated by known-flapping cases should say so, rather than being
read as a quality number.

### 4. Do NOT

- **Do not add control charts.** ≥20 points needed; we have 3, and they cost money.
- **Do not gate on metrics whose threshold sits inside their own swing.** `image` (0.70
  threshold, 0.299 observed swing) and `person` (0.94 threshold, 0.018 swing but 0.930
  observed) will flap red regardless of quality. Either widen them using the measured
  swing, or make them report-only.
- **Do not compare single runs.** Any A/B needs ≥3 runs per arm, and the comparison should
  be per-case, not per-aggregate.

## Sequencing

The stability grid (1) uses data already in `history.yml` and needs no new runs. It should
come first, because it is also what tells you whether (2) is trustworthy — a paired
comparison restricted to stable cases is only possible once you know which those are.

## Sources

- [Statistical Process Control (SPC) Charts: A Detailed Guide](https://www.invensislearning.com/blog/spc-charts-guide/)
- [Control Charts (Process Behavior Charts) Explained Simply](https://blog.kainexus.com/improvement-disciplines/lean/control-charts/an-introduction-to-process-control-charts)
- [Confidence and Stability of Global and Pairwise Scores in NLP Evaluation](https://arxiv.org/pdf/2507.01633)
- [Paired evaluation of machine-learning models characterizes effects of confounders and outliers](https://pmc.ncbi.nlm.nih.gov/articles/PMC10435952/)
- [Better Know a Visualization: Small Multiples](https://www.juiceanalytics.com/writing/better-know-visualization-small-multiples)
- [Dumbbell Chart: Definition, Examples, and Best Practices](https://www.domo.com/learn/charts/dumbbell-plot-chart)
- [Beyond the Bar: Alternative Methods for Visualizing Two Points of Change](https://nightingaledvs.com/beyond-the-bar-alternative-methods-for-visualizing-two-points-of-change/)

from decimal import Decimal

from pydantic import BaseModel


class StateSpend(BaseModel):
    """What a state's collection cost over the window, and the average cost of one run in it.

    Maintainer-only, unlike the rest of the state summary — see the router.

    **Nothing is ever 0.** `$0.00` would claim a state scraped for free, which is a different
    and false thing from not scraping. Two levels say so:

    - a **null** figure — the state spent nothing in *that* window,
    - an **absent state** — it spent nothing in either window.

    `cost_per_scrape_usd` is the schedule-independent measure — a bare total mostly ranks how
    often a state was scraped, so it answers "who runs most", not "who is expensive".

    ⚠ Both **exclude the grounded Google calls**: their API states no cost (grounding is sold on
    a quota, so per-call spend is not defined), and they are kept out of `llm_calls` rather than
    written as zero. Whatever renders these has to say so.
    """

    state: str
    spend_usd: Decimal | None = None
    # The window before this one, same length, for "is this state spending more than it was".
    prior_spend_usd: Decimal | None = None
    cost_per_scrape_usd: Decimal | None = None

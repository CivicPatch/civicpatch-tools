"""Which facts still count.

A fact is live if no live withdraw points at it. A withdraw is itself a fact, so it can be
withdrawn, and that is the whole of undo: rolling back a rollback withdraws its withdraws, and
what they cancelled comes back.

    alice's claim  <-- w1 (a vandal withdraws it)  <-- w2 (the rollback of the vandal)

    w2: nothing points at it          -> live
    w1: a live withdraw points at it  -> dead
    alice's claim: only w1 points at it, and w1 is dead -> live
"""

from core.projection.facts import Facts


def live_facts(facts: Facts) -> Facts:
    """The same facts with everything a live withdraw points at removed.

    Liveness is recursive, so answer it per id and remember the answer: a withdraw chain is
    rarely deeper than two, but a rollback of a rollback of a rollback is three and nothing
    bounds it.

    Every kind of fact can be withdrawn, records and page rows included. A rollback of a
    scrape that read an organization and listed nobody has only a page row to withdraw, and
    if that row survives, the organization stays "read" and the people it retired stay
    retired.
    """
    fact_id_to_withdraws: dict[str, list] = {}
    memo: dict[str, bool] = {}

    for withdraw in facts.withdraws:
        fact_id_to_withdraws.setdefault(withdraw.entity_id, []).append(withdraw)

    def live(fact_id):
        if fact_id in memo:
            return memo[fact_id]
        is_live = not any(live(w.id) for w in fact_id_to_withdraws.get(fact_id, []))
        memo[fact_id] = is_live
        return is_live

    return Facts(
        records=tuple(r for r in facts.records if live(r.id)),
        claims=tuple(c for c in facts.claims if live(c.id)),
        withdraws=tuple(w for w in facts.withdraws if live(w.id)),
        reads=tuple(r for r in facts.reads if live(r.id)),
    )

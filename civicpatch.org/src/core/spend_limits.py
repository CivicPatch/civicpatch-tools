"""Which cap, if any, a month's spend has reached.

Pure: the caller supplies the two figures and the two caps. There are three caps in this
system and they bound different things — one run, one state's month, every state's month — so
the answer says *which*, not just yes. A caller that only knew "over" could not tell an operator
whether to raise one state's cap or the global one.
"""

from decimal import Decimal
from enum import StrEnum


class Cap(StrEnum):
    STATE_MONTH = "state_month"
    GLOBAL_MONTH = "global_month"


def cap_reached(
    state_spent: Decimal,
    state_cap: Decimal | None,
    global_spent: Decimal,
    global_cap: Decimal | None,
) -> Cap | None:
    """`None` for either cap means no cap at that scope, never a cap of zero — those are
    different settings, and `$0` is a real one meaning spend nothing.

    `>=`, matching the per-run cap: at a cap of `$0` a state is already at its cap before it
    starts, which is what makes `$0` usable as a stop switch.

    The state is reported first when both are reached. It is the narrower fix, and raising it
    would not help while the global one is also spent — but naming the global one first would
    send an operator to change the wrong number.
    """
    if state_cap is not None and state_spent >= state_cap:
        return Cap.STATE_MONTH
    if global_cap is not None and global_spent >= global_cap:
        return Cap.GLOBAL_MONTH
    return None

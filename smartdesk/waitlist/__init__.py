"""Slot recovery: the empty chair (docs/workflows/slot-recovery.md).

    store.py     the waitlist and the offers, kept in the business's folder
    recovery.py  joining the waitlist; a cancelled slot offered to the earliest
                 matching waiter; a yes books it, a no or no answer offers the next
    routes.py    GET /api/widget/offer: the widget asks if its customer has an offer

Who is offered, and booking, are code; the Front Desk agent only hears the
customer and calls its tools (join_waitlist, answer_offer).
"""

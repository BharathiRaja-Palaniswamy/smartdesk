"""The customer's yes, before a Plan is booked or a booking cancelled.

This is the line between what the agents do alone and what needs the
customer: they may search, offer times and make a plan on their own, but a
plan is only booked, or a booking cancelled, after the customer says yes
to exactly what will happen. The graph, not a model, enforces it: it stops,
asks the question written here, and goes ahead only if the customer's
next message is a yes.

Three things wait for a yes:
  plan      the times found, every item of the plan (`plan_question`), after
            what the check found about the time asked for (`checked`: "16:00
            is free", "16:00 is taken"); for a change, which booking is
            cancelled and what is booked instead
  cancel    the booking to cancel (`cancel_question`)
  waitlist  joining the waitlist, and the number we will call (`waitlist_question`)
Booking (code) checked the plan against the calendar (booking.py) and
the cancellation against the 30-minute rule before asking, so the customer
is never asked to confirm something that would then fail.
"""

from datetime import datetime
from typing import Any

from ..booking.appointments import get_appointments
from ..business.store import get_schedule
from .booking import Plan, twelve
from .rules import BUT, YES, plain_quotes

# The replies to tap, by what is waiting for the yes.
CHOICES = {"plan": ["Yes, book it", "No"], "cancel": ["Yes, cancel it", "No, keep it"],
           "waitlist": ["Yes, add me", "No, thanks"]}



def is_yes(message: str) -> bool:
    """True when the customer's reply is a plain yes ("Yes, don’t" is not one)."""
    message = plain_quotes(message)
    return bool(YES.match(message)) and not BUT.search(message)


def day_words(day: datetime, spoken: bool) -> str:
    """'Friday 30 October' to read; 'Friday the 30th of October' to say."""
    if not spoken:
        return f"{day:%A} {day.day} {day:%B}"
    suffix = "th" if 11 <= day.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day.day % 10, "th")
    return f"{day:%A} the {day.day}{suffix} of {day:%B}"


def time_words(moment, spoken: bool = False) -> str:
    """'3 PM', '3:30 PM': to read and to say alike (booking.twelve)."""
    return twelve(moment)


def when(start: datetime, spoken: bool) -> str:
    """'Friday 30 October at 15:00' to read; 'Friday the 30th of October at 3 PM' to say."""
    return f"{day_words(start, spoken)} at {time_words(start, spoken)}"


def checked(asked: dict[str, Any], time_said: str, plan: Plan, spoken: bool) -> str:
    """What the check found about the one time the customer asked for (their words name
    one, `time_said`, or the request's window is one time): "16:00 is free. " when the
    plan starts then; when it starts at another, why: "We open at 10:00 on Sundays. "
    or "We close at 17:00 on Sundays. " for a time outside the day's hours, otherwise
    "16:00 is taken. ", so a different time is never offered without the true reason;
    "" when they asked for no one time."""
    from .details import one_time  # imported here: details.py imports this module

    after, before = asked.get("after", ""), asked.get("before", "")
    exact = after if after and (after == before or (not before and one_time(time_said))) else ""
    if not exact or not plan.items:
        return ""
    start, clock = plan.items[0].start, datetime.strptime(exact, "%H:%M")
    said = twelve(clock)
    if start.strftime("%H:%M") == exact:
        return f"{said} is free. "
    hours = get_schedule().hours.get(start.weekday())  # the opening hours: the schedule's, no calendar needed
    if hours and clock.time() < hours[0]:
        return f"We open at {twelve(hours[0])} on {start:%A}s. "
    if hours and clock.time() >= hours[1]:
        return f"We close at {twelve(hours[1])} on {start:%A}s. "
    return f"{said} is taken. "


def plan_question(plan: Plan, name: str, phone: str, spoken: bool = False,
                  replaces: dict[str, Any] | None = None) -> str:
    """What to ask before booking `plan`: every item, in order, written to be read
    or to be said on a phone call (`spoken`). For a change, it says first which
    booking is cancelled (`replaces`, as actions.confirmation gives it), so the
    customer knows exactly what happens to both."""
    services = get_appointments().schedule.services
    parts = []
    for n, item in enumerate(plan.items):  # the add-ons go with the first appointment
        length = item.minutes or services[item.service].minutes[0]
        extras = f" plus {' and '.join(plan.add_ons).lower()}" if plan.add_ons and n == 0 else ""
        parts.append(f"a {length}-minute {item.service}{extras} with {item.staff_member} on {when(item.start, True)}"
                     if spoken else f"{item.service}{extras} ({length} minutes) with {item.staff_member} on "
                                    f"{when(item.start, False)}")
    if replaces:
        old_start = datetime.fromisoformat(replaces["start"])
        old = (f"your {replaces['service']} on {when(old_start, True)}" if spoken else
               f"your current booking ({replaces['service']} with {replaces['staff_member']} on "
               f"{when(old_start, False)}, {replaces['reference']})")
        new = (", then ".join(parts) if spoken or len(parts) == 1
               else "these: " + " ".join(f"{n}. {part}." for n, part in enumerate(parts, 1)))
        lead = "Just to confirm: I'll" if spoken else "I'll"
        return f"{lead} cancel {old} and book {new} instead, for {name}. Shall I go ahead?"
    if spoken:
        return (f"Just to confirm: {', then '.join(parts)}, for {name}. "
                f"Shall I book {'them' if len(parts) > 1 else 'it'}?")
    if len(parts) == 1:
        return f"Shall I book {parts[0]}, for {name} ({phone})?"
    listed = " ".join(f"{n}. {part}." for n, part in enumerate(parts, 1))
    return f"Shall I book these for {name} ({phone})? {listed}"


def cancel_question(bookings: list[dict[str, Any]], spoken: bool = False) -> str:
    """What to ask before cancelling `bookings` (as actions.confirmation gives
    them), written to be read, or to be said on a phone call (`spoken`)."""
    def one(booking: dict[str, Any], spoken: bool) -> str:
        start = datetime.fromisoformat(booking["start"])
        return (f"your {booking['service']} on {when(start, True)}" if spoken else
                f"your {booking['service']} with {booking['staff_member']} on {when(start, False)} "
                f"(reference {booking['reference']})")
    if spoken:
        return (f"Just to confirm: cancel {', and '.join(one(b, True) for b in bookings)}. "
                f"Shall I cancel {'them' if len(bookings) > 1 else 'it'}?")
    if len(bookings) == 1:
        return f"Shall I cancel {one(bookings[0], False)}?"
    listed = " ".join(f"{n}. {one(b, False).removeprefix('your ')}." for n, b in enumerate(bookings, 1))
    return f"Shall I cancel these {len(bookings)} bookings? {listed}"


def _waited(waitlist: dict[str, Any], spoken: bool) -> str:
    """"Signature Radiance Facial on Friday 13 November at 17:00": the waitlist, as said back."""
    day = day_words(datetime.fromisoformat(waitlist["day"]), spoken)
    after, before = (twelve(datetime.strptime(waitlist[key], "%H:%M")) if waitlist.get(key) else ""
                     for key in ("after", "before"))
    times = (f"at {after}" if after and after == before else f"between {after} and {before}" if after and before
             else f"from {after}" if after else f"before {before}" if before else "at any time")
    return f"{waitlist['service']} on {day} {times}"


def waitlist_question(waitlist: dict[str, Any], phone: str, spoken: bool = False) -> str:
    """What to ask before adding the customer to the waitlist: what for, and the number we will call."""
    return f"Shall I add you to the waitlist for {_waited(waitlist, spoken)}? If it opens up, we'll call you at {phone}."


def done_message(result: dict[str, Any], spoken: bool = False) -> str:
    """What to tell the customer once their yes is carried out: each booking made,
    with its reference (theirs to change or cancel it later), and each one cancelled.
    "" when something was not done: then the agent explains, from the result. Written
    by code, as the questions are, so no reference or time can be left out or changed."""
    if result.get("not_booked") or result.get("not_cancelled") or result.get("error"):
        return ""
    if result.get("waiting"):
        return f"You're on the waitlist for {_waited(result, spoken)}. If it opens up, we'll call you."
    def said(reference: str) -> str:  # on a call, letter by letter
        return " ".join(reference) if spoken else reference
    def one(booking: dict[str, Any]) -> str:
        start = datetime.fromisoformat(booking["start"])
        return f"{booking['service']} with {booking['staff_member']} on {when(start, spoken)}, reference {said(booking['reference'])}"
    parts = []
    if booked := result.get("booked"):
        parts.append("You're booked: " + "; ".join(one(b) for b in booked) + ".")
        if replaced := result.get("cancelled"):  # a change: the booking it replaces
            parts.append(f"Your previous booking, {said(replaced)}, is cancelled.")
    elif cancelled := result.get("cancelled"):
        parts.append("Cancelled: " + "; ".join(one(b) for b in cancelled) + ".")
    if not parts:
        return ""
    return " ".join(parts) + (" We look forward to seeing you!" if booked else " Is there anything else I can help with?")

"""The booking engine's actions, in the shape a model's tool request takes.


Booking and cancelling are not here: a model never books or cancels
directly. Booking (code) offers a plan or a cancellation, and once the
customer says yes, code carries it out (smartdesk/agent/executor.py).

Each takes the arguments of a model's request (a dict) and returns what the
model is told (something JSON can hold). Every action goes through the
booking rules (appointments.py), so it can only do what those rules allow,
whatever the model asks. A broken rule comes back as {"error": "..."},
written for the customer, so the model can pass it on or try again
(`guarded`).

How these are offered to a model, and to whom, is frontdesk/agent.py.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .calendars import Booking
from .errors import UNAVAILABLE, BookingError, CalendarUnavailable

log = logging.getLogger("smartdesk.booking")


def guarded(run: Callable[[dict[str, Any]], Any]) -> Callable[[dict[str, Any]], Any]:
    """`run`, with a broken booking rule, or a calendar that cannot be
    reached, returned as {"error": ...} instead of raised."""
    def wrapped(args: dict[str, Any]) -> Any:
        try:
            return run(args)
        except BookingError as error:
            return {"error": str(error)}
        except CalendarUnavailable as error:
            log.warning("calendar unavailable: %s", error)  # the reason, for whoever reads the server log
            return {"error": UNAVAILABLE}
        except ValueError:  # a date or time the model wrote in the wrong format
            return {"error": "Dates are YYYY-MM-DD and times YYYY-MM-DDTHH:MM, in the business's time zone."}
    return wrapped


def _when(moment: datetime) -> str:
    """A time as the tools write it: '2026-10-24T15:00'."""
    return moment.strftime("%Y-%m-%dT%H:%M")


def confirmation(booking: Booking) -> dict[str, Any]:
    """What the customer is told about their own booking (in the chat, on a call, and on the booking form)."""
    return {"reference": booking.id, "service": booking.service, "staff_member": booking.staff_member,
            "start": _when(booking.start), "end": _when(booking.end), "name": booking.name,
            **({"add_ons": list(booking.add_ons)} if booking.add_ons else {})}

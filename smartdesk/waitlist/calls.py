"""The keypad call to the customer offered a slot (D34, D39).

When an offer opens (recovery._offer: after a cancellation, a "no", or an
offer running out), SmartDesk phones the waitlisted customer from the
business's own number (its phone line, onboarding/phone.py) through Twilio.
No AI speaks: Twilio reads the offer, in a natural neural voice
(SMARTDESK_CALL_VOICE), and waits for one key.

    "Hi Raja! It's Test Studio, with good news. The Prenatal Massage you asked
     for, on Friday 13 November at 4 PM, just opened up. To book it, press 1.
     If you'd rather not, press 2."

    1  the slot is booked for them, exactly as offered, after checking it is
       still free (recovery.answer); the call says the booking and its reference
    2  the offer is let go and the next customer on the waitlist is called
    no key, or another one: the question is asked once more; then the call
       ends and the offer stays open until it runs out

The key comes back to SmartDesk (routes.py, POST /api/waitlist/answer) with
the offer's own private key in the address, so nobody but that call can
answer that offer. Nothing is booked without the customer's 1: a slot is
never moved to anyone by itself.

A call is placed only when Twilio is set up (TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN, SMARTDESK_PUBLIC_URL), the business has a phone line, and
the business is open (SMARTDESK_CALL_ANY_TIME=true lifts that, for testing);
otherwise the offer waits until the customer is next in touch. It runs in the background, so a cancellation's reply never waits on
it; a call that fails is logged, and the offer stays open.
"""

import logging
import threading
from datetime import datetime
from typing import Any
from xml.sax.saxutils import escape, quoteattr

import httpx

from ..business.store import get_knowledge, get_schedule
from ..config import get_settings
from ..onboarding.phone import dialable

CALLS = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json"
TIMEOUT = 15  # seconds to wait for Twilio to accept the call
WAIT_FOR_KEY = 8  # seconds the customer has to press a key, each time it is asked
log = logging.getLogger("smartdesk.waitlist")


def set_up() -> bool:
    """Whether keypad calls can be placed: Twilio, a public address and the business's line."""
    from ..onboarding.store import live_phone  # imported here: onboarding imports the agent, which imports this

    s = get_settings()
    return bool(s.twilio_account_sid and s.twilio_auth_token and s.public_url and live_phone())


def open_now(now: datetime) -> bool:
    """Whether customers may be called at `now`: while the business is open, or at any
    time when SMARTDESK_CALL_ANY_TIME is on (for testing)."""
    if get_settings().call_any_time:
        return True
    hours = get_schedule().hours.get(now.weekday())
    return bool(hours) and hours[0] <= now.time() < hours[1]


def spoken_time(start: datetime) -> str:
    """"4 PM", "4:30 PM": a time as people say it (frontdesk/booking.twelve)."""
    from ..frontdesk.booking import twelve  # imported here: the agent's tools import this module

    return twelve(start)


def offer_words(offer: dict[str, Any]) -> str:
    """The offer, as the call reads it: warm, short, the choice last."""
    start = datetime.fromisoformat(offer["start"])
    return (f"Hi {offer['name']}! It's {get_knowledge().name}, with good news. The {offer['service']} you asked "
            f"for, on {start:%A %-d %B} at {spoken_time(start)}, just opened up. "
            "To book it, press 1. If you'd rather not, press 2.")


def _say(words: str) -> str:
    return f"<Say voice={quoteattr(get_settings().call_voice)}>{escape(words)}</Say>"


def answer_url(offer: dict[str, Any]) -> str:
    """Where Twilio sends the key pressed: this offer, with its private key."""
    return f"{get_settings().public_url.rstrip('/')}/api/waitlist/answer/{offer['id']}?key={offer['key']}"


def ask(offer: dict[str, Any], again: bool = False) -> str:
    """TwiML that reads the offer and waits for one key; asked a second time if
    nothing is pressed (unless `again`: this is the second time), then goodbye."""
    gather = (f'<Gather numDigits="1" timeout="{WAIT_FOR_KEY}" method="POST" action={quoteattr(answer_url(offer))}>'
              f"{_say(offer_words(offer))}</Gather>")
    second = "" if again else gather
    return (f"<Response>{gather}{second}{_say('We did not hear a choice, so we will hold it for you a little longer. Bye for now!')}"
            "</Response>")


def say(words: str) -> str:
    """TwiML that says `words` and ends the call."""
    return f"<Response>{_say(words)}</Response>"


def place(offer: dict[str, Any]) -> str | None:
    """Call the customer of `offer` now. Returns Twilio's call id, or None when no
    call was placed (not set up, a number that cannot be dialled, a failure)."""
    from ..onboarding.store import live_phone

    s, to, line = get_settings(), dialable(offer["phone"]), live_phone()
    if not set_up() or to is None or line is None:
        return None
    try:
        response = httpx.post(CALLS.format(sid=s.twilio_account_sid), timeout=TIMEOUT,
                              auth=(s.twilio_account_sid, s.twilio_auth_token),
                              data={"To": to, "From": line.number, "Twiml": ask(offer)})
        response.raise_for_status()
        call_id = response.json().get("sid")
    except (httpx.HTTPError, ValueError) as error:
        log.warning("could not call for offer %s: %s", offer["id"], error)
        return None
    log.info("calling the customer for offer %s", offer["id"])
    return call_id


def call_soon(offer: dict[str, Any], now: datetime) -> None:
    """Place the call for `offer` in the background, if calls are set up and the
    business is open at `now`; otherwise the offer waits."""
    if set_up() and open_now(now):
        threading.Thread(target=place, args=(offer,), name=f"call-{offer['id']}", daemon=True).start()

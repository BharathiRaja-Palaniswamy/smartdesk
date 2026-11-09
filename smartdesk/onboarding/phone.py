"""The business's phone line, when the owner asks for phone support (D32).

A caller dials the line; ElevenLabs answers it and asks the Front Desk agent
what to say (smartdesk/voice/). The owner keeps their own business number and
forwards calls to this line from their phone provider (all calls, or only
unanswered or busy ones), so customers dial the number they already know.

Demo build: nothing is bought. The line is the one SMARTDESK_PHONE_NUMBER
names, already attached to the ElevenLabs agent (docs/guides/phone-demo.md).
After the demo: SmartDesk's own Twilio account, one subaccount per business
(its cell), buys a local number and connects it to ElevenLabs, after the
owner's yes to the cost; the page and this module's callers stay the same.
"""

import re
from dataclasses import dataclass

from ..config import get_settings

# What a line costs, shown to the owner before they agree (Twilio's US prices).
MONTHLY = 1.15  # dollars a month for a local number; the first month is free
PER_MINUTE = 0.0085  # dollars a minute of calls received
E164 = re.compile(r"^\+[1-9]\d{7,14}$")  # "+14155550123"


class LineUnavailable(Exception):
    """No phone line can be given now, with the reason for the owner."""


@dataclass(frozen=True)
class Line:
    number: str  # "+14155550123"
    demo: bool  # True: an existing line assigned, nothing bought


def available() -> bool:
    """Whether a line can be given now."""
    return bool(E164.match(get_settings().phone_number))


def get_line() -> Line:
    """The business's phone line. Raises LineUnavailable when there is none to give."""
    number = get_settings().phone_number
    if not E164.match(number):
        raise LineUnavailable("Phone support isn't available right now. You can add it later.")
    return Line(number=number, demo=True)


def shown(number: str) -> str:
    """"+14155550123" as people write it: "(415) 555-0123"; other countries as they are."""
    if number.startswith("+1") and len(number) == 12:
        return f"({number[2:5]}) {number[5:8]}-{number[8:]}"
    return number

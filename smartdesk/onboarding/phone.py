"""The business's phone line, set up at every Go live (D36, D37: phone support by default).

The line is the business's own number, the one the owner gave in the first
step: customers call the number they already know. The business's own
ElevenLabs agent answers it and asks the Front Desk agent what to say
(smartdesk/voice/). The same number calls a waitlisted customer when a slot
opens, as a keypad call through Twilio (waitlist/calls.py).

Setting up a line is all API calls, in this order (set_up):

    1. find the owner's number among those connected to ElevenLabs, and the
       agent it answers for now                  GET    /v1/convai/phone-numbers
    2. a workspace secret holding SMARTDESK_VOICE_SECRET, which the agent
       sends to SmartDesk on every turn          POST   /v1/convai/secrets
    3. the business's own agent: its greeting, the two lines the phone line
       reads (Call ID, Caller number), its voice, and the Custom LLM at
       SMARTDESK_PUBLIC_URL/v1                    POST   /v1/convai/agents/create
    4. the number attached to that agent         PATCH  /v1/convai/phone-numbers/{id}

If a step fails, what was made is taken down again (tear_down) and nothing
goes live. Reset takes the line down: the number goes back to the agent it
answered for before (none, or another product's), then the agent and the
secret are deleted.

A number not connected to ElevenLabs cannot be set up yet: the owner is told
so, and the business goes live with its website chat only. Connecting it (porting it to
SmartDesk's Twilio account, or the business's phone system over SIP) comes
after the demo; the steps above stay the same.
"""

import logging
import re
from dataclasses import dataclass

import httpx

from ..config import get_settings

API = "https://api.elevenlabs.io/v1/convai"
TIMEOUT = 20  # seconds for each ElevenLabs request
VOICE_STYLE = {"stability": 0.35, "similarity_boost": 0.8, "speed": 1.05}  # the agent's voice: expressive, brisk
NOT_NOW = "Phone support couldn't be set up right now. Your website chat is live; we'll set up the phone with you."
log = logging.getLogger("smartdesk.phone")

# The agent's prompt: SmartDesk's Front Desk agent does the talking (the Custom LLM);
# ElevenLabs fills in the last two lines on every call, which voice/call.py reads back.
PROMPT = """You are the front desk of {business}.
Call ID: {{{{system__conversation_id}}}}
Caller number: {{{{system__caller_id}}}}"""


class LineUnavailable(Exception):
    """No phone line can be set up now, with the reason for the owner."""


@dataclass(frozen=True)
class Line:
    number: str  # the business's number, "+14155550123"
    agent_id: str = ""  # the business's ElevenLabs agent
    phone_number_id: str = ""  # ElevenLabs' id for the number
    secret_id: str = ""  # the workspace secret the agent sends SmartDesk
    previous_agent_id: str = ""  # the agent the number answered for before; it gets the number back


def dialable(phone: str) -> str | None:
    """`phone` as a number to dial ("+14085550101"); None when it cannot be one.
    Ten digits are a US or Canadian number; a number written with "+" keeps its country."""
    found = re.sub(r"\D", "", phone)
    if phone.strip().startswith("+") and 8 <= len(found) <= 15:
        return "+" + found
    if len(found) == 10:
        return "+1" + found
    if len(found) == 11 and found.startswith("1"):
        return "+" + found
    return None


def available() -> bool:
    """Whether lines can be set up at all: SmartDesk's own phone settings are set."""
    s = get_settings()
    return bool(s.elevenlabs_api_key and s.public_url and s.voice_secret)


def _request(method: str, path: str, body: dict | None = None) -> dict | list:
    """One ElevenLabs request; its JSON answer ({} when it has none)."""
    response = httpx.request(method, f"{API}{path}", json=body, timeout=TIMEOUT,
                             headers={"xi-api-key": get_settings().elevenlabs_api_key})
    response.raise_for_status()
    return response.json() if response.content else {}


def agent_config(business: str, secret_id: str) -> dict:
    """The business's agent, as ElevenLabs creates it."""
    s = get_settings()
    me = f", this is {s.assistant_name}" if s.assistant_name else ""
    # Lively, not flat: less "stable" means more expression; a touch quicker than the default.
    voice = {"tts": {**({"voice_id": s.voice_id} if s.voice_id else {}), **VOICE_STYLE}}
    return {
        "name": f"SmartDesk · {business}",
        "tags": ["smartdesk"],
        "conversation_config": {
            "agent": {
                "first_message": f"Hi, thanks for calling {business}{me}. How can I help?",
                "language": "en",
                "prompt": {"prompt": PROMPT.format(business=business), "llm": "custom-llm", "temperature": 0,
                           "custom_llm": {"url": f"{s.public_url.rstrip('/')}/v1", "model_id": "smartdesk",
                                          "api_key": {"secret_id": secret_id}, "api_type": "chat_completions"}},
            },
            **voice,
        },
    }


def set_up(business: str, phone: str) -> Line:
    """Set up `business`'s phone line on its number `phone` (see above). Raises
    LineUnavailable, having taken down whatever it made, when it cannot."""
    s = get_settings()
    if not available():
        raise LineUnavailable("Phone support isn't available right now. Your website chat is live meanwhile.")
    number = dialable(phone)
    if number is None:
        raise LineUnavailable("Your phone number needs its area code for calls to be answered.")
    made = Line(number)
    try:
        connected = {dialable(p.get("phone_number", "")): p for p in _request("GET", "/phone-numbers")}
        if number not in connected:
            raise LineUnavailable(f"{shown(number)} isn't connected to SmartDesk's phone system yet; "
                                  "we'll connect it with you. Your website chat is live meanwhile.")
        found = connected[number]
        before = (found.get("assigned_agent") or {}).get("agent_id") or ""
        secret = _request("POST", "/secrets", {"type": "new", "name": f"smartdesk-voice-{_slug(business)}",
                                                "value": s.voice_secret})
        made = Line(number, secret_id=secret["secret_id"])
        agent = _request("POST", "/agents/create", agent_config(business, made.secret_id))
        made = Line(number, agent["agent_id"], found["phone_number_id"], made.secret_id, before)
        _request("PATCH", f"/phone-numbers/{made.phone_number_id}", {"agent_id": made.agent_id})
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as error:
        log.warning("phone line for %s not set up: %s", business, error)
        tear_down(made)
        raise LineUnavailable(NOT_NOW) from error
    log.info("phone line set up for %s on %s: agent %s", business, number, made.agent_id)
    return made


def tear_down(line: Line) -> None:
    """Take down what set_up made: the number back to the agent it had before, then
    the agent and the secret. Each part is tried even if another fails; a failure
    is logged, never raised."""
    steps = []
    if line.previous_agent_id and line.phone_number_id:
        steps.append(("PATCH", f"/phone-numbers/{line.phone_number_id}", {"agent_id": line.previous_agent_id}))
    if line.agent_id:
        steps.append(("DELETE", f"/agents/{line.agent_id}", None))
    if line.secret_id:
        steps.append(("DELETE", f"/secrets/{line.secret_id}", None))
    for method, path, body in steps:
        try:
            _request(method, path, body)
        except httpx.HTTPError as error:
            log.warning("could not %s %s: %s", method, path, error)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "business"


def shown(number: str) -> str:
    """"+14155550123" as people write it: "(415) 555-0123"; other countries as they are."""
    if number.startswith("+1") and len(number) == 12:
        return f"({number[2:5]}) {number[5:8]}-{number[8:]}"
    return number

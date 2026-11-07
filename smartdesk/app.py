"""The web app: the Front Desk chat and phone line, and the owner's console.

Run with:  uvicorn smartdesk.app:app --reload

This file is the wiring: it plugs each package's routes into one app. The
work happens in the packages: `frontdesk/` (the customer chat), `voice/`
(the phone line), `owner/` (the owner chat), `reports/` (the manage page),
`access/` (the owner's sign-in), `business/` (the business document).

Customers never visit this app's pages: they chat through the widget on the
business's own website (web/widget/), and call its phone number.

Routes:
  GET  /                        sends the owner to the manage page
  GET  /login                   the owner's sign-in page        (access/routes.py)
  POST /api/login, /api/logout  sign the owner in and out
  GET  /manage                  the owner's manage page         (reports/routes.py)
  GET  /api/report...           the reports' data               (reports/routes.py)
  POST /api/report/chat         the owner chat                  (owner/routes.py)
  GET  /api/profile             the whole business profile, for the manage page
  GET  /api/powered-by          which provider answers each chat, for the "Powered by" line
  POST /api/assistant           the customer chat: the Front Desk agent (frontdesk/routes.py)
  GET  /api/feedback...         customers' feedback cards, for the owner (frontdesk/routes.py)
  POST /v1/chat/completions     the phone line: the same agent, called by ElevenLabs (voice/routes.py)
  GET  /static/...              CSS and JavaScript for the owner's pages
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .access.routes import router as owner_sign_in
from .business.profile import build_profile
from .business.store import get_knowledge
from .frontdesk.routes import owner as feedback_cards
from .frontdesk.routes import router as front_desk
from .models.profiles import get_profile
from .models.providers import NAMES
from .owner.routes import router as owner_chat
from .reports.routes import page_router as manage_page
from .reports.routes import router as report_router
from .tracing import setup as setup_tracing
from .voice.routes import router as phone_line

STATIC = Path(__file__).parent / "static"
setup_tracing()  # before any request: hides personal details in every trace (tracing.py)
app = FastAPI(title="SmartDesk")
for router in (manage_page, report_router, owner_chat, owner_sign_in, front_desk, feedback_cards, phone_line):
    app.include_router(router)


@app.get("/")
def index() -> RedirectResponse:
    """The owner's start page: the manage page (which asks them to sign in first)."""
    return RedirectResponse("/manage")


@app.get("/api/profile")
def profile():
    """The whole business document, section by section, for the manage page's profile tab."""
    return build_profile(get_knowledge())


@app.get("/api/powered-by")
def powered_by():
    """The provider behind each chat, as people know it ("Claude", "Nebius"),
    read from the settings now, so it follows SMARTDESK_MODELS."""
    def name(profile: str) -> str:
        provider = get_profile(profile).primary.provider
        return NAMES.get(provider, provider)
    return {"customer": name("booking-agent"), "owner": name("chat-default")}


class FreshStaticFiles(StaticFiles):
    """Static files that the browser must re-check before reusing.

    Without this, a browser may keep using its saved copy of a JavaScript or
    CSS file after the file has changed, so an edit seems to have no effect.
    "no-cache" does not mean "never store": the browser keeps its copy but
    asks the server each time whether it is still current, and only downloads
    the file again when it has changed.
    """

    async def get_response(self, path, scope):
        """Serves the file as usual, then adds the "check before reuse" header."""
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serves every file in static/ under /static/. Mounted last so it cannot
# shadow the routes above.
app.mount("/static", FreshStaticFiles(directory=STATIC), name="static")

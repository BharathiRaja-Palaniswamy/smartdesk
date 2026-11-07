"""HTTP routes for the manage page and its reports.

  GET /manage               the manage page (static/dashboard/index.html)
  GET /api/report/options   what the filter row can offer (date range, dropdown values)
  GET /api/report           the full report for the chosen filters

The owner chat, POST /api/report/chat, is in smartdesk/owner/routes.py.

Example:  /api/report?start=2026-09-01&end=2026-09-30&category=Facials

The routes live in an APIRouter, a group of routes that app.py plugs in with
one line. That keeps these routes out of app.py.

All of them are the owner's: the data routes need the "reports" permission
(smartdesk/access/), so a request without the owner's sign-in gets 401, and
the page sends a visitor who has not signed in to /login.
"""

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from ..access.permissions import allowed
from ..access.session import require, role_of
from ..business.store import get_knowledge
from .dataset import get_dataset
from .report import build_report

PAGE = Path(__file__).resolve().parent.parent / "static" / "dashboard" / "index.html"

router = APIRouter(prefix="/api/report", dependencies=[Depends(require("reports"))])  # the data routes
page_router = APIRouter()  # the page itself, at /manage


@page_router.get("/manage", response_model=None)
def manage(request: Request) -> FileResponse | RedirectResponse:
    """The manage page: business profile and reports, as two tabs. Only for
    the signed-in owner; anyone else is sent to the sign-in page."""
    if not allowed(role_of(request), "reports"):
        return RedirectResponse("/login?next=/manage")
    # The page's CSS and JavaScript are served from /static/dashboard/ by app.py.
    return FileResponse(PAGE)


@router.get("/options")
def options() -> dict[str, Any]:
    """What the filter row can offer: business name, the date range the data
    covers, and the category and channel lists.
    """
    dataset = get_dataset()
    # The business name is a business fact, so it comes from the business document.
    return {"business": get_knowledge().name, "note": dataset.meta["description"], **dataset.filter_options()}


# FastAPI reads these arguments from the query string and converts them: `start`
# arrives as text and is turned into a date, or rejected with a 422 if it is not one.
@router.get("")
def report(
    start: date | None = None,
    end: date | None = None,
    category: str | None = None,
    channel: str | None = None,
) -> dict[str, Any]:
    """The full report for the chosen filters. Every filter is optional.
    Answers 422 when a filter is not valid.
    """
    dataset = get_dataset()
    available = dataset.filter_options()
    # A missing date means "from the first day" or "to the last day" of the data.
    start = start or date.fromisoformat(available["min_date"])
    end = end or date.fromisoformat(available["max_date"])

    if problem := dataset.filter_problem(start, end, category, channel):
        raise HTTPException(status_code=422, detail=problem)

    return build_report(dataset, start, end, category, channel)

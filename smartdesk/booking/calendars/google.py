"""The staff members' calendars in Google Calendar, through the Calendar API.

The app's only calendar (calendars/__init__.py). Each staff member has their own calendar,
named after SmartDesk, the business and the staff member ("SmartDesk · Test Studio – Dev
Patel"), so the calendars are found by name and nothing else needs to be configured, and
they never mix with calendars another app keeps for the same business on the same account.

When the app starts using Google Calendar, it creates the calendar of anyone
in the team who has none yet (someone who just joined). If
SMARTDESK_CALENDAR_OWNER names a Google account, each new calendar is shared
with it: that person sees all of them side by side in Google Calendar and
can add time off to any of them. Without it, the calendars work just the
same, but nobody can open them in Google Calendar. Someone who has left
the team keeps their calendar: no new bookings are offered with them, but
their bookings can still be found, listed and cancelled.

The app signs in as a service account: a Google account for a program, not
a person, with its own key (GOOGLE_SERVICE_ACCOUNT, the key file's JSON
text, or the path to the file). It owns the calendars it creates, so no
person has to sign in from the server.

How the Calendar interface (base.py) maps onto Google:
  busy      every event on the staff member's calendar, ours or not, so time
            off added by hand counts too; each event on its own (two events
            at the same times are two periods), skipping events marked "free"
  add       a new event, with our reference and the customer's details in
            its private properties, which the app searches by, and in its
            description, for whoever opens it in Google Calendar
  find      a search for the event whose private "reference" is the one given
  remove    deleting that event
  bookings  the events with our private "booked_by" mark, between two times

Any failure to reach Google (no key, a refused key, no network) is raised
as CalendarUnavailable (errors.py).
"""

import json
from datetime import date, datetime, time
from pathlib import Path
from collections.abc import Callable
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error

from ...business.store import get_knowledge, get_schedule
from ...config import get_settings
from ..errors import CalendarUnavailable
from .base import Booking

SCOPES = ["https://www.googleapis.com/auth/calendar"]  # read and write calendars
MARK = ("booked_by", "smartdesk")  # a private property on every event the app books
FAILURES = (HttpError, GoogleAuthError, HttpLib2Error, OSError, ValueError)


def calendar_name(business: str, staff_member: str) -> str:
    """The calendar a staff member's bookings go on: 'SmartDesk · Test Studio – Dev Patel'."""
    return f"SmartDesk · {business} – {staff_member}"


def connect() -> Any:
    """A Calendar API client signed in as the service account in GOOGLE_SERVICE_ACCOUNT."""
    key = get_settings().google_service_account.strip()
    if not key:
        raise CalendarUnavailable("GOOGLE_SERVICE_ACCOUNT is not set, so bookings cannot be kept. "
                                  "See docs/guides/google-calendar.md.")
    try:
        # The key file's JSON text (a host's secret), or the path to the file (on a laptop).
        info = json.loads(key if key.startswith("{") else Path(key).read_text(encoding="utf-8"))
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        return build("calendar", "v3", credentials=credentials, cache_discovery=False)
    except FAILURES as error:
        raise CalendarUnavailable(f"Could not read the Google service account key: {error}") from error


class CalendarGone(CalendarUnavailable):
    """A calendar the app knew is no longer there (deleted since): its list is read again."""


def run(request: Any) -> dict[str, Any]:
    """Send one prepared API request, turning any failure into CalendarUnavailable
    (CalendarGone when Google answers that the calendar is not there)."""
    try:
        return request.execute()
    except HttpError as error:
        if getattr(error.resp, "status", None) == 404:
            raise CalendarGone(f"A calendar is no longer there: {error}") from error
        raise CalendarUnavailable(f"Google Calendar could not be reached: {error}") from error
    except FAILURES as error:
        raise CalendarUnavailable(f"Google Calendar could not be reached: {error}") from error


def own_calendars(api: Any) -> dict[str, str]:
    """Every calendar the service account has, as name -> id."""
    calendars, page = {}, None
    while True:
        found = run(api.calendarList().list(pageToken=page))
        calendars |= {entry["summary"]: entry["id"] for entry in found.get("items", [])}
        if not (page := found.get("nextPageToken")):
            return calendars


def delete_bookings(api: Any, business: str) -> int:
    """Delete every booking on SmartDesk's calendars of `business` (onboarding reset),
    keeping the calendars, so they stay shared with the owner. Only calendars named
    "SmartDesk · <business> – <staff>": another app's calendars for the same business,
    on the same account, are never touched. Returns how many bookings were deleted."""
    prefix, deleted = calendar_name(business, ""), 0
    for name, cid in own_calendars(api).items():
        if not name.startswith(prefix):
            continue
        page = None
        while True:
            found = run(api.events().list(calendarId=cid, singleEvents=True, pageToken=page))
            for event in found.get("items", []):
                run(api.events().delete(calendarId=cid, eventId=event["id"]))
                deleted += 1
            if not (page := found.get("nextPageToken")):
                break
    return deleted


class GoogleCalendar:
    """A Calendar (see base.py) backed by one Google calendar per staff member."""

    def __init__(self, api: Any, calendars: dict[str, str], zone: ZoneInfo) -> None:
        """`calendars`: staff member name -> Google calendar id."""
        self.api, self.calendars, self.zone = api, calendars, zone

    def _run(self, request: Callable[[], Any]) -> dict[str, Any]:
        """Send the request `request()` prepares; when a calendar it names is gone (deleted
        since this list was read), read the calendars again (making any that are missing)
        and send it once more, so a stale list never stops a booking or a cancellation."""
        try:
            return run(request())
        except CalendarGone:
            self.calendars = ensure_calendars(self.api)[0]
            return run(request())

    def busy(self, staff_member: str, start: datetime, end: datetime) -> list[tuple[datetime, datetime]]:
        """Every event on the staff member's calendar between `start` and `end`, one period each.
        (Google's free/busy query would merge neighbouring events into one period, which
        could not tell a booking from another event right next to it.)"""
        events = self._events(staff_member, timeMin=start.isoformat(), timeMax=end.isoformat())
        return [(self._moment(event["start"]), self._moment(event["end"])) for _, event in events
                if event.get("transparency") != "transparent" and event.get("status") != "cancelled"]

    def add(self, booking: Booking) -> None:
        """A new event on the staff member's calendar."""
        zone = str(self.zone)
        self._run(lambda: self.api.events().insert(calendarId=self.calendars[booking.staff_member], body={
            "summary": f"{booking.service} – {booking.name}",
            "description": f"Booked through the business's site.\nReference: {booking.id}\nPhone: {booking.phone}"
                           + (f"\nAdd-ons: {', '.join(booking.add_ons)}" if booking.add_ons else ""),
            "start": {"dateTime": booking.start.isoformat(), "timeZone": zone},
            "end": {"dateTime": booking.end.isoformat(), "timeZone": zone},
            "extendedProperties": {"private": {
                MARK[0]: MARK[1], "reference": booking.id, "service": booking.service,
                "customer": booking.name, "phone": booking.phone,
                **({"package": booking.package} if booking.package else {}),
                **({"add_ons": "; ".join(booking.add_ons)} if booking.add_ons else {})}},
        }))

    def find(self, booking_id: str) -> Booking | None:
        """The booking with this reference, on whichever calendar it is."""
        return next(iter(self._search(privateExtendedProperty=f"reference={booking_id}")), None)

    def remove(self, booking_id: str) -> None:
        """Delete the event for this booking."""
        for staff_member, event in self._events(privateExtendedProperty=f"reference={booking_id}"):
            self._run(lambda who=staff_member, eid=event["id"]: self.api.events().delete(
                calendarId=self.calendars[who], eventId=eid))

    def bookings(self, start: datetime, end: datetime, staff_member: str | None = None) -> list[Booking]:
        """The app's bookings between `start` and `end`, earliest first."""
        found = self._search(staff_member, timeMin=start.isoformat(), timeMax=end.isoformat(),
                             privateExtendedProperty=f"{MARK[0]}={MARK[1]}")
        return sorted(found, key=lambda booking: booking.start)

    # ---- reading events ----------------------------------------------------

    def _events(self, staff_member: str | None = None, **query: str) -> list[tuple[str, dict[str, Any]]]:
        """(staff member, event) for every event matching `query`, on one calendar or all."""
        names = [staff_member] if staff_member else list(self.calendars)
        events = []
        for name in names:
            page = None
            while True:
                found = self._run(lambda who=name, at=page: self.api.events().list(
                    calendarId=self.calendars[who], singleEvents=True, pageToken=at, **query))
                events += [(name, event) for event in found.get("items", [])]
                if not (page := found.get("nextPageToken")):
                    break
        return events

    def _search(self, staff_member: str | None = None, **query: str) -> list[Booking]:
        """The bookings among the events matching `query`."""
        return [self._booking(name, event) for name, event in self._events(staff_member, **query)]

    def _booking(self, staff_member: str, event: dict[str, Any]) -> Booking:
        """A Booking from one of the app's events."""
        private = event["extendedProperties"]["private"]
        return Booking(private["reference"], private["service"], staff_member,
                       self._time(event["start"]["dateTime"]), self._time(event["end"]["dateTime"]),
                       private["customer"], private["phone"], private.get("package", ""),
                       tuple(a for a in private.get("add_ons", "").split("; ") if a))

    def _time(self, text: str) -> datetime:
        """A time from Google ('2026-10-23T17:00:00Z') in the business's time zone."""
        return datetime.fromisoformat(text).astimezone(self.zone)

    def _moment(self, when: dict[str, str]) -> datetime:
        """An event's start or end: a time ("dateTime"), or a whole day ("date", e.g. a day off) from midnight."""
        if "dateTime" in when:
            return self._time(when["dateTime"])
        return datetime.combine(date.fromisoformat(when["date"]), time(0), self.zone)


def share(api: Any, calendar: str, person: str) -> None:
    """Make `person` (a Google account) an owner of `calendar`: they see it,
    can add time off to it, and can share it with its staff member. Sharing
    again with the same person changes nothing."""
    run(api.acl().insert(calendarId=calendar, body={"role": "owner", "scope": {"type": "user", "value": person}}))


def ensure_calendars(api: Any) -> tuple[dict[str, str], list[str]]:
    """The business's calendars as staff member -> id, after creating any the team is
    missing (each shared with SMARTDESK_CALENDAR_OWNER, if set). Also returns
    the names of the staff members whose calendar was just created.

    Every calendar named after the business is included, the team's and those of
    people who have left, so no booking is lost when the team changes."""
    kb, settings = get_knowledge(), get_settings()
    prefix = calendar_name(kb.name, "")
    calendars = {name.removeprefix(prefix): cid for name, cid in own_calendars(api).items()
                 if name.startswith(prefix)}
    created = [person for person in get_schedule().staff_members if person not in calendars]
    for person in created:
        calendars[person] = run(api.calendars().insert(body={
            "summary": calendar_name(kb.name, person), "timeZone": settings.timezone}))["id"]
        if settings.calendar_owner:
            share(api, calendars[person], settings.calendar_owner)
    return calendars, created


def make_google() -> GoogleCalendar:
    """The business's Google calendars, one per staff member, created where missing."""
    api = connect()
    calendars, _ = ensure_calendars(api)
    return GoogleCalendar(api, calendars, ZoneInfo(get_settings().timezone))

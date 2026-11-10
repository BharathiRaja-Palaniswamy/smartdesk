"""Tests for the Google Calendar adapter (smartdesk/booking/calendars/google.py),
with a stand-in for Google's Calendar API: no account, no network.

The stand-in keeps calendars and their events and answers the requests the
adapter sends (calendar list, calendar insert, sharing, events insert, list
and delete), so the booking rules can run on it end to end,
including an event added by hand in Google Calendar (time off), which has
none of our marks.

Run with:  .venv/bin/python -m pytest tests/test_booking_google.py
"""

from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from googleapiclient.errors import HttpError

from smartdesk.frontdesk import agent, booking
from smartdesk.booking import actions
from smartdesk.booking.appointments import Appointments
from smartdesk.booking.calendars import google
from smartdesk.booking.calendars.google import GoogleCalendar, calendar_name
from smartdesk.booking.errors import CalendarUnavailable
from smartdesk.booking.schedule import read_schedule
from smartdesk.business.store import get_knowledge

SPA = ZoneInfo("America/Los_Angeles")
FRIDAY = date(2026, 10, 23)


def at(clock):
    hour, minute = map(int, clock.split(":"))
    return datetime(2026, 10, 23, hour, minute, tzinfo=SPA)


class Request:
    """A prepared request: runs when `execute()` is called, as Google's do."""

    def __init__(self, answer):
        self.answer = answer

    def execute(self):
        return self.answer() if callable(self.answer) else self.answer


class FakeApi:
    """Stands in for the Calendar API client, with calendars it already has."""

    def __init__(self, calendars: dict[str, str]):
        self.names = calendars  # name -> id
        self.stored: dict[str, list[dict]] = {cid: [] for cid in calendars.values()}
        self.fail = False
        self.shared: list[tuple[str, str]] = []  # (calendar id, person)

    # api.calendars().insert(body=...)
    def calendars(self):
        def insert(body):
            cid = f"cal-new-{len(self.names)}"
            self.names[body["summary"]] = cid
            self.stored[cid] = []
            return Request({"id": cid})
        return SimpleNamespace(insert=insert)

    # api.acl().insert(calendarId=..., body=...)
    def acl(self):
        def insert(calendarId, body):
            self.shared.append((calendarId, body["scope"]["value"]))
            return Request({})
        return SimpleNamespace(insert=insert)

    # api.calendarList().list(...)
    def calendarList(self):  # noqa: N802 (Google's own name)
        items = [{"summary": name, "id": cid} for name, cid in self.names.items()]
        return SimpleNamespace(list=lambda pageToken=None: Request({"items": items}))

    # api.events().insert / list / delete
    def events(self):
        def insert(calendarId, body):
            def run():
                if self.fail:
                    raise HttpError(SimpleNamespace(status=503, reason="Unavailable"), b"")
                self.stored[calendarId].append({**body, "id": f"event-{sum(map(len, self.stored.values()))}"})
                return {}
            return Request(run)

        def list_(calendarId, singleEvents, pageToken=None, timeMin=None, timeMax=None, privateExtendedProperty=None):
            if calendarId not in self.stored:  # deleted, or never there: Google answers 404
                def gone():
                    raise HttpError(SimpleNamespace(status=404, reason="Not Found"), b"")
                return Request(gone)
            key, _, value = (privateExtendedProperty or "").partition("=")
            found = self.stored[calendarId]
            if timeMin:
                found = self._overlapping(calendarId, datetime.fromisoformat(timeMin), datetime.fromisoformat(timeMax))
            if key:
                found = [e for e in found if e.get("extendedProperties", {}).get("private", {}).get(key) == value]

            def run():
                if self.fail:
                    raise HttpError(SimpleNamespace(status=503, reason="Unavailable"), b"")
                return {"items": found}
            return Request(run)

        def delete(calendarId, eventId):
            return Request(lambda: self.stored[calendarId].remove(
                next(e for e in self.stored[calendarId] if e["id"] == eventId)))
        return SimpleNamespace(insert=insert, list=list_, delete=delete)

    def _overlapping(self, calendar, start, end):
        return [e for e in self.stored[calendar] if moment(e["start"]) < end and moment(e["end"]) > start]


def moment(when: dict) -> datetime:
    """An event's start or end as Google writes it: a time, or a whole day (from midnight at the business)."""
    if "dateTime" in when:
        return datetime.fromisoformat(when["dateTime"])
    return datetime.combine(date.fromisoformat(when["date"]), datetime.min.time(), SPA)


def team() -> list[str]:
    """The test business's staff, read when a test runs (its own business folder, conftest.py)."""
    return list(read_schedule(get_knowledge()).staff_members)


@pytest.fixture
def api():
    return FakeApi({calendar_name("Test Studio", name): f"cal-{n}" for n, name in enumerate(team())})


@pytest.fixture
def desk(api):
    calendar = GoogleCalendar(api, {name: f"cal-{n}" for n, name in enumerate(team())}, SPA)
    return Appointments(read_schedule(get_knowledge()), calendar, SPA, 30,
                        now=lambda: datetime(2026, 10, 22, 14, 10, tzinfo=SPA))


def dev(api):
    return api.stored[f"cal-{team().index('Dev Patel')}"]


def test_a_booking_becomes_an_event_on_the_staff_members_own_calendar(api, desk):
    booking = desk.book("Prenatal Massage", "Dev Patel", at("10:00"), "Asha", "(408) 555-0101")
    [event] = dev(api)
    assert event["summary"] == "Prenatal Massage – Asha"
    assert event["start"] == {"dateTime": "2026-10-23T10:00:00-07:00", "timeZone": "America/Los_Angeles"}
    assert event["extendedProperties"]["private"]["reference"] == booking.id


def test_bookings_read_back_as_they_were_made_and_can_be_cancelled(api, desk):
    booking = desk.book("Prenatal Massage", "Dev Patel", at("10:00"), "Asha", "(408) 555-0101")
    assert desk.day_bookings(FRIDAY) == [booking]
    assert desk.cancel(booking.id, "4085550101") == booking
    assert dev(api) == [] and desk.day_bookings(FRIDAY) == []


def test_a_bookings_package_and_add_ons_are_kept_on_its_event(api, desk):
    booking = desk.book("Prenatal Massage", "Dev Patel", at("10:00"), "Asha", "(408) 555-0101",
                        package="Parent & Child Package", add_ons=("Scalp massage",))
    found = desk.calendar.find(booking.id)
    assert (found.package, found.add_ons) == ("Parent & Child Package", ("Scalp massage",))
    [event] = [e for events in api.stored.values() for e in events]
    assert "Add-ons: Scalp massage" in event["description"]  # what the staff see in Google Calendar


def test_time_off_added_in_google_calendar_blocks_those_times_but_is_not_a_booking(api, desk):
    # The owner adds "Dev – dentist" from 12:00 to 14:00 directly in Google Calendar.
    dev(api).append({"id": "by-hand", "summary": "Dev – dentist",
                       "start": {"dateTime": at("12:00").isoformat()}, "end": {"dateTime": at("14:00").isoformat()}})
    offered = [s.start.strftime("%H:%M") for s in desk.free_slots("Prenatal Massage", FRIDAY)]
    assert "11:00" in offered and "11:30" not in offered and "13:30" not in offered and "14:00" in offered
    assert desk.day_bookings(FRIDAY) == []


def test_google_failing_is_reported_as_calendar_unavailable_and_the_tool_says_so(api, desk, monkeypatch):
    api.fail = True
    with pytest.raises(CalendarUnavailable, match="could not be reached"):
        desk.book("Prenatal Massage", "Dev Patel", at("10:00"), "Asha", "(408) 555-0101")
    # Through the tool, the model gets a message it can pass on, not the reason.
    for module in (agent, booking):
        monkeypatch.setattr(module, "get_appointments", lambda: desk)
    ask = next(t for t in agent.agent_tools("Asha", "4085550101", words="prenatal friday") if t.name == "booking")
    reply = ask.run({"intent": "availability", "services": ["Prenatal Massage"], "day_said": "friday"})
    assert reply == {"error": actions.UNAVAILABLE}


def test_someone_new_in_the_team_gets_a_calendar_shared_with_the_owner(api, monkeypatch):
    del api.names[calendar_name("Test Studio", "Fay Kim")]  # as if Fay just joined
    monkeypatch.setattr(google, "connect", lambda: api)
    monkeypatch.setenv("SMARTDESK_CALENDAR_OWNER", "owner@example.com")
    calendar = google.make_google()
    new = api.names[calendar_name("Test Studio", "Fay Kim")]
    assert calendar.calendars["Fay Kim"] == new and api.shared == [(new, "owner@example.com")]


def test_bookings_with_someone_who_left_the_team_are_still_found(api, monkeypatch):
    # A calendar named after the business, for someone no longer in the document.
    api.names[calendar_name("Test Studio", "Ana Former")] = "cal-gone"
    api.stored["cal-gone"] = [{"id": "e1", "start": {"dateTime": at("10:00").isoformat()},
                               "end": {"dateTime": at("11:00").isoformat()},
                               "extendedProperties": {"private": {
                                   "booked_by": "smartdesk", "reference": "BK-OLD001", "service": "Lip Wax",
                                   "customer": "Ben", "phone": "4085550102"}}}]
    monkeypatch.setattr(google, "connect", lambda: api)
    calendar = google.make_google()
    assert calendar.find("BK-OLD001").staff_member == "Ana Former"
    assert [b.id for b in calendar.bookings(at("00:00"), at("23:59"))] == ["BK-OLD001"]


def test_without_a_key_the_error_says_what_to_do(monkeypatch):
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT", "")
    with pytest.raises(CalendarUnavailable, match="GOOGLE_SERVICE_ACCOUNT is not set"):
        google.connect()


def test_there_is_no_other_place_for_bookings_without_google(monkeypatch):
    # Without the key, booking is unavailable: nothing is quietly kept somewhere else.
    from smartdesk.booking.calendars import get_calendar
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT", "")
    get_calendar.cache_clear()
    with pytest.raises(CalendarUnavailable, match="GOOGLE_SERVICE_ACCOUNT is not set"):
        get_calendar()
    get_calendar.cache_clear()


def test_a_day_off_blocks_the_day_and_an_event_marked_free_does_not(api, desk):
    dev(api).append({"id": "off", "summary": "Dev – day off", "start": {"date": "2026-10-23"},
                       "end": {"date": "2026-10-24"}})
    assert desk.free_slots("Prenatal Massage", FRIDAY) == []
    dev(api).clear()
    dev(api).append({"id": "note", "summary": "Reminder", "transparency": "transparent",
                       "start": {"dateTime": at("10:00").isoformat()}, "end": {"dateTime": at("11:00").isoformat()}})
    assert "10:00" in [s.start.strftime("%H:%M") for s in desk.free_slots("Prenatal Massage", FRIDAY)]



def test_reset_deletes_this_business_s_bookings_and_keeps_its_calendars():
    from smartdesk.booking.calendars.google import delete_bookings

    api = FakeApi({calendar_name("Test Studio", "Dev Patel"): "cal-1",
                   "Test Studio – Dev Patel": "cal-other-app",  # another app's calendar for the same business
                   calendar_name("Another Studio", "Jo Lin"): "cal-other-business"})
    for cid in api.stored:
        api.stored[cid].append({"id": f"event-{cid}", "summary": "a booking"})
    assert delete_bookings(api, "Test Studio") == 1
    assert api.stored["cal-1"] == [] and calendar_name("Test Studio", "Dev Patel") in api.names  # kept, empty
    assert api.stored["cal-other-app"] and api.stored["cal-other-business"]  # untouched



def test_a_calendar_deleted_since_is_read_again_not_a_failure():
    # As seen live: the server kept a staff calendar id deleted since, and every lookup of the
    # customer's bookings failed ("Not Found"), so a cancellation could not be done.
    api = FakeApi({calendar_name("Test Studio", name): f"cal-{n}" for n, name in enumerate(team())})
    stale = {name: f"cal-{n}" for n, name in enumerate(team())} | {"Dev Patel": "cal-deleted"}
    calendar = GoogleCalendar(api, stale, SPA)
    assert calendar.bookings(datetime(2026, 10, 23, tzinfo=SPA), datetime(2026, 10, 24, tzinfo=SPA)) == []
    assert calendar.calendars["Dev Patel"] != "cal-deleted"  # the list was read again

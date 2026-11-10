"""Tests for slot recovery, the empty chair (smartdesk/waitlist/).

The booking rules run over the test business and an in-memory calendar with a
fixed clock (standin_calendar.py); the waitlist and offers live in a folder of
the test's own. No model is called.

Run with:  .venv/bin/python -m pytest tests/test_waitlist.py
"""

from datetime import date, datetime, time, timedelta

import pytest
from standin_calendar import NOW, SPA, standin_desk

from smartdesk.frontdesk import executor
from smartdesk.waitlist import recovery
from smartdesk.waitlist.store import load

FRIDAY = date(2026, 10, 23)
THREE_PM = datetime(2026, 10, 23, 15, 0, tzinfo=SPA)
ASHA, BEN, CARA = "(555) 010-0001", "(555) 010-0002", "(555) 010-0003"


@pytest.fixture
def desk(tmp_path, monkeypatch):
    """One calendar for the whole test, a fixed clock, and the test's own folder."""
    monkeypatch.setenv("SMARTDESK_BUSINESS_FOLDER", str(tmp_path))
    the_desk = standin_desk()
    monkeypatch.setattr(executor, "get_appointments", lambda: the_desk)
    monkeypatch.setattr(recovery, "get_appointments", lambda: the_desk)
    monkeypatch.setattr(recovery, "_now", lambda: NOW)
    return the_desk


def booked_and_cancelled(desk) -> None:
    """Asha books Friday 3 pm with Dev, then cancels it: the slot opens."""
    reference = desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Asha", ASHA).id
    executor.cancel([reference], ASHA)


def test_a_cancelled_slot_is_offered_to_the_earliest_matching_waiter_only(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offers = load("offers")
    assert [(o["name"], o["start"], o["status"]) for o in offers] == [("Ben", THREE_PM.isoformat(), "open")]
    assert recovery.open_for(CARA) is None


def test_a_waiter_for_another_service_day_or_window_is_not_offered(desk):
    recovery.join("Ben", BEN, "Swedish Massage", FRIDAY)  # another service
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY, before=time(12, 0))  # mornings only
    booked_and_cancelled(desk)
    assert load("offers") == []


def test_one_exact_time_is_a_window_from_and_to_that_time(desk):
    # As seen with the real model: "only 3pm" became after 15:00, before 15:00.
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY, after=time(15, 0), before=time(15, 0))
    booked_and_cancelled(desk)
    assert recovery.open_for(BEN)["start"] == THREE_PM.isoformat()


def test_yes_books_exactly_the_offered_slot(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offer = recovery.open_for(BEN)
    result = recovery.answer(offer["id"], BEN, accept=True)
    assert [b["staff_member"] for b in result["booked"]] == ["Dev Patel"]
    [booking] = desk.calendar.bookings(THREE_PM, THREE_PM + timedelta(hours=1))
    assert (booking.name, booking.phone, booking.start) == ("Ben", BEN, THREE_PM)
    assert load("waitlist")[0]["status"] == "booked"


def test_no_offers_the_slot_to_the_next_waiter(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    assert recovery.answer(recovery.open_for(BEN)["id"], BEN, accept=False) == {"declined": True}
    assert recovery.open_for(CARA)["start"] == THREE_PM.isoformat()
    assert recovery.open_for(BEN) is None  # never offered that slot again


def test_an_offer_not_answered_in_time_goes_to_the_next_waiter(desk, monkeypatch):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    expires = datetime.fromisoformat(recovery.open_for(BEN)["expires_at"])
    monkeypatch.setattr(recovery, "_now", lambda: expires + timedelta(seconds=1))
    assert recovery.open_for(BEN) is None
    assert recovery.open_for(CARA) is not None


def test_a_slot_taken_meanwhile_is_not_booked_on_yes(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Walk-in", "(555) 010-0009")  # taken at the desk
    result = recovery.answer(recovery.open_for(BEN)["id"], BEN, accept=True)
    assert "could not be booked" in result["error"]


def test_only_the_offered_customer_can_answer_it(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offer = recovery.open_for(BEN)
    assert "no open offer" in recovery.answer(offer["id"], CARA, accept=True)["error"]


def test_the_widget_is_shown_its_customers_offer_once_and_the_agent_hears_of_it(desk, monkeypatch):
    from fastapi.testclient import TestClient

    from smartdesk import frontdesk
    from smartdesk.app import app
    from smartdesk.waitlist import routes

    told = []
    monkeypatch.setattr(routes, "customer_phone", lambda thread: BEN if thread == "ben-chat-1" else "")
    monkeypatch.setattr(routes, "tell", lambda thread, text: told.append((thread, text)))
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    client = TestClient(app)
    first = client.get("/api/widget/offer", params={"thread": "ben-chat-1"}).json()
    assert first["text"].startswith("Good news, Ben: a Prenatal Massage with Dev Patel on Friday 23 October at 3 PM")
    assert first["suggestions"] == ["Yes, book it", "No, thanks"]
    assert told == [("ben-chat-1", first["text"])]  # written into Ben's conversation
    assert client.get("/api/widget/offer", params={"thread": "ben-chat-1"}).json() is None  # shown once
    assert client.get("/api/widget/offer", params={"thread": "someone-else"}).json() is None
    assert frontdesk.customer_phone  # the real lookup exists


def test_a_yes_result_reads_like_any_booking_result(desk):
    # As seen live: the debug note and the agent read "booked" as a list of bookings.
    from smartdesk.frontdesk.debug import outcome

    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    result = recovery.answer(recovery.open_for(BEN)["id"], BEN, accept=True)
    assert outcome(result).startswith("booked BK-")



# ---- who is offered, and for how long (choose.py, D34) -------------------------------------------

def waiter(name: str, after: str = "", before: str = "", joined: str = "09:00", phone: str = "") -> dict:
    return {"id": f"WL-{name}", "name": name, "phone": phone or f"408 555 01{len(name):02d}", "after": after,
            "before": before, "joined_at": f"2026-11-10T{joined}:00-08:00"}


def test_who_asked_for_exactly_that_time_comes_first_then_the_narrower_window_then_any_time():
    from smartdesk.waitlist.choose import rank

    anytime = waiter("Ann", joined="08:00")  # joined first, but wanted any time
    window = waiter("Bo", "13:00", "17:00", joined="08:30")
    narrow = waiter("Cy", "15:00", "16:00", joined="09:00")
    exact = waiter("Di", "15:00", "15:00", joined="09:30")
    assert [w["name"] for w in rank([anytime, window, narrow, exact], [])] == ["Di", "Cy", "Bo", "Ann"]


def test_a_customer_who_let_offers_run_out_comes_after_one_who_did_not():
    from smartdesk.waitlist.choose import rank

    first = waiter("Ann", "15:00", "15:00", joined="08:00", phone="408 555 0111")
    second = waiter("Bo", "15:00", "15:00", joined="09:00", phone="408 555 0122")
    missed = [{"status": "expired", "phone": "(408) 555-0111"}, {"status": "declined", "phone": "408 555 0122"}]
    assert [w["name"] for w in rank([first, second], missed)] == ["Bo", "Ann"]  # saying no is fine
    assert [w["name"] for w in rank([first, second], [])] == ["Ann", "Bo"]  # otherwise who waited longest


@pytest.mark.parametrize("ahead, held", [
    (timedelta(days=2), 60),      # far off: the longest hold
    (timedelta(hours=2), 10),     # two hours ahead: a twelfth of it
    (timedelta(minutes=50), 5),   # near: the shortest hold, so several can be asked before it starts
    (timedelta(minutes=37), 5),   # and never past the minimum notice (30 minutes) before it starts
    (timedelta(minutes=33), None),  # too near to answer and still arrive: offered to nobody
])
def test_the_hold_follows_how_soon_the_slot_is(ahead, held):
    from smartdesk.waitlist.choose import hold

    now = datetime(2026, 11, 10, 9, 0)
    found = hold(now + ahead, now)
    assert (found and found.total_seconds() / 60) == held


def test_a_cancelled_slot_goes_to_who_wanted_exactly_that_time_before_an_earlier_any_time_waiter(desk):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)  # first, any time
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY, time(15, 0), time(15, 0))  # later, 3 pm only
    booked_and_cancelled(desk)
    assert recovery.open_for(CARA) is not None and recovery.open_for(BEN) is None



# ---- the keypad call to the customer offered a slot (calls.py, D39) ------------------------------

class StandInTwilio:
    """Records the calls asked for, and answers as Twilio does; never phones anyone."""

    def __init__(self):
        self.calls = []

    def post(self, url, data=None, auth=None, timeout=None, **kwargs):
        import httpx

        self.calls.append(data)
        return httpx.Response(201, json={"sid": f"CA{len(self.calls)}"}, request=httpx.Request("POST", url))


@pytest.fixture
def calls(monkeypatch):
    """Twilio set up and stood in for, the business open and with its line; calls placed at once."""
    from smartdesk.onboarding import store
    from smartdesk.onboarding.phone import Line
    from smartdesk.waitlist import calls as module

    for name, value in {"TWILIO_ACCOUNT_SID": "AC_test", "TWILIO_AUTH_TOKEN": "token",
                        "SMARTDESK_PUBLIC_URL": "https://desk.example"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(store, "live_phone", lambda: Line("+14085550100", agent_id="agent_test"))
    standin = StandInTwilio()
    monkeypatch.setattr(module.httpx, "post", standin.post)
    monkeypatch.setattr(module, "open_now", lambda now: True)
    monkeypatch.setattr(module.threading, "Thread",
                        lambda target, args, **kwargs: type("Now", (), {"start": lambda self: target(*args)})())
    return standin


def keypad(offer: dict, digits: str, key: str = ""):
    """What Twilio sends back when the customer presses `digits` on the call about `offer`."""
    from fastapi.testclient import TestClient

    from smartdesk.app import app

    return TestClient(app).post(f"/api/waitlist/answer/{offer['id']}", params={"key": key or offer["key"]},
                                data={"Digits": digits})


def test_when_a_slot_opens_the_customer_is_called_to_press_1_or_2(desk, calls):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    [call] = calls.calls
    offer = recovery.open_for(BEN)
    assert call["To"] == "+15550100002" and call["From"] == "+14085550100"  # from the business's own number
    assert ("Hi Ben! It's Test Studio, with good news. The Prenatal Massage you asked for, on Friday 23 October "
            "at 3 PM, just opened up. To book it, press 1. If you'd rather not, press 2.") in call["Twiml"]
    assert '<Say voice="Polly.Joanna-Neural">' in call["Twiml"]  # a natural voice, not the flat default
    assert f"/api/waitlist/answer/{offer['id']}?key={offer['key']}" in call["Twiml"]
    assert desk.day_bookings(FRIDAY) == []  # nothing booked before they press 1


def test_pressing_1_books_exactly_the_slot_offered(desk, calls):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    reply = keypad(recovery.open_for(BEN), "1")
    assert reply.headers["content-type"].startswith("application/xml")
    assert "you're booked! Prenatal Massage with Dev Patel on Friday 23 October at 3 PM" in reply.text
    [booking] = desk.day_bookings(FRIDAY)
    assert (booking.name, f"{booking.start:%H:%M}") == ("Ben", "15:00")


def test_pressing_2_lets_it_go_and_the_next_customer_is_called(desk, calls):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    assert "offer it to someone else" in keypad(recovery.open_for(BEN), "2").text
    assert desk.day_bookings(FRIDAY) == [] and recovery.open_for(CARA) is not None
    assert [c["To"] for c in calls.calls] == ["+15550100002", "+15550100003"]  # Ben, then Cara


def test_only_the_offers_own_call_can_answer_it_and_no_key_asks_again(desk, calls):
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    offer = recovery.open_for(BEN)
    assert "this offer has ended" in keypad(offer, "1", key="guessed").text
    assert desk.day_bookings(FRIDAY) == []  # a wrong key books nothing
    assert "press 1" in keypad(offer, "").text  # nothing pressed: asked once more


def test_no_call_outside_opening_hours_or_without_twilio(desk, calls, monkeypatch):
    from smartdesk.waitlist import calls as module

    monkeypatch.setattr(module, "open_now", lambda now: False)  # closed: the offer waits
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    assert calls.calls == [] and recovery.open_for(BEN) is not None
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    assert module.place(recovery.open_for(BEN)) is None and calls.calls == []


def test_a_failed_call_leaves_the_offer_open(desk, calls, monkeypatch):
    import httpx

    from smartdesk.waitlist import calls as module

    def down(*args, **kwargs):
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(module.httpx, "post", down)
    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY)
    booked_and_cancelled(desk)
    assert recovery.open_for(BEN) is not None


@pytest.mark.parametrize("phone, dialled", [("(408) 555-0101", "+14085550101"), ("1 408 555 0101", "+14085550101"),
                                            ("+44 20 7946 0958", "+442079460958"), ("555-0101", None)])
def test_a_number_is_dialled_only_when_it_is_a_whole_one(phone, dialled):
    from smartdesk.onboarding.phone import dialable

    assert dialable(phone) == dialled



def test_a_waiter_who_cannot_be_reached_is_not_offered_the_slot(desk):
    # As seen live: an entry from before numbers were checked ("1283739") was offered the slot first,
    # so nobody was called; the customer after them was waiting behind an unreachable one.
    recovery.join("B", "1283739", "Prenatal Massage", FRIDAY, time(15, 0), time(15, 0))
    recovery.join("Cara", CARA, "Prenatal Massage", FRIDAY, time(15, 0), time(15, 0))
    booked_and_cancelled(desk)
    assert recovery.open_for(CARA) is not None and recovery.open_for("1283739") is None



def test_calls_can_be_allowed_at_any_hour_for_testing(monkeypatch):
    from datetime import datetime

    from smartdesk.waitlist.calls import open_now

    midnight = datetime(2026, 10, 23, 0, 30)  # closed
    assert not open_now(midnight)
    monkeypatch.setenv("SMARTDESK_CALL_ANY_TIME", "true")
    assert open_now(midnight)



def test_moving_a_booking_offers_its_old_time_to_the_waitlist(desk):
    from smartdesk.frontdesk.booking import Plan, PlanItem
    from smartdesk.frontdesk.executor import execute

    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY, time(15, 0), time(15, 0))
    old = desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Asha", ASHA)
    later = Plan(items=[PlanItem(service="Prenatal Massage", staff_member="Dev Patel",
                                 start=THREE_PM.replace(hour=17, tzinfo=None))], summary="moved")
    assert execute(later, "Asha", ASHA, desk, replaces=old.id).booked
    assert recovery.open_for(BEN) is not None  # the 15:00 Asha moved from is offered to Ben


def test_a_change_at_the_same_time_offers_nothing(desk):
    from smartdesk.frontdesk.booking import Plan, PlanItem
    from smartdesk.frontdesk.executor import execute

    recovery.join("Ben", BEN, "Prenatal Massage", FRIDAY, time(15, 0), time(15, 0))
    old = desk.book("Prenatal Massage", "Dev Patel", THREE_PM, "Asha", ASHA)
    same = Plan(items=[PlanItem(service="Prenatal Massage", staff_member="Dev Patel",
                                start=THREE_PM.replace(tzinfo=None))], summary="with an extra", add_ons=["Scalp massage"])
    assert execute(same, "Asha", ASHA, desk, replaces=old.id).booked
    assert recovery.open_for(BEN) is None  # 15:00 is still Asha's: nothing to offer

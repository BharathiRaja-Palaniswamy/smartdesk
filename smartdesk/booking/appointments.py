"""The booking rules: free times, booking, cancelling, and the day's schedule.

    free time = the business's opening hours on that day
              - (staff member not working that day)
              - the classes they teach (an instructor's timetable)
              - whatever is on their calendar (bookings, time off)
              - times less than SMARTDESK_MIN_NOTICE_MINUTES from now (or past)

These rules are ours, which is why the app talks to the calendar through its
own interface (calendars/) rather than handing a model the calendar itself:
a booking can only be made in a free time, with a staff member who offers the
service, and a customer can only cancel a booking whose phone number they
know, and not once it is less than SMARTDESK_MIN_NOTICE_MINUTES away (they
call the business instead). The agent (in the chat and on the phone) asks through actions.py, and
every request is checked here.

Times are in the business's time zone (SMARTDESK_TIMEZONE). Appointments start on a
grid, every SMARTDESK_SLOT_MINUTES from opening, and must end by closing time.
"""

import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..business.store import get_schedule
from ..config import get_settings
from .calendars import Booking, Calendar, get_calendar
from .errors import BookingError
from .schedule import Schedule, Service, StaffMember


@dataclass(frozen=True)
class Slot:
    """A time a staff member is free for the whole service."""

    staff_member: str
    start: datetime
    end: datetime


def digits(phone: str) -> str:
    """'(408) 555-0188' -> '4085550188', so two ways of writing a number compare equal."""
    return re.sub(r"\D", "", phone)


class Appointments:
    """Books appointments on a calendar, following the schedule in the document."""

    def __init__(self, schedule: Schedule, calendar: Calendar, zone: ZoneInfo, step: int, notice: int = 0,
                 now: Callable[[], datetime] | None = None) -> None:
        """`step`: minutes between possible start times. `notice`: the fewest
        minutes ahead a booking can be made, changed or cancelled. `now` gives
        the current time; tests pass a fixed one."""
        self.schedule, self.calendar, self.zone = schedule, calendar, zone
        self.step, self.notice = timedelta(minutes=step), timedelta(minutes=notice)
        self._now = now or (lambda: datetime.now(zone))

    def now(self) -> datetime:
        """The current time in the business's zone (fixed, in tests)."""
        return self._now()

    # ---- what the customer can ask -----------------------------------------

    def free_slots(self, service: str, day: date, staff_member: str | None = None,
                   minutes: int | None = None, ignoring: Booking | None = None) -> list[Slot]:
        """Every free time on `day` for `service` (of length `minutes`, its
        standard length if not given), with `staff member` or anyone who offers
        it. Earliest first. `ignoring`: a booking whose time counts as free,
        the one a change replaces (it is cancelled once the new one is made)."""
        chosen = self._service(service)
        length = timedelta(minutes=self._length(chosen, minutes))
        slots = [slot for person in self._staff_members(chosen, staff_member)
                 for slot in self._free_for(person, day, length, ignoring)]
        return sorted(slots, key=lambda slot: (slot.start, slot.staff_member))

    def book(self, service: str, staff_member: str, start: datetime, name: str, phone: str,
             minutes: int | None = None, ignoring: Booking | None = None, package: str = "",
             add_ons: tuple[str, ...] = ()) -> Booking:
        """Book `service` with `staff member` at `start`, if that time is free
        (`ignoring` a booking this one replaces), as part of `package` if any,
        with any `add_ons`.
        A time with no time zone is taken as the business's."""
        if not name.strip():
            raise BookingError("Please give the name the booking is for.")
        if len(digits(phone)) < 7:
            raise BookingError("Please give a phone number the business can reach you on.")
        start = start.astimezone(self.zone) if start.tzinfo else start.replace(tzinfo=self.zone)
        free = self.free_slots(service, start.date(), staff_member, minutes, ignoring)
        slot = next((s for s in free if s.start == start), None)
        if slot is None:
            raise BookingError(f"{staff_member} is not free for {service} at that time. Please choose a free time.")
        # The check and the booking are two steps: two customers booking the
        # same time at the same moment could both pass the check. That is rare
        # for one small business; a busier one would lock the time first.
        booking = Booking("BK-" + secrets.token_hex(3).upper(), service, staff_member, slot.start, slot.end,
                          name.strip(), phone.strip(), package, tuple(add_ons))
        self.calendar.add(booking)
        return booking

    def cancel(self, booking_id: str, phone: str) -> Booking:
        """Cancel a booking, given its reference and the phone number it was
        booked with, if it is at least `notice` away. The rest of the
        cancellation policy (fees) is left to the business."""
        booking = self.check_cancel(booking_id, phone)
        self.calendar.remove(booking.id)
        return booking

    def check_cancel(self, booking_id: str, phone: str) -> Booking:
        """The booking `cancel` would cancel, without cancelling it: raises
        BookingError if it may not be cancelled. Lets a caller show the
        booking and ask "are you sure?" first."""
        booking = self.calendar.find(booking_id.strip().upper())
        # The same answer whether the reference or the phone number is wrong,
        # so nobody can find out which bookings exist by guessing.
        if booking is None or digits(booking.phone) != digits(phone):
            raise BookingError("No booking matches that reference and phone number.")
        if booking.start - self._now() < self.notice:
            minutes = int(self.notice.total_seconds() // 60)
            raise BookingError(f"That appointment is less than {minutes} minutes away, so it can't be changed "
                               "or cancelled here. Please call the business.")
        return booking

    def upcoming(self, phone: str, days: int = 60) -> list[Booking]:
        """The bookings made with this phone number in the next `days` days, earliest first."""
        now = self._now()
        return [b for b in self.calendar.bookings(now, now + timedelta(days=days)) if digits(b.phone) == digits(phone)]

    # ---- for the owner only ------------------------------------------------

    def day_bookings(self, day: date, staff_member: str | None = None) -> list[Booking]:
        """Every booking on `day`, earliest first, with the customers' details."""
        if staff_member is not None:
            self._staff_member(staff_member)
        start = datetime.combine(day, time(0), self.zone)
        return self.calendar.bookings(start, start + timedelta(days=1), staff_member)

    # ---- checks ------------------------------------------------------------

    def _service(self, name: str) -> Service:
        """The bookable service called `name`."""
        if name not in self.schedule.services:
            raise BookingError(f"{name!r} is not a service that can be booked here. "
                               f"Choose one of: {', '.join(self.schedule.services)}.")
        return self.schedule.services[name]

    def _length(self, service: Service, minutes: int | None) -> int:
        """`minutes` if the service comes in that length, its standard length if None."""
        if minutes is None:
            return service.minutes[0]
        if minutes not in service.minutes:
            lengths = " or ".join(str(m) for m in service.minutes)
            raise BookingError(f"{service.name} is {lengths} minutes long.")
        return minutes

    def _staff_member(self, name: str) -> StaffMember:
        """The team member called `name`."""
        if name not in self.schedule.staff_members:
            raise BookingError(f"{name!r} is not on the team. The team: {', '.join(self.schedule.staff_members)}.")
        return self.schedule.staff_members[name]

    def _staff_members(self, service: Service, name: str | None) -> list[StaffMember]:
        """`name` if they offer the service; everyone who does if `name` is None."""
        if name is None:
            return self.schedule.staff_members_for(service.name)
        person = self._staff_member(name)
        if service.name not in person.services:
            others = ", ".join(t.name for t in self.schedule.staff_members_for(service.name))
            raise BookingError(f"{name} does not offer {service.name}. It is offered by: {others}.")
        return [person]

    # ---- free time -----------------------------------------------------------

    def _free_for(self, person: StaffMember, day: date, length: timedelta,
                  ignoring: Booking | None = None) -> list[Slot]:
        """The free start times for one staff member on one day, with `ignoring`'s time counted as free."""
        hours = self.schedule.hours.get(day.weekday())
        if hours is None or day.weekday() not in person.days:
            return []
        opens, closes = (datetime.combine(day, t, self.zone) for t in hours)
        busy = self.calendar.busy(person.name, opens, closes) + self._teaching(person, day)
        if ignoring and ignoring.staff_member == person.name and (ignoring.start, ignoring.end) in busy:
            busy.remove((ignoring.start, ignoring.end))  # one copy: anything else at that time still counts
        earliest, slots, start = self._now() + self.notice, [], opens
        while start + length <= closes:
            end = start + length
            if start >= earliest and all(end <= b_start or start >= b_end for b_start, b_end in busy):
                slots.append(Slot(person.name, start, end))
            start += self.step
        return slots

    def _teaching(self, person: StaffMember, day: date) -> list[tuple[datetime, datetime]]:
        """The times `person` teaches a class on `day`, from the timetable."""
        periods = []
        for lesson in self.schedule.lessons:
            if lesson.teacher == person.name and lesson.day == day.weekday():
                start = datetime.combine(day, lesson.start, self.zone)
                periods.append((start, start + timedelta(minutes=lesson.minutes)))
        return periods


def get_appointments() -> Appointments:
    """The booking rules over the current document and the configured calendar."""
    settings = get_settings()
    return Appointments(get_schedule(), get_calendar(), ZoneInfo(settings.timezone),
                        settings.slot_minutes, settings.min_notice_minutes)

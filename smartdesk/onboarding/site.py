"""What the owner's preview website shows (D33): the business's own facts, nothing made up.

The preview stands in for the business's website, so it shows what a real one would:
its services with lengths and prices, its team, its opening hours and how to reach it.
Everything comes from what onboarding read (the schedule and the document), so the same
page looks right for a spa, a barbershop or a studio, and never names another business.
"""

from pydantic import BaseModel

from ..business.store import get_knowledge, get_schedule
from ..frontdesk.booking import twelve
from .phone import shown
from .store import live_phone

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


class Offer(BaseModel):
    name: str
    category: str
    detail: str  # "60 or 90 min"
    price: str  # "$115 / $160"


class Hours(BaseModel):
    day: str
    time: str  # "9 AM – 8 PM", or "Closed"


class Site(BaseModel):
    name: str
    services: list[Offer]
    team: list[str]
    hours: list[Hours]
    phone: str
    email: str
    address: str


def site() -> Site:
    """The business's website content, read from its live schedule and document."""
    schedule, facts, line = get_schedule(), get_knowledge().facts, live_phone()
    services = [Offer(name=s.name, category=s.category or "",
                      detail=" or ".join(str(m) for m in s.minutes) + " min",
                      price=" / ".join(f"${p}" for p in s.prices))
                for s in schedule.services.values()]
    def open_(day: int) -> str:
        if day not in schedule.hours:
            return "Closed"
        opens, closes = schedule.hours[day]
        return f"{twelve(opens)} – {twelve(closes)}"

    hours = [Hours(day=name, time=open_(day)) for day, name in enumerate(DAYS)]
    return Site(name=get_knowledge().name, services=services,
                team=[person.name for person in schedule.staff_members.values()],
                hours=hours,
                phone=shown(line.number) if line else facts.get("Phone", ""),  # the number its assistant answers
                email=facts.get("Email", ""), address=facts.get("Address", ""))

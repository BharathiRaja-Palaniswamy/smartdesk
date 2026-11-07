"""Create the staff members' Google calendars, and share them with the owner.

    .venv/bin/python -m scripts.setup_calendars

One calendar per member of the team in the business document, named after
the business and the staff member ("Test Studio – Dev Patel"), in the business's time
zone. The app does the same by itself when it starts using Google Calendar;
running this first shows that the key works and lists the calendars, and
shares every one with SMARTDESK_CALENDAR_OWNER (again, which is harmless), in
case the owner was set after the calendars were made.

Needs GOOGLE_SERVICE_ACCOUNT (see docs/guides/google-calendar.md). The Calendar
API has no charge.
"""

from smartdesk.booking.calendars.google import connect, ensure_calendars, share
from smartdesk.config import get_settings


def main() -> None:
    """Create any missing calendar, share every one with the owner, and list them."""
    owner = get_settings().calendar_owner
    api = connect()
    calendars, created = ensure_calendars(api)
    for person, calendar in calendars.items():
        if owner:
            share(api, calendar, owner)
        print(f"{'created' if person in created else 'exists '}  {person}")
    if owner:
        print(f"Shared with {owner}. Google emails them a link to add each calendar.")
    else:
        print("Not shared with anyone: set SMARTDESK_CALENDAR_OWNER to the owner's Google account and run again.")


if __name__ == "__main__":
    main()

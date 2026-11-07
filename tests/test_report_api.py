"""Tests for the report routes in smartdesk/reports/routes.py.

Run with:  .venv/bin/pytest tests/test_report_api.py
"""

import re

import pytest
from conftest import signed_in

from smartdesk.app import app
from smartdesk.reports.dataset import get_dataset
from smartdesk.reports.tools import run_report


@pytest.fixture(scope="module")
def client():
    """A test browser for the app, signed in as the owner: makes requests without starting a server."""
    return signed_in(app)


def test_options(client):
    options = client.get("/api/report/options").json()
    assert options["business"] == "Test Studio"
    assert (options["min_date"], options["max_date"]) == ("2025-10-01", "2026-09-30")
    assert "Massage Therapy" in options["categories"] and "Referral" in options["channels"]


def test_report_defaults_to_the_whole_period(client):
    report = client.get("/api/report").json()
    assert report["filters"] == {"start": "2025-10-01", "end": "2026-09-30", "category": None, "channel": None}
    assert report["summary"]["bookings"] == 2949
    assert report["trend"]["bucket"] == "month" and len(report["trend"]["points"]) == 12
    # Nothing exists before the data starts, so there is nothing to compare with.
    assert report["previous_period"] is None and report["change"] is None
    assert set(report) >= {"categories", "services", "channels", "customers", "feedback"}


def test_report_for_a_date_range(client):
    report = client.get("/api/report", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
    assert report["summary"]["bookings"] == 290
    assert report["trend"]["bucket"] == "day" and len(report["trend"]["points"]) == 30
    assert report["previous_period"] == {"start": "2026-08-02", "end": "2026-08-31"}
    assert report["change"]["revenue"] is not None


def test_filters_narrow_the_report(client):
    everything = client.get("/api/report").json()["summary"]["bookings"]
    facials = client.get("/api/report", params={"category": "Facials"}).json()
    both = client.get("/api/report", params={"category": "Facials", "channel": "Website"}).json()
    assert [c["category"] for c in facials["categories"]] == ["Facials"]
    assert both["summary"]["bookings"] < facials["summary"]["bookings"] < everything


def test_report_includes_previous_summary_for_comparisons(client):
    september = client.get("/api/report", params={"start": "2026-09-01", "end": "2026-09-30"}).json()
    assert september["previous_summary"]["bookings"] > 0
    assert client.get("/api/report").json()["previous_summary"] is None


def test_manage_page_and_its_files_are_served(client):
    page = client.get("/manage")
    assert page.status_code == 200
    assert client.get("/dashboard").status_code == 404  # the old address is gone
    # Both tabs and their panels are in the page.
    for name in ("profile", "reports"):
        assert f'data-tab="{name}"' in page.text and f'id="panel-{name}"' in page.text
    # Every stylesheet and script the page links to must exist.
    for path in re.findall(r'(?:href|src)="(/static/dashboard/[^"]+)"', page.text):
        response = client.get(path)
        assert response.status_code == 200, path
        # The browser is told to re-check each file, so edits show up on refresh.
        assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("params", [
    {"start": "2026-09-30", "end": "2026-09-01"},  # range the wrong way round
    {"start": "last week"},                        # not a date
    {"category": "Haircuts"},                      # not in the data file
    {"channel": "Billboard"},
])
def test_bad_filters_are_rejected(client, params):
    assert client.get("/api/report", params=params).status_code == 422


def test_the_report_tool_explains_what_is_wrong_with_its_inputs():
    dataset = get_dataset()
    assert "no data for that period" in run_report(dataset, {"start": "2026-10-01", "end": "2026-10-31"})["error"]
    assert "start and end are required" in run_report(dataset, {"start": "last month"})["error"]
    assert "Unknown category" in run_report(dataset, {"start": "2026-09-01", "end": "2026-09-30", "category": "Hats"})["error"]

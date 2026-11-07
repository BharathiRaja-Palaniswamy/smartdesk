"""Tests for the business document and the app's own routes.

Run with:  .venv/bin/pytest tests/test_smartdesk.py
"""

import pytest
from fastapi.testclient import TestClient

from smartdesk import app as app_module
from smartdesk.config import get_settings
from smartdesk.business.knowledge import KnowledgeBase
from smartdesk.business.profile import build_profile


# Fixtures are shared set-up. scope="module" builds each one once for the whole file.
@pytest.fixture(scope="module")
def kb():
    """The real business document, parsed."""
    return KnowledgeBase(get_settings().data_path)


# ---- Business document ----
def test_document_is_read_into_services_and_facts(kb):
    assert kb.name == "Test Studio"
    assert kb.facts["Phone"] == "(555) 010-0100"
    swedish = next(i for i in kb.items if i.name == "Swedish Massage")
    assert (swedish.category, swedish.get("price"), swedish.get("duration")) == (
        "Massage Therapy", "$115 / $160", "60 minutes / 90 minutes")
    lip_wax = next(i for i in kb.items if i.name == "Lip Wax")
    assert (lip_wax.category, lip_wax.get("price")) == ("Hair Removal", "$18")


def test_pieces_can_be_found_by_title(kb):
    assert kb.find("Cancellation Policy").lines[0].startswith("Cancellations or rescheduling")
    assert kb.find("Business Hours").lines[-1] == "Sunday: 10:00 AM – 5:00 PM"
    assert kb.find("No Such Heading") is None


# ---- Business profile (manage page) ----
def test_profile_follows_the_document(kb):
    profile = build_profile(kb)
    titles = [s["title"] for s in profile["sections"]]
    assert titles[:3] == ["About", "Mission", "Location and Hours"]
    assert titles[-1] == "Seasonal Promotions"
    section = {s["title"]: s for s in profile["sections"]}

    # Sub-headings become groups, and services keep their duration and price.
    services = section["Core Services"]["groups"]
    assert [g["title"] for g in services] == ["Facials", "Massage Therapy", "Body Treatments", "Hair Removal", "Kids Services"]
    swedish = next(i for i in services[1]["items"] if i["name"] == "Swedish Massage")
    assert (swedish["duration"], swedish["price"]) == ("60 minutes / 90 minutes", "$115 / $160")
    wax = next(i for i in services[3]["items"] if i["name"] == "Eyebrow Wax")
    assert (wax["duration"], wax["price"]) == ("45 minutes", "$22")

    # Plain text keeps whether it was a bullet list.
    policies = {g["title"]: g for g in section["Policies"]["groups"]}
    assert policies["Refund Policy"]["bulleted"] and len(policies["Refund Policy"]["lines"]) == 2
    assert not section["Mission"]["groups"][0]["bulleted"]

    # An entry without a price carries its own text.
    faq = section["Frequently Asked Questions"]["groups"][0]["items"][0]
    assert faq["name"] == "Do you offer services for children?" and faq["lines"][0].startswith("Yes.")
    hours = section["Location and Hours"]["groups"][0]
    assert "Phone: (555) 010-0100" in hours["lines"]
    assert hours["items"][0]["name"] == "Business Hours" and len(hours["items"][0]["lines"]) == 4


# ---- HTTP routes ----
def test_api():
    client = TestClient(app_module.app)

    assert client.get("/", follow_redirects=False).headers["location"] == "/manage"
    assert client.get("/api/profile").json()["name"] == "Test Studio"


def test_the_powered_by_line_follows_the_model_set(monkeypatch):
    client = TestClient(app_module.app)
    assert client.get("/api/powered-by").json() == {"customer": "Claude", "owner": "Claude"}
    monkeypatch.setenv("SMARTDESK_MODELS", "opensource")
    assert client.get("/api/powered-by").json() == {"customer": "Nebius", "owner": "Nebius"}

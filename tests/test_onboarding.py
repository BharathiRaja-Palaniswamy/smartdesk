"""Tests for onboarding (smartdesk/onboarding/): reading documents, checking the
services table the model reads from them, and going live.

The model is a stand-in that plays back a prepared answer (tests/standins.py):
nothing is spent. Each test that goes live uses a folder of its own.

Run with:  .venv/bin/python -m pytest tests/test_onboarding.py
"""

import io
from pathlib import Path

import docx
import pytest
from conftest import signed_in
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from standins import use_standin

from smartdesk.app import app
from smartdesk.business.store import document_path, get_knowledge
from smartdesk.onboarding.readers import Unreadable, read
from smartdesk.onboarding.services import OptionRead, ServiceRead, ServicesRead, check

PDF = Path(__file__).parent / "fixtures" / "price-list.pdf"
PRICE_LIST = read("price-list.pdf", PDF.read_bytes()).text

SWEDISH = ServiceRead(name="Swedish Massage", category="Massage Therapy",
                      options=[OptionRead(minutes=60, price=115), OptionRead(minutes=90, price=160)],
                      quote="Swedish Massage\nDuration: 60 minutes / 90 minutes\nPrice: $115 / $160")


# ---- reading files ---------------------------------------------------------------

def test_text_pdf_and_word_documents_are_read():
    assert read("menu.md", b"# Menu\nSwedish Massage").text == "# Menu\nSwedish Massage"
    pdf = read("price-list.pdf", PDF.read_bytes())
    assert pdf.kind == "pdf" and pdf.pages == 1 and "Price: $115 / $160" in pdf.text
    word = docx.Document()
    word.add_paragraph("Lip Wax: 15 minutes, $18")
    data = io.BytesIO()
    word.save(data)
    assert read("menu.docx", data.getvalue()).text == "Lip Wax: 15 minutes, $18"


@pytest.mark.parametrize("name, data, reason", [
    ("tool.exe", b"MZ...", "isn't supported"),
    ("menu.pdf", b"just text", "not a PDF"),
    ("menu.docx", b"just text", "not a Word document"),
    ("menu.md", b"", "empty"),
    ("menu.txt", b"\xff\xfe\x00", "not a text file"),
])
def test_a_file_that_is_not_what_it_says_is_refused_with_the_reason(name, data, reason):
    with pytest.raises(Unreadable, match=reason):
        read(name, data)


# ---- checking what the model read ---------------------------------------------------

def test_each_option_becomes_a_row_backed_by_the_documents_words():
    reading = check(ServicesRead(services=[SWEDISH]), PRICE_LIST)
    assert [(s.name, s.minutes, s.price) for s in reading.services] == [
        ("Swedish Massage", 60, 115), ("Swedish Massage", 90, 160)]
    assert reading.problems == []


def test_a_service_whose_words_are_not_in_the_document_is_dropped():
    made_up = ServiceRead(name="Hot Stone Massage", category="", options=[OptionRead(minutes=60, price=140)],
                          quote="Hot Stone Massage 60 minutes $140")
    reading = check(ServicesRead(services=[made_up]), PRICE_LIST)
    assert reading.services == [] and "Hot Stone Massage: dropped" in reading.problems[0]


def test_a_value_the_document_does_not_state_is_left_empty_never_guessed():
    wrong_price = ServiceRead(name="Lip Wax", category="Hair Removal", options=[OptionRead(minutes=15, price=20)],
                              quote="Lip Wax\nDuration: 15 minutes\nPrice: $18")
    no_price = ServiceRead(name="Brow Shaping", category="Hair Removal", options=[],
                           quote="Brow Shaping\nAsk at the desk.")
    reading = check(ServicesRead(services=[wrong_price, no_price]), PRICE_LIST)
    assert [(s.name, s.minutes, s.price) for s in reading.services] == [
        ("Lip Wax", 15, None), ("Brow Shaping", None, None)]  # price missing: shown, not bookable
    assert any("price 20 left empty" in problem for problem in reading.problems)


# ---- the routes ------------------------------------------------------------------------

@pytest.fixture
def own_folder(tmp_path, monkeypatch):
    """A business folder of the test's own; the test business comes back afterwards."""
    monkeypatch.setenv("SMARTDESK_BUSINESS_FOLDER", str(tmp_path / "business"))
    monkeypatch.setenv("SMARTDESK_WIDGET_KEY", "pub_test_123")
    yield tmp_path / "business"
    get_knowledge.cache_clear()


def test_read_then_go_live(own_folder, monkeypatch):
    use_standin(monkeypatch, [AIMessage(content=ServicesRead(services=[SWEDISH]).model_dump_json())])
    owner = signed_in(app)
    answer = owner.post("/api/onboarding/read", files=[("files", ("price-list.pdf", PDF.read_bytes(), "application/pdf")),
                                                       ("files", ("virus.exe", b"MZ", "application/octet-stream"))],
                       data={"business": "Test Studio"})
    assert answer.status_code == 200
    body = answer.json()
    assert body["documents"] == [{"name": "price-list.pdf", "kind": "pdf", "pages": 1}]
    assert [(s["name"], s["minutes"], s["price"]) for s in body["services"]] == [
        ("Swedish Massage", 60, 115), ("Swedish Massage", 90, 160)]
    assert any("virus.exe" in problem for problem in body["problems"])
    assert document_path() != own_folder / "business.md"  # nothing live before Go live

    rows = body["services"] + [{"name": "Gift Wrap", "minutes": 15, "price": None}]  # the owner added one
    live = owner.post("/api/onboarding/go-live", json={"services": rows})
    assert live.status_code == 200 and 'data-business="pub_test_123"' in live.json()["snippet"]
    assert document_path() == own_folder / "business.md"  # the agents now read the onboarded document
    assert get_knowledge().name == "Test Studio"  # the PDF had no title: the owner's business name is used


def test_go_live_needs_a_document_read_first(own_folder):
    reply = signed_in(app).post("/api/onboarding/go-live", json={"services": [{"name": "Swedish Massage"}]})
    assert reply.status_code == 409


def test_only_the_signed_in_owner_may_onboard():
    stranger = TestClient(app)
    reply = stranger.post("/api/onboarding/read", files=[("files", ("a.md", b"x", "text/markdown"))], data={"business": "X"})
    assert reply.status_code == 401


def test_reset_needs_the_name_typed_and_brings_back_the_configured_document(own_folder, monkeypatch):
    use_standin(monkeypatch, [AIMessage(content=ServicesRead(services=[SWEDISH]).model_dump_json())])
    owner = signed_in(app)
    owner.post("/api/onboarding/read", files=[("files", ("price-list.pdf", PDF.read_bytes(), "application/pdf"))],
               data={"business": "Test Studio"})
    owner.post("/api/onboarding/go-live", json={"services": [{"name": "Swedish Massage", "minutes": 60, "price": 115}]})
    assert document_path() == own_folder / "business.md"

    assert owner.post("/api/onboarding/reset", json={"confirm": "Test"}).status_code == 422
    done = owner.post("/api/onboarding/reset", json={"confirm": "Test Studio"}).json()
    assert done["removed"] == ["services table", "onboarded document"]
    assert document_path().name == "business.md" and document_path().parent.name == "fixtures"  # the configured one

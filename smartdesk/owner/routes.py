"""The owner chat's route: POST /api/report/chat, one question about the business.

The reply is structured: the model is given OwnerReply as a schema and must
fill in every field, so the manage page can rely on them (show the answer,
lay a list out as a list, say where it came from, style a "not covered"
reply differently). The model returns data; the page decides how it looks.

Only the signed-in owner may ask (the "reports" permission, smartdesk/access/).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from langsmith import traceable
from pydantic import BaseModel, Field

from ..access.session import require
from ..models import ModelError
from ..replies import MAX_SUGGESTIONS, UNAVAILABLE, ReplyItem
from ..reports.dataset import get_dataset
from ..search.errors import ModelUnavailable
from . import answer
from .prompt import checked_sections

router = APIRouter(prefix="/api/report", dependencies=[Depends(require("reports"))])
log = logging.getLogger("smartdesk.owner")


class OwnerQuestion(BaseModel):
    """The JSON body the chat sends."""

    question: str


# The docstring and each field's `description` are sent to the model as part
# of the schema; they are how it learns what each field is for.
class OwnerReply(BaseModel):
    """The assistant's reply to one question from the business's owner."""

    answer: str = Field(description="The reply to show the owner, in plain sentences without markdown. Two to "
                                    "four sentences normally. When `items` is used, one short sentence that "
                                    "introduces the list and does not repeat its entries. For an answer from "
                                    "report figures, one sentence naming the period and the headline result.")
    items: list[ReplyItem] = Field(description="Use when the answer is a list of three or more things, such as "
                                               "services with their prices: one entry per thing, in the "
                                               "profile's order. Always use it for report figures: one entry "
                                               "per figure, the most important first, never written out as a "
                                               "paragraph. Empty for any other answer.")
    insights: list[str] = Field(description="Only for answers from report figures: two or three short "
                                            "observations about what the figures mean for the owner, each one "
                                            "sentence, each resting on figures in the report. Say what stands "
                                            "out, what explains a change, or what deserves attention. Do not "
                                            "repeat a figure without adding a point. Empty for any other answer.")
    covered: bool = Field(description="True if the business profile or the report figures contain the answer. "
                                      "False if they do not, or if the question is not about the business.")
    sections: list[str] = Field(description="The profile sections the answer was taken from, by their exact "
                                            "heading, most specific first. Empty when covered is false, when "
                                            "the answer came from report figures, or no section was needed.")
    suggestions: list[str] = Field(description="Up to three short questions the owner might naturally ask next. "
                                               "Each must be answerable from the profile or the reports, be written "
                                               "as the owner would ask it, and not repeat the question just "
                                               "asked.")


class OwnerAnswerBody(OwnerReply):
    """What the route sends to the browser: the model's reply, plus how it was
    produced. Kept apart from OwnerReply so the model is not asked to fill
    these in; the server knows them."""

    chunks: int  # how many passages were retrieved
    reports: list[str]  # the reports the model asked for, e.g. "2026-09-01 to 2026-09-30"


# The owner assistant's own instructions. The rules for using the profile, the
# current time and the passages are added after them (prompt.py).
INSTRUCTIONS = """You are the assistant for the owner of a business. You answer the owner's \
questions about their own business.

For questions about how the business is doing (revenue, bookings, \
cancellations, channels, customers, feedback), call the get_report tool and \
answer from the figures it returns. Never estimate or invent a figure. Work \
out the dates to ask for from the current time; "last month" means the last \
full calendar month. Say which period your figures cover. If the tool \
reports that there is no data for a period, tell the owner what the data covers."""


@router.post("/chat")
@traceable  # the whole request is the top step of the trace
def chat(body: OwnerQuestion) -> OwnerAnswerBody:
    """Answer one question about the business."""
    try:
        result = answer(INSTRUCTIONS, body.question, OwnerReply, get_dataset())
    except (ModelError, ModelUnavailable) as error:
        # ModelError: the gateway's error, whichever provider failed.
        # ModelUnavailable: search could not reach Pinecone.
        log.warning("owner assistant unavailable: %s", error)  # the reason, for whoever reads the server log
        raise HTTPException(status_code=503, detail=UNAVAILABLE)

    if result.reply is None:
        # No structured reply came back, for example because the model declined to answer.
        raise HTTPException(status_code=503, detail="The assistant could not answer that.")

    reply = result.reply
    reply.sections = checked_sections(reply.sections, result.headings)
    # The schema cannot limit how many suggestions come back, so the limit is applied here.
    reply.suggestions = reply.suggestions[:MAX_SUGGESTIONS]
    return OwnerAnswerBody(**reply.model_dump(), chunks=result.chunks, reports=result.reports)

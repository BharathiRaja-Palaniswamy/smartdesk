"""The owner chat's prompt, as a LangChain template, and the check on what a reply cites.

A `ChatPromptTemplate` is a list of messages with {placeholders}; invoking it
with values fills them in. The system message holds the assistant's own
instructions, the rules for using the business's documents, the current
time, the headings it may cite, and the passages the retriever found, each
between tags so the model can tell instructions apart from data.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate

from ..business.store import get_knowledge
from ..config import get_settings

# How to treat the passages: the only source of facts, quoted exactly, and
# "not found" said plainly rather than guessed.
PROFILE_RULES = """The parts of the business profile that best match the question are given \
below, each between <excerpt> tags, inside <profile> tags. They are the only \
source of facts about what the business offers. Quote prices, hours and policies \
exactly as written there. They were cut by length, so an excerpt may begin or end \
mid-sentence; the rest of the profile is not shown. If the excerpts do not contain \
the answer, say plainly that you could not find it in the profile; do not guess or \
fill in what businesses usually do.

Answer the question that was asked. If the excerpts have only related \
information, not the answer itself, say first that the answer is not in the \
profile, then offer what is related.

The current date and time at the business are given below between <currentTime> \
tags. Use them to work out dates, days of the week and how much time is left \
when a question depends on them, then answer from the profile as usual.

The headings of the excerpts are listed between <sections> tags. When you name \
the sections an answer came from, use those names exactly, and prefer the most \
specific one: the sub-heading the answer sits under, where there is one."""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", "{instructions}\n\n{rules}\n\n<currentTime>{current_time}</currentTime>\n\n"
               "<sections>\n{sections}\n</sections>\n\n<profile>\n{profile}\n</profile>"),
    ("human", "{question}"),
])


def all_headings() -> list[str]:
    """Every heading and sub-heading of the document, in order."""
    # dict.fromkeys removes repeats while keeping the document's order.
    return list(dict.fromkeys(name for pair in get_knowledge().outline for name in pair if name))


def prompt_values(instructions: str, question: str, documents: list[Document]) -> dict[str, str]:
    """The values that fill PROMPT, from the passages the retriever found.
    Only the headings of those passages can be cited, so a source the model
    was never shown cannot be named."""
    settings = get_settings()
    found = {name for doc in documents for name in doc.metadata["sections"]}
    headings = [name for name in all_headings() if name in found]
    profile = "\n".join(f"<excerpt>\n{doc.page_content}\n</excerpt>" for doc in documents)
    # The model has no clock, so it is told the current date and time in the
    # business's own time zone, e.g. "Friday, 09 October 2026, 3:42 PM (PDT)".
    current_time = datetime.now(ZoneInfo(settings.timezone)).strftime("%A, %d %B %Y, %-I:%M %p (%Z)")
    return {"instructions": instructions, "rules": PROFILE_RULES, "current_time": current_time,
            "sections": "\n".join(headings), "profile": profile, "question": question}


def checked_sections(cited: list[str], headings: list[str]) -> list[str]:
    """The sections a reply cited, keeping only real ones, most specific first.

    Structured output guarantees the shape of a reply, not that its content is
    right, so the model's section names are checked against the headings it
    was shown: the page never shows a source that does not exist.
    """
    cited = [name for name in cited if name in headings]
    # When a sub-heading is cited, its parent heading adds nothing: "Cancellation
    # Policy" already says where the answer is, so "Policies" is dropped.
    parents = {heading for heading, subheading in get_knowledge().outline if subheading in cited}
    return [name for name in cited if name not in parents]

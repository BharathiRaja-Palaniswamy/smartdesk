"""What the chats share about replies: one list entry, how many follow-up
questions to show, and what to say when the model cannot be reached.

Each chat defines its own reply class (its fields are described for its own
reader, customer or owner), and both use ReplyItem for lists.
"""

from pydantic import BaseModel, Field

# How many follow-up questions a chat shows under an answer. The schema cannot
# limit a list's length, so each route cuts the list to this many.
MAX_SUGGESTIONS = 3
# What a chat route answers (503) when the model or search cannot be reached.
UNAVAILABLE = "The assistant is unavailable right now."


# Part of the structured output. The description of each field is sent to the
# model as an instruction.
class ReplyItem(BaseModel):
    """One entry of a list in the assistant's reply, for example one service."""

    name: str = Field(description="What the entry is, e.g. 'Swedish Massage', 'Late cancellations' or 'Revenue'.")
    detail: str = Field(description="The facts about it, kept short, e.g. '60 / 90 minutes, $115 / $160', or for "
                                    "a figure its value and change: '$19,818, down 2.1% from $20,235'.")

"""Settings for the whole app, in one place.

Two kinds of configuration live here:

1. Constants that say HOW the app uses the business document (which block
   holds the opening hours, which section lists the team). They only name
   headings; the facts themselves are always read from the document.
2. `Settings`: values that can differ per machine (API model, file paths).
   Each one can be overridden with an environment variable or a line in the
   `.env` file.

Every other module imports from here, so nothing else reads `os.environ`.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Reads the `.env` file (if there is one) into environment variables. This is
# also how ANTHROPIC_API_KEY reaches the Anthropic SDK.
load_dotenv()

# The project folder (the parent of this `smartdesk/` package).
ROOT = Path(__file__).resolve().parent.parent

# ---- How the app uses the business document -------------------------------

# The bold block that lists opening hours, read by booking (smartdesk/booking/schedule.py).
HOURS_BLOCK = "Business Hours"
# Booking (smartdesk/booking/schedule.py): the section listing the team, with the
# days each member works and their specialties.
TEAM_SECTION = "Our Team"


# ---- Per-machine settings --------------------------------------------------

# Environment variables that pick a model for one profile (smartdesk/models/profiles.py).
PROFILE_PREFIX = "SMARTDESK_PROFILE_"
# The model sets, each a high-end and a low-end model (see smartdesk/models/profiles.py):
# set name -> (the variables that name its two models, and their defaults).
MODEL_SETS = {
    "claude": {"high": ("SMARTDESK_CLAUDE_HIGH", "anthropic:claude-opus-5-5"),
               "low": ("SMARTDESK_CLAUDE_LOW", "anthropic:claude-haiku-4-5-20251001")},
    "opensource": {"high": ("SMARTDESK_OPENSOURCE_HIGH", "nebius:Qwen/Qwen3-235B-A22B-Instruct-2507"),
                   "low": ("SMARTDESK_OPENSOURCE_LOW", "nebius:Qwen/Qwen3-30B-A3B-Instruct-2507")},
}

@dataclass(frozen=True)  # frozen: settings cannot be changed after they are loaded
class Settings:
    """Values that can differ per machine. Read once by `get_settings`."""

    data_path: Path | None  # the business document the assistants answer from; None when not set
    assistant_name: str  # the name the customer chat's assistant gives itself, e.g. "Robin"; "" for none
    eval_set_path: Path | None  # the business's golden eval set (evals/); None when not set
    report_data_path: Path | None  # the bookings JSON the report dashboard reads; None when not set
    timezone: str  # the business's time zone, used to tell the assistant the current time
    chunk_tokens: int  # search: how many tokens each chunk of the document holds
    chunk_overlap: int  # search: how many tokens a chunk shares with the one before it
    header_tokens: int  # search: the most tokens of a chunk's header, used for search only; 0 for no headers
    vector_store: str  # search: which vector store keeps the chunks: "pinecone" or "memory" (tests)
    vector_store_path: Path  # search: names a local index (tests give each its own, so in-memory stores stay apart)
    pinecone_index: str  # search: the Pinecone index to use
    retrieval_top_k: int  # search: how many chunks are given to the model for a question
    reranker: str  # search: "pinecone" to rerank the candidates, or "none"
    rerank_candidates: int  # search: how many chunks the first search fetches for the reranker to choose from
    slot_minutes: int  # booking: appointments start on this grid, e.g. every 30 minutes from opening
    min_notice_minutes: int  # booking: the fewest minutes ahead a booking can be made, changed or cancelled
    handoffs_path: Path  # the chat: where requests for the staff to call a customer back are appended
    feedback_path: Path  # the chat: where customers' feedback, as the Front Desk's feedback tool read it, is appended
    debug: bool  # the chat: show what happened between the agents under each reply (for testing only)
    # The model gateway (smartdesk/models/). A model is named "provider:model", e.g.
    # "nebius:Qwen/Qwen3-235B-A22B-Instruct-2507".
    model_set: str  # which set of models the app uses: "claude" or "opensource"
    model_sets: dict[str, dict[str, str]]  # set -> {"high": "provider:model", "low": "provider:model"}
    model_fallback: str  # "provider:model" to try when a profile's own model fails; "" for none
    profile_models: dict[str, str]  # profile -> "provider:model", from SMARTDESK_PROFILE_<NAME> variables
    nebius_base_url: str  # the address of Nebius's OpenAI-compatible API
    nebius_api_key: str = field(repr=False)  # repr=False: never shown when settings are printed
    pinecone_api_key: str = field(repr=False)  # Pinecone's key: the vector store, its embedding model and reranker
    google_service_account: str = field(repr=False)  # booking: the service account's key, as JSON text or a file path
    calendar_owner: str  # booking: a Google account the calendars are shared with, to see them; "" for none
    voice_secret: str = field(repr=False)  # phone line: the secret ElevenLabs sends; "" switches the line off
    voice_agent_id: str  # the ElevenLabs agent the manage page's phone-line test talks to; "" hides the test
    owner_password: str = field(repr=False)  # the manage page's sign-in; "" keeps the owner's pages closed
    session_secret: str = field(repr=False)  # signs the owner's sign-in cookie; "" uses a random key per start


def _path(variable: str) -> Path | None:
    """The file a variable names, or None when it is not set. Used for a business's
    own files: SmartDesk holds no business's data, so these have no default."""
    value = os.getenv(variable, "")
    return Path(value) if value else None


def get_settings() -> Settings:
    """Read every setting from the environment, falling back to its default."""
    # os.getenv(name, default) returns the environment variable if it is set,
    # otherwise the default written here.
    return Settings(
        data_path=_path("SMARTDESK_DATA"),
        assistant_name=os.getenv("SMARTDESK_ASSISTANT_NAME", ""),
        eval_set_path=_path("SMARTDESK_EVAL_SET"),
        report_data_path=_path("SMARTDESK_REPORT_DATA"),
        timezone=os.getenv("SMARTDESK_TIMEZONE", "America/Los_Angeles"),
        chunk_tokens=int(os.getenv("SMARTDESK_CHUNK_TOKENS", "150")),
        chunk_overlap=int(os.getenv("SMARTDESK_CHUNK_OVERLAP", "30")),
        header_tokens=int(os.getenv("SMARTDESK_HEADER_TOKENS", "50")),
        vector_store=os.getenv("SMARTDESK_VECTOR_STORE", "pinecone"),
        vector_store_path=Path(os.getenv("SMARTDESK_VECTOR_STORE_PATH", ROOT / "storage" / "vectors")),
        pinecone_index=os.getenv("SMARTDESK_PINECONE_INDEX", "smartdesk"),
        retrieval_top_k=int(os.getenv("SMARTDESK_RETRIEVAL_TOP_K", "3")),
        reranker=os.getenv("SMARTDESK_RERANKER", "pinecone"),
        rerank_candidates=int(os.getenv("SMARTDESK_RERANK_CANDIDATES", "20")),
        slot_minutes=int(os.getenv("SMARTDESK_SLOT_MINUTES", "30")),
        min_notice_minutes=int(os.getenv("SMARTDESK_MIN_NOTICE_MINUTES", "30")),
        handoffs_path=Path(os.getenv("SMARTDESK_HANDOFFS", ROOT / "storage" / "handoffs.jsonl")),
        feedback_path=Path(os.getenv("SMARTDESK_FEEDBACK", ROOT / "storage" / "feedback.jsonl")),
        debug=os.getenv("SMARTDESK_DEBUG", "false").lower() == "true",
        model_set=os.getenv("SMARTDESK_MODELS", "claude"),
        model_sets={name: {tier: os.getenv(variable, default) for tier, (variable, default) in tiers.items()}
                    for name, tiers in MODEL_SETS.items()},
        model_fallback=os.getenv("SMARTDESK_MODEL_FALLBACK", ""),
        # SMARTDESK_PROFILE_CHEAP_ROUTER=nebius:... -> {"cheap-router": "nebius:..."}
        profile_models={name.removeprefix(PROFILE_PREFIX).lower().replace("_", "-"): value
                        for name, value in os.environ.items() if name.startswith(PROFILE_PREFIX) and value},
        nebius_base_url=os.getenv("SMARTDESK_NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/"),
        nebius_api_key=os.getenv("NEBIUS_API_KEY", ""),
        pinecone_api_key=os.getenv("PINECONE_API_KEY", ""),
        google_service_account=os.getenv("GOOGLE_SERVICE_ACCOUNT", ""),
        calendar_owner=os.getenv("SMARTDESK_CALENDAR_OWNER", ""),
        voice_secret=os.getenv("SMARTDESK_VOICE_SECRET", ""),
        voice_agent_id=os.getenv("SMARTDESK_VOICE_AGENT_ID", ""),
        owner_password=os.getenv("SMARTDESK_OWNER_PASSWORD", ""),
        session_secret=os.getenv("SMARTDESK_SESSION_SECRET", ""),
    )

"""One turn of the agent's conversation, as a LangGraph graph.

                 +--> identify --(details complete and a question waiting)--> agent
                 |        +--(otherwise: ask, or thank them)--> END
    START -------+--> decide (a yes or no was waited for) ---------------> agent
                 |        +--(yes to the details, and a plan to approve)--> END
                 +--> agent <------------------------------------+
                        |                                         |
                        +--(asked for tools)--> tools --(ran them)+
                        |                         +--(a booking to confirm)--> END
                        +--(too many rounds, or a request repeated)--> give_up --> END
                        +--(replied)--> END

It runs once per customer message. The checkpointer keeps each conversation's
state between messages, by thread id: that is the agent's memory. It is kept
in this server's memory, so a restart starts every conversation afresh.

The steps (plain functions: the state in, what changed out):
  identify  name and phone first (agent.py reads them)
  agent     one call to the agent: a reply, or tool requests
  tools     runs them; a plan booking (code) found, or a cancellation, is held
            for the customer's yes (yes.py), asked in one question that says
            what the check found ("16:00 is taken")
  decide    their answer: yes to a plan or cancellation -> executor.py;
            anything else back to the agent with their reply
  give_up   too many rounds or repeats: the staff take over (staff.py)
AgentState, what a conversation remembers, is defined here too.
"""

import json
import re
from functools import lru_cache
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from ..frontdesk import executor as approved
from ..booking.appointments import digits
from ..models import run_requests, structured
from ..privacy import remember
from .booking import Plan
from .debug import brief, note, outcome
from .details import customer_words
from .agent import (
    HELD,
    join_now,
    STARTERS,
    AgentReply,
    about_bookings,
    agent_tools,
    ask_for,
    instructions,
    read_details,
    valid_phone,
)
from .rules import (A_TIME, AGENT_MODEL, ASKS_TO_CONFIRM, CHECK_FIRST, CLAIMS_DONE, MAX_REPEATS, MAX_TOOL_ROUNDS,
                    NOT_DONE, plain_quotes)
from .staff import HANDOVER, record_handoff
from .yes import cancel_question, checked, done_message, is_yes, plan_question, waitlist_question


@lru_cache  # one graph, and so one memory, for the whole server
def get_graph() -> CompiledStateGraph:
    """The agent's graph, ready to run, with its memory."""
    graph = StateGraph(AgentState)
    for step in (identify, agent, tools, decide, give_up):
        graph.add_node(step.__name__, step)
    graph.add_conditional_edges(START, first_step, ["identify", "decide", "agent"])
    graph.add_conditional_edges("identify", after_identify, ["agent", END])
    graph.add_conditional_edges("agent", after_agent, ["tools", "give_up", END])
    graph.add_conditional_edges("tools", after_tools, ["agent", "give_up", END])
    graph.add_conditional_edges("decide", after_decide, ["agent", END])
    graph.add_edge("give_up", END)
    return graph.compile(checkpointer=InMemorySaver(), name="booking_agent")


REPEATED = ("You already made this exact request this turn; its result is above and will not change. Do not "
            "repeat it: answer the customer, ask them what they meant, or use hand_off.")


class AgentState(TypedDict, total=False):
    """One customer conversation."""

    # The conversation as the model sees it: the customer's messages, the
    # agent's replies, and each tool request with its result. add_messages
    # appends new messages (and removes one when given a RemoveMessage).
    messages: Annotated[list[AnyMessage], add_messages]
    channel: str  # "chat" (the website) or "voice" (a phone call): how the agent phrases its replies
    caller: str  # on a phone call, the number calling (caller ID); "" in the chat
    name: str  # the customer's name, once given
    phone: str  # their phone number, once given (not verified)
    held: bool  # they asked something before giving their details: answer it once they have
    pending: dict | None  # details, a plan or a cancellation waiting for the customer's yes, with its request
    failed_plans: int  # approved plans in a row that could not be booked (a time taken meanwhile)
    rounds: int  # tool rounds this turn
    asked: list[str]  # this turn's tool requests, to spot one asked for again unchanged
    repeats: int  # this turn: requests the model asked for again unchanged
    requests: list[dict]  # the model's latest tool requests: {"name", "args", "id"}
    reply: BaseModel | None  # the model's reply this turn, once it gives one
    say: str  # a reply written by the graph itself this turn (asking for details or for a yes)
    suggestions: list[str]  # replies to tap offered with `say` this turn (the starters, after the details)
    confirming: bool  # this turn ends by asking the customer to confirm
    acted: bool  # this turn made or cancelled a booking (the customer said yes)
    untrue: bool  # this turn the agent twice said something was done that was not: the staff take over
    untold: bool  # a replaced turn before this one made or cancelled a booking the customer was not told of


def _latest(state: AgentState) -> HumanMessage:
    """The customer's message this turn: the last message the route added."""
    return state["messages"][-1]


# ---- where each turn starts ----------------------------------------------

def first_step(state: AgentState) -> str:
    """Details first; then a waiting yes-or-no; otherwise the agent."""
    if not (state.get("name") and state.get("phone")):
        return "identify"
    return "decide" if state.get("pending") else "agent"


# ---- identify ----------------------------------------------------------------

def _said(name: str, message: str) -> bool:
    """True when every word of `name` is in the customer's message."""
    words = set(re.findall(r"\w+", message.lower()))
    return bool(name.strip()) and set(re.findall(r"\w+", name.lower())) <= words


# Words that only give the details ("my name is Asha, you can reach me on ..."): saying them asks
# for no warm word back. A greeting, thanks or a question about how the agent is says something more.
DETAILS_WORDS = {"my", "name", "names", "is", "im", "i", "am", "this", "it", "its", "here", "phone", "number", "no",
                 "and", "the", "call", "me", "you", "can", "reach", "on", "at", "s", "m", "mobile", "cell"}


# A sentence that asks for their details ("Please provide your name and phone number"): code's to ask.
ASKS_DETAILS = re.compile(r"\b(name|phone|number|contact)\b", re.IGNORECASE)


def _warm_word(reply: str, said: str, name: str) -> str:
    """The reader's warm sentences back to what the customer said, or "" when they said
    nothing beyond their name and number. Never a question, a request for their details,
    nor a number: asking is code's (ask_for), and their details are not read back here."""
    words = set(re.findall(r"[a-z]+", said.lower())) - set(re.findall(r"[a-z]+", name.lower())) - DETAILS_WORDS
    if not words:
        return ""
    sentences = re.findall(r"[^.!?]+[.!?]*", reply)
    return " ".join(part.strip() for part in sentences if not part.strip().endswith("?") and not re.search(r"\d", part)
                    and not ASKS_DETAILS.search(part))


def identify(state: AgentState) -> dict:
    """Read the name and phone number from the customer's message, and ask
    for whatever is still missing. Once both are known: what they asked
    before giving them goes straight on to the agent (they have said what
    they want); otherwise, if the number has upcoming bookings, ask whether
    this is about one of them or something new; otherwise thank them."""
    last = next((m.text for m in reversed(state["messages"]) if isinstance(m, AIMessage)), "")
    # On the website the greeting (static/home/js/chat/welcome.js) has already asked for the name
    # and number before the first message, but only the browser showed it; so the reader is told,
    # or "raja 9289381938" is not read as a name. A call opens without that question.
    if not last and state.get("channel") != "voice":
        last = ask_for("", "")[1]
    details = read_details(_latest(state).text, last)  # with the question it answers
    note("Identify", "Front Desk", f"read name {details.name or '-'} · phone {details.phone or '-'}"
         + (f' · asked "{details.asked}"' if details.asked else ""), details.model_dump())
    caller, said = state.get("caller", ""), _latest(state).text
    # Their details are their own (rules.py, 2): a name or number the reader gave that is not
    # in what they wrote is not taken, and is asked for again.
    read = details.name.strip() if _said(details.name, said) else ""
    name = state.get("name") or read
    remember(name)  # masked in traces from now on (privacy.py)
    # A number they give wins; on a call, the number calling is used until they do.
    given = details.phone.strip() if valid_phone(details.phone) and digits(details.phone) in digits(said) else ""
    phone = given or state.get("phone") or caller
    # What they asked is theirs too: words not in their message are not kept (a model's guess).
    held = state.get("held", False) or (bool(details.asked.strip()) and _said(details.asked, said))
    known = {"name": name, "phone": phone}
    if name and phone and held:
        return {**known, "held": False}  # on to the agent, which answers what they asked first
    if name and phone and (question := about_bookings(name, phone, state.get("channel") == "voice")):
        # Their reply goes to the agent, which sees the whole conversation.
        return {**known, "held": False, "say": question, "messages": [AIMessage(question)]}
    # A warm word back to what they said (the reader's, in place of code's opening), then what is
    # still missing (code's).
    # A number they wrote (not one the reader made up), but not a whole one: asked for in full.
    partial = bool(digits(details.phone)) and digits(details.phone) in digits(said) and not given
    opening, question = ask_for(name, phone, caller, partial)
    say = f"{_warm_word(details.reply, said, name) or opening} {question}".strip()
    # Both given and nothing asked yet: "How can I help?" comes with a few things to tap.
    offered = STARTERS if name and phone else []
    return {**known, "held": held, "say": say, "suggestions": offered, "messages": [AIMessage(say)]}


def after_identify(state: AgentState) -> str:
    """To the agent when the details are complete and a question is waiting; else the turn ends."""
    return END if state.get("say") else "agent"


# ---- agent and tools ------------------------------------------------------------

def _offered(state: AgentState) -> list:
    """This customer's tools, with what they have written so far (to check the booking details against)."""
    return agent_tools(state["name"], state["phone"], words=customer_words(state["messages"]))


def _done_this_turn(messages: list) -> bool:
    """Whether a tool booked, changed or cancelled something since the customer's latest message."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if isinstance(message, ToolMessage):
            try:
                result = json.loads(message.content)
            except ValueError:
                continue
            result = result.get("result", result) if isinstance(result, dict) else {}  # a yes's result (decide)
            if isinstance(result, dict) and (result.get("booked") or result.get("cancelled")):
                return True
    return False


def _asks_to_confirm(answer) -> bool:
    """Whether the reply asks the customer to confirm a booking at a time itself, rather
    than having it checked (rules.py, 3: the confirmation is code's question)."""
    if answer.reply is None or answer.tool_calls:
        return False
    text = plain_quotes(answer.reply.answer)
    return bool(ASKS_TO_CONFIRM.search(text) and A_TIME.search(text))


def _untrue(answer, state: AgentState) -> bool:
    """Whether the reply says something was done that no tool did this turn, nor a
    replaced turn the customer never saw the reply of (rules.py, 3)."""
    return (answer.reply is not None and not answer.tool_calls
            and bool(CLAIMS_DONE.search(plain_quotes(answer.reply.answer)))
            and not _done_this_turn(state["messages"]) and not state.get("untold"))


def agent(state: AgentState) -> dict:
    """One model call with the whole conversation: it ends in a reply or in tool requests.
    A reply saying something was done that was not is never sent (rules.py, 3)."""
    offered = _offered(state)
    rules = instructions(state["name"], state["phone"], state.get("channel", "chat"))
    messages = [SystemMessage(rules), *state["messages"]]
    # After a repeated request, the model must answer now: asked again with tools, it tends to repeat again.
    answer = structured(AGENT_MODEL, messages, AgentReply, offered, answer_now=state.get("repeats", 0) > 0)
    if _asks_to_confirm(answer):
        # The yes is code's question, after the check (rules.py, 3): told to check, so it is asked once.
        note("The yes", "Front Desk", "asked for a yes itself: told to check first", answer.reply.answer)
        answer = structured(AGENT_MODEL, [*messages, SystemMessage(CHECK_FIRST)], AgentReply, offered)
    if _untrue(answer, state):
        note("The yes", "Front Desk", "said something was done that was not: asked again", answer.reply.answer)
        answer = structured(AGENT_MODEL, [*messages, SystemMessage(NOT_DONE)], AgentReply, offered)
        if _untrue(answer, state):
            note("The yes", "Handoff", "said it again: the staff take over", answer.reply.answer)
            return {"requests": [], "reply": None, "untrue": True}
    if answer.tool_calls:
        for call in answer.tool_calls:
            note("Front Desk", call["name"], brief(call["args"]), call["args"])
    elif answer.reply is not None:
        note("Front Desk", "Customer", answer.reply.answer, answer.reply.model_dump())
    message = answer.message
    if answer.reply is not None and message.tool_calls:
        # A reply given as the answer tool's call (open models), with or without other calls: it is
        # remembered as the reply's text, so no call is left without a result in the conversation,
        # and the question the agent asked can be read (a customer's yes to it: details.py).
        message = AIMessage(answer.reply.model_dump_json())
    return {"messages": [message], "requests": answer.tool_calls, "reply": answer.reply}


def after_agent(state: AgentState) -> str:
    """The end when the model replied; the tools when it asked for some and has rounds left;
    the staff when it kept saying something was done that was not."""
    if state.get("untrue"):
        return "give_up"
    if state.get("reply") is not None or not state.get("requests"):
        return END
    return "tools" if state.get("rounds", 0) < MAX_TOOL_ROUNDS else "give_up"


def _offer(result: dict, request: dict, state: AgentState) -> dict:
    """The state that asks the customer to approve booking (code)'s plan, a
    cancellation, or joining the waitlist; {} when `result` is none of them."""
    spoken = state.get("channel") == "voice"
    if result.get("status") == "plan_ready":
        plan = Plan.model_validate(result["plan"])
        # What the check found about the time they asked for (the booking tool sends both).
        question = checked(result.get("request") or {}, result.get("time_said", ""), plan, spoken) + plan_question(
            plan, state["name"], state["phone"], spoken, result.get("replaces"))
        replaces = (result.get("replaces") or {}).get("reference", "")
        held = {"kind": "plan", "plan": result["plan"], "replaces": replaces}
    elif result.get("status") == "cancel_ready":
        question = cancel_question(result["cancel"], spoken)
        held = {"kind": "cancel", "references": [booking["reference"] for booking in result["cancel"]]}
    elif result.get("status") == "waitlist_ready":
        question = waitlist_question(result["waitlist"], state["phone"], spoken)
        held = {"kind": "waitlist", "waitlist": result["waitlist"]}
    else:
        return {}
    keep = {key: request[key] for key in ("name", "args", "id")}
    note("The yes", "Customer", question, {"waits for a yes to": held["kind"]})
    return {"pending": {**keep, **held, "question": question}, "say": question, "confirming": True}


def _hold(request: dict, state: AgentState, results: list) -> dict:
    """Run a booking request. A plan booking (code) found, or a cancellation, is held
    for the customer's yes, asked in one question. Anything else (what is missing,
    the openings to choose from, why nothing fits, their bookings) goes back to the
    model, added to `results`. Returns the state to change."""
    [answer] = run_requests([request], _offered(state))
    result = json.loads(answer.content)
    if offer := _offer(result, request, state):
        return offer
    results.append(answer)
    return {}


def _key(request: dict) -> str:
    """A request as one string, to spot the same request asked for again."""
    return request["name"] + json.dumps(request["args"], sort_keys=True)


def tools(state: AgentState) -> dict:
    """Run what the model asked for; a booking request may end in a question
    for the customer's yes (`_hold`). A request already made
    this turn is not run again (models sometimes loop on one: a booking
    reference they made up, a handoff written six times): the model is told
    its result will not change."""
    asked, repeated = list(state.get("asked") or []), False
    fresh, results = [], []
    for request in state["requests"]:
        if _key(request) in asked:
            repeated = True
            results.append(ToolMessage(json.dumps({"error": REPEATED}), tool_call_id=request["id"]))
        else:
            asked.append(_key(request))
            fresh.append(request)
    now = [r for r in fresh if r["name"] not in HELD]
    later = [r for r in fresh if r["name"] in HELD]
    results += run_requests(now, _offered(state))
    update: dict = {"rounds": state.get("rounds", 0) + 1}
    if len(later) == 1:
        update |= _hold(later[0], state, results)
    elif later:  # several at once: which one the customer meant is not clear, so none is run
        results += [ToolMessage(json.dumps({"error": "Send one booking request at a time, with everything the "
                                                      "customer has said."}), tool_call_id=r["id"]) for r in later]
        asked = [key for key in asked if key not in {_key(r) for r in later}]  # not run: may be sent again alone
    by_id = {r["id"]: r for r in state["requests"]}
    for message in results:
        request = by_id.get(message.tool_call_id, {})
        result = json.loads(message.content)
        note(request.get("name", "?"), "Front Desk", outcome(result), {"args": request.get("args"), "result": result})
    # Rounds with a repeat, not repeated requests: two repeated at once are one round, and the
    # next call must answer (agent: answer_now) before the staff take over (MAX_REPEATS).
    repeats = state.get("repeats", 0) + repeated
    # A tool whose answer is meant for the customer (the Feedback agent's reply) ends the turn with
    # it: the customer hears it as the agent's, and the agent is not asked again.
    spoken = next((json.loads(m.content)["reply_to_customer"] for m in results
                   if "reply_to_customer" in json.loads(m.content)), None)
    if spoken is not None:
        reply = AgentReply(answer=spoken, items=[], suggestions=[])
        update |= {"reply": reply, "messages": [*results, AIMessage(reply.model_dump_json())]}
        return {**update, "asked": asked, "repeats": repeats}
    return {**update, "asked": asked, "repeats": repeats, "messages": results}


def after_tools(state: AgentState) -> str:
    """The turn ends while waiting for the customer's yes, or when a tool answered the
    customer (the Feedback agent); the staff take over when the model keeps repeating
    a request; otherwise back to the model."""
    if state.get("confirming") or state.get("reply") is not None:  # asking for a yes, or already answered
        return END
    return "give_up" if state.get("repeats", 0) >= MAX_REPEATS else "agent"


# ---- the customer's yes or no ------------------------------------------------------

def decide(state: AgentState) -> dict:
    """The customer's answer to what is waiting for their yes.

    Yes to a plan or a cancellation: it is carried out, and the model is
    told what happened, in the request's result. After a yes, the customer's words go
    only into that result: passed on as a new message, a "yes, book it"
    would read as a new request. After anything else, nothing is done and
    their reply is passed on, since it may ask for something else."""
    pending, said = state["pending"], _latest(state)
    # The messages since the request (time notes, the customer's replies) came
    # in after it; its result must come straight after it, so they are taken
    # out, and put back after it only when not a yes.
    start = next(n for n, m in enumerate(state["messages"])
                 if any(call["id"] == pending["id"] for call in getattr(m, "tool_calls", None) or []))
    since = state["messages"][start + 1:]
    acted = is_yes(said.text)  # a yes books or cancels: something that really happens
    to = {"plan": "Executor", "cancel": "Approved", "waitlist": "Waitlist"}[pending["kind"]] if acted else "Front Desk"
    note("Customer", "The yes", f'"{said.text}": ' + ("yes" if acted else "not a yes, so nothing is done"),
         {"to": pending["question"]})
    note("The yes", to, f"go ahead with the {pending['kind']}" if acted else "their reply goes back to the agent")
    update: dict = {"asked": [*(state.get("asked") or []), _key(pending)]}  # not asked for again this turn
    if acted and pending["kind"] == "plan":
        result, failed = approved.book(pending["plan"], pending["replaces"], state["name"], state["phone"],
                                       state.get("failed_plans", 0))
        update["failed_plans"] = failed
    if acted and pending["kind"] == "cancel":
        result = approved.cancel(pending["references"], state["phone"])
    if acted and pending["kind"] == "waitlist":
        result = join_now(pending["waitlist"], state["name"], state["phone"])
    removed = [RemoveMessage(id=message.id) for message in since]
    if acted:
        note(to, "Front Desk", outcome(result), result)
        told = {"customer_said_yes_to": pending["question"], "customer_said": said.text, "result": result}
        update |= {"pending": None, "acted": True}
        # What was done is told by code, as the question was (rules.py, 3): the references and
        # times exactly as booked. What was not done goes to the agent to explain.
        if say := done_message(result, state.get("channel") == "voice"):
            note("The yes", "Customer", say, result)
            return {**update, "say": say, "messages": [
                *removed, ToolMessage(json.dumps(told), tool_call_id=pending["id"]), AIMessage(say)]}
        return {**update, "messages": [*removed, ToolMessage(json.dumps(told), tool_call_id=pending["id"])]}
    told = {"not_done": f"The customer was asked {pending['question']!r} and did not say yes, so "
                           "nothing was changed. Their reply follows."}
    return {**update, "pending": None, "acted": False, "messages": [
        *removed, ToolMessage(json.dumps(told), tool_call_id=pending["id"]),
        *[HumanMessage(message.content) for message in since]]}


def after_decide(state: AgentState) -> str:
    """The turn ends when a plan now waits for the customer's yes, or when what was done has
    been told (code's words); otherwise the agent answers."""
    return END if state.get("confirming") or state.get("say") else "agent"


# ---- too many rounds -----------------------------------------------------------------

def give_up(state: AgentState) -> dict:
    """Stop, hand the request to the staff, and tell the customer."""
    if not any(key.startswith("hand_off") for key in state.get("asked") or []):  # not twice in one turn
        record_handoff(state["name"], state["phone"], "The assistant could not finish the customer's request.")
    say = HANDOVER
    note("Handoff", "Customer", "too many steps or repeats: the staff take over",
         {"rounds": state.get("rounds", 0), "repeats": state.get("repeats", 0)})
    # Every request gets one result, so the conversation can carry on next turn
    # (requests the tools step already answered keep that answer).
    answered = {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)}
    stopped = [ToolMessage(json.dumps({"error": "Stopped: too many steps."}), tool_call_id=r["id"])
               for r in state["requests"] if r["id"] not in answered]
    return {"say": say, "messages": [*stopped, AIMessage(say)]}

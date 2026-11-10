# Workflow spec: Slot recovery (the empty chair)

From `docs/templates/WORKFLOW.md`. Status: **demo build**.

## 1. Purpose and boundaries *(Developer)*

| | |
|---|---|
| **Job, in one sentence** | When an appointment is cancelled, offer the opened time to a customer on the waitlist who asked for it, and book it only when they say yes. |
| **Triggered by** | A cancellation, or a change that moves a booking, through the Front Desk agent (`frontdesk/executor.py`); the freed slot is offered only if it is really free then (a change kept at the same time offers nothing), and offering never undoes the cancellation or change |
| **Input** | The cancelled booking: service, staff member, start and end |
| **Output** | One offer to one waitlisted customer, shown in their chat and, while the business is open, a phone call from the agent (D34); a booking if they accept |
| **Out of scope (demo)** | SMS offers (US carrier registration first), changes (a moved booking), packages |

## 2. Steps

| # | Step | Code or AI | Input → output |
|---|---|---|---|
| 1 | Join the waitlist | the agent's `join_waitlist` tool (code) | when a wanted time is not free and the customer **agrees** to wait: service, day, optional time window, and when they agreed |
| 2 | A slot opens | code, after a cancellation | the cancelled booking's service, staff member and time |
| 3 | Match | code (`waitlist/choose.py`, D34) | every waiting customer who wants that service on that day, with the start inside their window (both ends included: 15:00 to 15:00 is "3 pm only"), ranked: **exactly that time** first, then a window (narrower first), then any time; then fewer offers let run out unanswered; then who joined first. One at a time (D6) |
| 4 | Offer | code | held for a time that follows how soon the slot is: a twelfth of the time until it starts, at least 5 minutes, at most SMARTDESK_OFFER_MINUTES (60 by default), and never past the minimum notice before it starts; a slot too near for that is offered to nobody. Shown in the customer's chat (the widget checks every few seconds) and written into their conversation |
| 4b | Call | code (`waitlist/calls.py`), no AI | while the business is open: a keypad call through Twilio from the business's own number. It reads "The <service> you asked for, on <day> at <time>, is available now. To book it, press 1. If you don't want it, press 2." **1** books exactly that slot (checked free again) and says the reference; **2** lets it go and the next customer is called; no key: asked once more, then the offer stays open until it runs out. The key comes back to `POST /api/waitlist/answer/{offer}` with the offer's private key; nothing is booked without a 1 (D39) |
| 5 | Answer | the agent's `answer_offer` tool (code) | yes → book that exact slot (still free, checked) and close the offer; no → close it and offer the next match |
| 6 | Expiry | code | an offer not answered in time closes, and the next match is offered |

## 3. AI inside steps

None decides who is offered or books: the agent only hears the customer and
calls the tools; matching, expiry and booking are code.

## 4. Threats and design review

| Threat | Defence |
|---|---|
| Two customers booked into one slot | one offer at a time per slot; the slot is checked free again at "yes" |
| Offering without consent | only customers who agreed to join the waitlist, with when they agreed recorded |
| One customer's offer reaching another | an offer is tied to the customer's phone; the widget asks for offers by its own conversation, and the server finds that conversation's customer |
| Booking without the customer's yes | `answer_offer` books only on the customer's yes to that offer |
| Calling without consent, or at night | only customers who agreed to wait, told first that we may call them; calls only while the business is open |
| A call reaching the wrong person | the number dialled is the one the customer gave; a waiter without a whole number is not offered the slot |
| Someone else answering an offer | the keypad's answer is taken only with the offer's private key, which only that call carries |
| Tests phoning real people | no ElevenLabs key in tests; the call tests stand in for ElevenLabs |

## 5. Tests that must pass

| Gate | Bar |
|---|---|
| A cancellation offers the slot to the earliest matching waiter only | all pass |
| No match: nobody is offered | all pass |
| Yes books exactly the offered slot; no and expiry offer the next waiter | all pass |
| A slot taken meanwhile is not booked on "yes" | all pass |

## 6. Storage (demo build)

The waitlist and offers are kept in the business's folder
(`waitlist.jsonl`, `offers.jsonl`); with cells (M2) they move to the
business's database.

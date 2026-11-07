# SmartDesk

**An AI front desk for appointment-based businesses.**

> **Status: proposed product, concept stage.** A working single-business version
> already exists (see [Where it starts](#where-it-starts)); SmartDesk turns it
> into a platform any appointment-based business can sign up to.

SmartDesk answers customers from owner-approved knowledge, handles booking from
start to finish by chat and phone, and helps fill cancelled slots.

📄 **Pitch pamphlet:** [SmartDesk.pdf](pamphlet/SmartDesk.pdf)

---

## The problem

Small spas and salons juggle calls, repeat questions, bookings and last-minute
changes, often with no one free to answer. Customers wait. Appointments slip.
Open slots go unfilled.

## What SmartDesk does

1. **Learns your business, with your approval.** You share service details,
   policies, documents and past support call recordings you're authorized to use.
   SmartDesk transcribes, cleans and organizes them, flags gaps and conflicts,
   and asks you to resolve them. Nothing goes live until you approve it.
2. **Answers your customers** on your website and over the phone, using only
   your approved knowledge.
3. **Handles booking from start to finish.** Check availability, book,
   reschedule or cancel in one conversation. Anything it can't handle goes to
   your staff, with the reason attached.
4. **Plus: fills cancelled slots.** When an appointment is cancelled, SmartDesk
   can offer the opening to eligible customers on your waitlist who opted in.
   No booking is confirmed until the customer accepts.

## Built on trust

- Answers come only from knowledge the owner has approved.
- Call recordings only *suggest* knowledge; the owner decides what's true.
  Documents win over recordings; conflicts go to the owner.
- Personal details are hidden before anything is stored.
- Customers opt in to waitlist offers and accept before they're booked.
- Booking actions are done by code, only after the customer confirms exactly
  what will happen.

## Scope

| Initial scope (spas and salons first) | Planned for later |
|---|---|
| Business knowledge from documents and call recordings, owner-approved | Campaign management |
| Website chat assistant | More customer engagement workflows |
| Phone support | |
| Full booking: availability, book, reschedule, cancel | |
| Hand-off to staff | |
| Filling cancelled slots from the waitlist | |

## Where it starts

SmartDesk grows out of a working AI front desk built for one fictional spa
(Pebble Spa): [spaDesk](https://github.com/bharathiraja-palaniswamy/spaDesk) ·
[live overview](https://bharathiraja-palaniswamy.github.io/spaDesk/) ·
[evaluation write-up](https://bharathiraja-palaniswamy.github.io/spaDesk/week-4.html).

| Capability | In the working version | SmartDesk |
|---|---|---|
| Chat assistant with booking, changes, cancellations | ✅ | Reused |
| Phone line (speech in, speech out) | ✅ | Reused |
| Answers from the business guide (vector RAG with reranking) | ✅ | Reused, per business |
| Hand-off to staff with a reason | ✅ | Reused |
| Evaluations and production tracing (LangSmith) | ✅ | Per business |
| Many businesses on one engine | Designed for, one running | **New** |
| Onboarding from documents and call recordings | — | **New** |
| Owner review and approval of knowledge | — | **New** |
| Cancellation-slot recovery from the waitlist | — | **New** |

## How it will be built

- **Agents:** a front-desk agent per business (chat and phone), plus onboarding
  and waitlist agents; booking itself stays in code.
- **Knowledge:** speech-to-text, cleaning and classification turn documents and
  recordings into suggestions; approved knowledge is searched with RAG. Graph
  RAG is considered only where evaluations show linked questions failing.
- **Quality:** each business gets its own test set; live conversations are
  traced and sampled for human review.

## Roadmap

1. Onboard a business in minutes: documents and recordings in, owner-approved knowledge out.
2. Fill the empty chair: cancellation-slot recovery from an opt-in waitlist.
3. Many businesses on one engine.
4. Campaign management and engagement workflows.

---

*SmartDesk is a proposed product in concept stage. Features marked new or
planned are not yet available.*

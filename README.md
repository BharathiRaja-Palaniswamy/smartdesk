# SmartDesk

**An AI front desk for appointment-based businesses.**

> **Status: proposed product, in development.** A working single-business version
> already exists (see [Where it starts](#where-it-starts)); SmartDesk turns it
> into a platform any appointment-based business can sign up to.

SmartDesk answers customers from the business's own documents, handles booking
from start to finish by chat and phone, and helps fill cancelled slots.

📄 **Pitch pamphlet:** [SmartDesk.pdf](pamphlet/SmartDesk.pdf) (the original
pitch; the first release is narrower, see [Scope](#scope)) ·
🗺️ **Build plan:** [docs/PLAN.md](docs/PLAN.md)

---

## The problem

Small spas and salons juggle calls, repeat questions, bookings and last-minute
changes, often with no one free to answer. Customers wait. Appointments slip.
Open slots go unfilled.

## What SmartDesk does

1. **Learns your business from your documents.** You enter the basics and
   upload your price lists, service menus, policies and FAQs (PDF, Word, text,
   or photos). SmartDesk reads them, builds a services table you can check and
   edit, and makes the rest searchable for your assistant.
2. **Answers your customers** on your website and over the phone, using only
   your documents. When they don't say, it says so and hands over to your staff.
3. **Handles booking from start to finish.** Check availability, book,
   reschedule or cancel in one conversation, from your services table and
   calendar. Anything it can't handle goes to your staff, with the reason attached.
4. **Plus: fills cancelled slots.** When an appointment is cancelled, SmartDesk
   can offer the opening to eligible customers on your waitlist who opted in.
   No booking is confirmed until the customer accepts.

## Built on trust

- Answers come only from your documents; prices for booking come only from the
  services table you can see and edit.
- Each business's information is kept separate.
- Personal details are hidden before anything is stored.
- Customers opt in to waitlist offers and accept before they're booked.
- Booking actions are done by code, only after the customer confirms exactly
  what will happen.

## Scope

| First release (spas and salons first) | Planned for later |
|---|---|
| Onboarding from business basics and documents | Learning from past support call recordings |
| Services table, checked and editable by the owner | Owner review of gaps and conflicts before going live |
| Website chat assistant | Campaign management |
| Phone support | More customer engagement workflows |
| Full booking: availability, book, reschedule, cancel, on Google Calendar | Connecting to existing booking systems (Square and others) |
| Hand-off to staff | |
| Filling cancelled slots from the waitlist | |

## Where it starts

SmartDesk grows out of a working AI front desk built for one fictional business:
[spaDesk](https://github.com/bharathiraja-palaniswamy/spaDesk) ·
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
| Onboarding from uploaded documents, with a services table | — | **New** |
| Cancellation-slot recovery from the waitlist | — | **New** |

## How it is built

- **Agents:** Front Desk (chat and phone), Feedback and Owner agents, reused
  and made per business; booking, matching and consent stay in code.
- **Document intelligence:** pdfplumber and python-docx, with Claude reading
  images and scanned pages; a services table extracted into a strict Pydantic
  schema, normalised and validated by code, with an exact quote behind every
  value. Sections are searched with RAG in each business's own Pinecone namespace.
- **Quality:** a parser benchmark, per-field precision and recall, abstention
  tests (no invented prices), per-business evals, and traced live conversations
  sampled for human review.
- **Security by default:** every agent and workflow is specified first, from
  [templates](docs/templates/) that cover threats, test gates and live checks.

## Try the preview

The front end is a static preview (sample data, no backend yet):
`web/index.html` (landing page), `web/onboard.html` (onboarding),
`web/demo/sample-business.html` (the chat widget on a business's site).

---

*SmartDesk is a proposed product in development. Features marked new or
planned are not yet available.*

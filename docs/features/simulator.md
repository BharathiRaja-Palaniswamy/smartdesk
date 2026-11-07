# Feature spec: Simulator (talk to a business's real agent, safely)

From `docs/templates/WORKFLOW.md`, adapted for a tool. Status: **draft for review**.

## 1. Purpose and boundaries *(Developer)*

| | |
|---|---|
| **Job, in one sentence** | Lets a person chat with one business's real Front Desk agent and watch every step, without touching that business's customers, calendar or staff. |
| **Used by** | SmartDesk admin, for any business (from the admin console's **Simulate** link); the business owner, for their own business ("Preview your assistant" before go-live) |
| **Real** | the model, the prompt, the business's search and services table, the agent's rules and tools |
| **Never real** | bookings on the live calendar, hand-offs to staff, feedback cards, real customers |
| **Out of scope** | load testing; replaying live conversations (later) |

## 2. The sandbox (D26)

| The real agent uses | In the simulator |
|---|---|
| The business's Google calendars | a **sandbox calendar**: a copy of the real calendars' busy times when the session starts, kept in memory; bookings and cancellations land only there |
| Hand-offs and feedback cards | written to the session only, shown in the debug panel; staff never see them |
| The customer's name and phone | a made-up test customer; a phone number that belongs to a real customer of the business is refused |
| The clock | the business's time now, or a time the person sets ("Friday 2 pm") to test date logic |
| Traces | the business's trace project, tagged `simulator`, kept out of live monitoring and review queues |
| Cost | real tokens; a per-session limit, and the session's cost shown in the panel |

The sandbox is chosen by code when the session starts, before the agent is
built: the agent's tools are made with the sandbox calendar and the session's
hand-off and feedback stores, so no tool can reach the real ones.

## 3. Screen

```
┌ Simulator: Test Studio ─────────────────────── sandbox · $0.03 of $0.50 ┐
│ Customer: Test Customer, (555) 010-9999   Clock: Fri 2:00 PM [change]     │
│ Channel: chat ▾ (chat · phone, as text)                    [Reset]        │
├───────────────────────────────────────┬──────────────────────────────────┤
│  chat, as the customer sees it        │ debug: each step, live           │
│                                       │ ● Front Desk (AI) thinking 1.2 s │
│                                       │ ├ search_knowledge → 3 passages  │
│                                       │ ├ booking new · Deep Tissue 60   │
│                                       │ └ The yes (code) "Just to check" │
│                                       │ Sandbox bookings: 1 · hand-offs: 0│
└───────────────────────────────────────┴──────────────────────────────────┘
```

- **Reset** starts a fresh session: a new sandbox calendar, an empty memory.
- The debug panel is the live debug view (`docs/PLAN.md`, Debug view): never
  the system prompt, personal details hidden.

## 4. Access (D27)

| Who | May simulate | Conditions |
|---|---|---|
| SmartDesk admin | any business | it is **support access**: a stated reason, time-limited, logged, and shown to the owner |
| Business owner | their own business only | signed in as that business's owner |
| Anyone else | no one | 401 |

## 5. Threats and design review *(AI security review)*

| Threat | Defence | Tested by |
|---|---|---|
| A simulated booking reaching the live calendar | tools built with the sandbox calendar; the live calendar is never opened for writing in a session | test: a session's booking leaves the live calendar unchanged |
| A real customer's bookings read or cancelled | real customers' phone numbers refused; the sandbox holds only busy times, no customer details | test |
| Staff paged by a test | hand-offs and cards go to the session store | test |
| An admin reading business content through the agent | counts as support access: reason, time limit, log, owner notified | access test |
| Runaway cost | per-session token limit; the session stops with a message | limit test |
| Simulated chats polluting monitoring and evals | traces tagged `simulator`; excluded from review rules and health summaries | test |

## 6. Tests that must pass *(Policy gates)*

| Gate | Bar |
|---|---|
| Booking, changing, cancelling in a session never writes to the live calendar | zero writes |
| No hand-off or feedback card reaches the business's stores | zero |
| A real customer's phone number is refused | all pass |
| Owner of A cannot simulate B; admin use is logged with its reason | all pass |
| The session stops at its cost limit | all pass |

## 7. Live checks *(Runtime verification)*

| | |
|---|---|
| **Audit log** | each session: who, which business, why (admin), when, cost |
| **Shown to the owner** | admin sessions on their business |
| **Debug view** | live, in the panel |

## Build

- **v0, one business** (the business the settings name, before cells): the
  real agent with the sandbox calendar, session stores, settable clock and
  the debug panel; signed-in owner only. It is also how the chats are tried
  locally.
- **Real, per business**: with cells, opened from the admin console's
  Simulate link and from onboarding's "Preview your assistant".

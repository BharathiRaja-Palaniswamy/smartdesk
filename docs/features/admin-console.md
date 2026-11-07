# Feature spec: Admin console (SmartDesk monitoring its clients)

From `docs/templates/WORKFLOW.md`, adapted for a screen. Status: **draft for review**.

## 1. Purpose and boundaries *(Developer)*

| | |
|---|---|
| **Job, in one sentence** | Lets SmartDesk's own team see every business's health at a glance and act when one needs help. |
| **Used by** | SmartDesk staff (the admin role), never business owners |
| **Shows** | Health, never content (D19): status, channels, counts, activity, errors, cost |
| **Out of scope** | Reading a business's documents, customers or chats (only through support access); billing |

## 2. Screens

**Business list** (`/admin`)

| Column | Example | From |
|---|---|---|
| Business, type | Test Studio · Spa | registry |
| Status | draft · live · paused · resetting · deleting · **failed** | registry |
| Created / live since | 7 Nov · 7 Nov | registry |
| Documents / services | 3 · 24 (2 price missing) | cell summary |
| Channels | widget on example.com ✓ · phone ✓ · calendar ✓ (4 staff) | registry + cell summary |
| Activity, 7 days | 132 chats · 18 bookings · 3 open hand-offs · last chat 2 h ago | cell summary |
| Health, 24 h | 0 errors · reply p95 6.2 s | cell summary |
| Cost today | $0.42 of $5.00 | cell summary |
| Links | **Simulate** (`docs/features/simulator.md`) · Traces | — |

Failed and paused first, then live, then draft. Filter by status; search by name.

**Business detail** (`/admin/businesses/<id>`): the same facts in full, the
last go-live, reset or delete with its steps, and the actions below.

## 3. Where the numbers come from

Each cell writes a small **health summary** to the registry after anything
changes (a document processed, a go-live, a chat turn, an error). The admin
console reads the registry only; it never opens a cell's database, so its
code cannot reach documents, customers or chats.

| Summary field | Updated when |
|---|---|
| documents, services, price missing | a document is processed; the services table is saved |
| chats, bookings, hand-offs (7 days), last chat | each chat turn ends |
| errors, reply p95 (24 hours) | each chat turn ends |
| cost today | each model call |

## 4. Actions

| Action | What happens | Confirmation |
|---|---|---|
| Pause / resume assistant | widget and phone say "temporarily unavailable" / answer again | one click, logged |
| Retry | finishes a failed go-live, reset or delete from its failed step | one click, logged |
| Reset onboarding / delete business | as `docs/workflows/go-live.md` parts C and D | type the business name |
| Simulate | opens the simulator for this business (counts as support access, D27) | a stated reason, logged |
| Traces | opens the business's LangSmith project | — |

No "log in as this business": support access and the simulator replace it.

## 5. Threats and design review *(AI security review)*

| Threat | Defence | Tested by |
|---|---|---|
| The console used to read every business's data | reads the registry only; no code path to a cell's database | test: admin routes never open a cell |
| A stolen admin sign-in | separate admin role, second factor, short sessions, every view and action logged | access tests |
| An owner reaching `/admin` | admin role required on every admin route | access test |
| A wrong pause or delete | typed name for delete and reset; pause is reversible | UI test |

## 6. Tests that must pass *(Policy gates)*

| Gate | Bar |
|---|---|
| Only the admin role reaches `/admin` (owners and visitors get 401) | all pass |
| The list shows only registry fields and summaries | no document, customer or chat field in any admin response |
| Pause stops the widget and phone within one request; resume restores them | all pass |
| Every action is in the audit log with who and when | all pass |

## 7. Live checks *(Runtime verification)*

| | |
|---|---|
| **Audit log** | every admin view of a business, every action, every support access |
| **Alerts** | a business failed; errors above the usual rate; cost over budget |
| **Debug view** | not shown here; the simulator has it |

## Build

- **Preview** (static, sample businesses): to settle the layout now.
- **Real**: needs the registry and cells; built with cells, then filled in as
  summaries become available (activity and cost once traffic is recorded).

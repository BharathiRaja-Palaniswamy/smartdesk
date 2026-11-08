# Demo script (about 2 minutes)

Before going on stage:

- SmartDesk running locally with the demo settings (RUNNING.md, "The demo build").
- Onboarding reset (last step of `/web/onboard.html`), so it starts empty.
- Signed in as the owner in one browser window.
- Four tabs open: landing `/web/`, onboarding `/web/onboard.html`,
  demo site `/web/demo/sample-business.html` (two windows, side by side),
  admin `/web/admin.html`.
- A copy of the test business's document to upload (`tests/fixtures/business.md`,
  or the price-list PDF `tests/fixtures/price-list.pdf`).
- Start each chat with the name and number only ("Asha Rao, 555 010 0001"),
  no "Hi": the first reply is then the plain one.

| Time | Screen | Do | Say |
|---|---|---|---|
| 0:00 | Landing | scroll once | "Small spas and salons miss calls, answer the same questions all day, and lose money when a slot is cancelled. SmartDesk is an AI front desk for them." |
| 0:15 | Onboarding | basics: Test Studio, Spa, hours → upload the document → read | "A business signs up and uploads what it already has: price lists, menus, policies." |
| 0:35 | Services table | point at the rows, hover "Your document", show a problem line | "It reads them into a services table. Every price and length is checked against the document's own words; anything it can't back up is left empty, never guessed." |
| 0:50 | Done | Save and finish → "is live", the snippet | "One line on their website, and they're live." |
| 0:55 | Demo site, window 1 | Asha books a Prenatal Massage, Friday 3 pm, confirms twice | "Customers ask and book in plain words. It always reads the booking back and waits for their yes." |
| 1:15 | Demo site, window 2 | Ben asks for the same time, says only 3 pm works, joins the waitlist | "The time is taken, so Ben joins the waitlist." |
| 1:30 | Window 1 | Asha cancels | "Now Asha cancels…" |
| 1:35 | Window 2 | the offer appears within seconds → "Yes, book it" | "…and Ben is offered the slot straight away. He says yes, and the empty chair is filled. No staff involved." |
| 1:50 | Admin | the list, statuses, cost | "And SmartDesk watches every business it runs: health, cost, problems first, never their customers' data." |
| 2:00 | — | — | "Built on LangChain and LangGraph, with evals, tracing and security designed in. Thank you." |

If something goes wrong on stage: the chat always answers (a slow or failed
model hands over politely to staff), and every step can be shown again from
the admin console's Simulate link to the demo site.

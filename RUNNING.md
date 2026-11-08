# Running SmartDesk

All commands are run from the project folder.

## 1. Install (once)

You need Python 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv venv -p 3.13 .venv                           # a private Python environment for this project
uv pip install -p .venv/bin/python -r requirements.txt
```

## 2. Settings (once)

```sh
cp .env.example .env
```

`.env` is listed in `.gitignore`, so keys are never committed. Fill in:

- `ANTHROPIC_API_KEY`: the models (Claude).
- `PINECONE_API_KEY`: search (Pinecone keeps the passages and runs the
  embedding model and the reranker).
- **The business to run.** SmartDesk holds no business's data, so point it
  at one business's own files (until onboarding stores businesses in their
  own cells):
  - `SMARTDESK_DATA`: its document (markdown)
  - `SMARTDESK_REPORT_DATA`: its bookings, for the reports (JSON)
  - `SMARTDESK_ASSISTANT_NAME`: what its assistant calls itself (optional)
- `SMARTDESK_OWNER_PASSWORD`: the owner's sign-in for the manage page.
- `GOOGLE_SERVICE_ACCOUNT`: booking, on the business's Google calendars
  (see [docs/guides/google-calendar.md](docs/guides/google-calendar.md)).

Every setting is described in `.env.example`.

## 3. Start the app

```sh
.venv/bin/uvicorn smartdesk.app:app --reload
```

Open http://127.0.0.1:8000: it leads to the owner's manage page (sign in
with the owner's password). Customers reach the Front Desk agent through the
chat widget on the business's own website, and by phone.

`--reload` restarts the server whenever you save a Python file.

## The demo build (one business, nothing reaches a real calendar)

The settings the demo runs with, in `.env` (keys from your own accounts):

```sh
SMARTDESK_MODELS=opensource            # the open-source models through Nebius (NEBIUS_API_KEY)
SMARTDESK_DATA=tests/fixtures/business.md          # the made-up test business, until one is onboarded
SMARTDESK_REPORT_DATA=tests/fixtures/bookings.json
SMARTDESK_VECTOR_STORE=memory          # search kept in memory (Pinecone's embeddings and reranker)
SMARTDESK_CALENDAR=memory              # bookings kept in memory: never a real calendar
SMARTDESK_WIDGET_KEY=pub_demo_sample   # the key the demo page's widget uses
SMARTDESK_ASSISTANT_NAME=Robin
SMARTDESK_OWNER_PASSWORD=...           # your own, to sign in
```

Then start the app (section 3) and open, on http://127.0.0.1:8002 if you
start it with `--port 8002`:

| Page | What it shows |
|---|---|
| `/web/` | the landing page |
| `/web/onboard.html` | onboarding: basics, documents (read for real), services table, go live |
| `/web/demo/sample-business.html` | a business's website with the chat widget (the real agent) |
| `/web/admin.html` | the admin console preview (sample businesses) |
| `/manage` | the owner's console |

The empty chair: in one browser window a customer asks for a time that is
taken and agrees to the waitlist; in another, the customer who has that time
cancels; the first window is offered the slot within a few seconds and
books it with "Yes, book it". The phone line: docs/guides/phone-demo.md.

## 4. Run the tests

```sh
.venv/bin/python -m pytest
```

The tests use a made-up test business (`tests/fixtures/`), fake embeddings
and stand-in models: they need no keys, reach no outside service and spend
nothing.

## 5. Front-end preview

The landing page, onboarding and the chat widget are a static preview with
sample data for now:

```sh
python3 -m http.server 8100 --directory web
```

Then open http://127.0.0.1:8100.

"""Onboarding: a business's documents in, checked safe, live for its assistant (docs/workflows/onboarding.md).

    readers.py  a document's text, from Markdown, text, CSV, PDF or Word, with its real type checked
    safety.py   cleaning what a page could run, and the check for what must not reach customers
    phone.py    the business's phone line, when the owner asks for phone support (D32)
    store.py    where the draft, its check, the onboarded document and the phone line are kept
    routes.py   the owner's routes: read; check; phone offer; go live; reset

The documents are taken as they are: SmartDesk asks nothing about the business (D31).
Only the owner, signed in, may onboard (the "onboarding" permission, access/).
"""

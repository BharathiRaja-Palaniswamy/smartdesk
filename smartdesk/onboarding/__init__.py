"""Onboarding: a business's documents in, its services table out (docs/workflows/onboarding.md).

    readers.py   a document's text, from Markdown, text, PDF or Word, with its real type checked
    services.py  the services table, read from that text by a model and checked by code
    store.py     where the business's onboarded document and services table are kept
    routes.py    the owner's routes: read uploaded documents; go live

Only the owner, signed in, may onboard (the "onboarding" permission, access/).
"""

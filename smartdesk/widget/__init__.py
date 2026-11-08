"""The chat widget's server side: which business a widget key belongs to.

The widget (web/widget/chat.js) is the one script a business pastes on its
website. When it loads, it asks GET /api/widget/business?key=... for the
business's name and greeting; each message then goes to the Front Desk
agent (POST /api/assistant). An unknown key gets 404, and the widget says it
is not set up for this website.

Demo build: one business, one key (SMARTDESK_WIDGET_KEY). With cells (M2),
each business has its own key, valid only on its own website's domains.
"""

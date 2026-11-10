/* SmartDesk chat widget: the one script a business pastes on its site.

     <script src=".../widget/chat.js" data-business="pub_..." defer></script>

   It draws a chat button and panel inside a Shadow DOM, so the site's styles
   and the widget's never touch. Replies come from the "brain" (brain.js): the
   business's real Front Desk agent on the SmartDesk server. A reply is an
   answer, an optional list (shown as lines under it) and suggested next
   questions (shown as buttons). While open, after the first message, it
   checks every few seconds for a slot offered from the waitlist.

   Messages are always set as text, never HTML: a reply can't run code on the
   business's page. */

(() => {
  const script = document.currentScript;
  const base = script.src.replace(/chat\.js(\?.*)?$/, "");
  const key = script.dataset.business || "";
  const OFFER_CHECK_MS = 5000;  // how often an open chat checks for a slot offered from the waitlist
  const MAX_LINES = 4;  // the message box grows to this many lines, then scrolls
  const LINE_HEIGHT = 20;  // px, as chat.css sets it for the box
  const BOX_EDGES = 18;  // px: the box's padding (8 + 8) and border (1 + 1)

  /** Load another widget file next to this one. */
  function load(file) {
    return new Promise((resolve, reject) => {
      const tag = document.createElement("script");
      tag.src = base + file;
      tag.onload = resolve;
      tag.onerror = reject;
      document.head.append(tag);
    });
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function build(brain, business) {   // business: null when not set up for this key
    const host = el("div");
    host.id = "smartdesk-widget";
    document.body.append(host);
    const root = host.attachShadow({ mode: "open" });

    const style = el("link");
    style.rel = "stylesheet";
    style.href = base + "chat.css";

    const launcher = el("button", "launcher", "💬");
    launcher.setAttribute("aria-label", business ? `Chat with ${business.name}` : "Chat");

    const panel = el("section", "panel");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Chat");
    panel.hidden = true;

    const head = el("header");
    const titles = el("div");
    titles.append(el("strong", "", business ? business.name : "Chat"), el("span", "", "AI assistant"));
    const close = el("button", "close", "×");
    close.setAttribute("aria-label", "Close chat");
    head.append(titles, close);

    const log = el("div", "log");
    log.setAttribute("aria-live", "polite");

    const quick = el("div", "quick");
    const form = el("form");
    // A box that grows with the message (up to MAX_LINES), so a long one is never cut off.
    const input = el("textarea");
    input.rows = 1;
    input.placeholder = "Type a message";
    input.setAttribute("aria-label", "Message");
    input.maxLength = 500;
    const send = el("button", "send", "Send");
    send.type = "submit";
    form.append(input, send);

    const note = el("p", "note", "You're chatting with an AI assistant. Ask for a person any time. Powered by SmartDesk");

    panel.append(head, log, quick, form, note);
    root.append(style, launcher, panel);

    function say(who, text, items = []) {
      const message = el("div", `msg ${who}`);
      if (text) message.append(el("p", "text", text));
      // A list under the answer (services, bookings, times): a bulleted list, the name in bold.
      if (items.length) {
        const list = el("ul", "items");
        items.forEach((item) => {
          const row = el("li");
          row.append(el("b", "", item.name));
          if (item.detail) row.append(document.createTextNode(`: ${item.detail}`));
          list.append(row);
        });
        message.append(list);
      }
      log.append(message);
      log.scrollTop = log.scrollHeight;
    }

    /** The message box's height follows its text, up to MAX_LINES; then it scrolls. */
    function fit() {
      input.style.height = "auto";
      // scrollHeight counts the text and padding but not the border, so add the border back.
      const needed = input.scrollHeight + (input.offsetHeight - input.clientHeight);
      input.style.height = `${Math.min(needed, LINE_HEIGHT * MAX_LINES + BOX_EDGES)}px`;
    }

    function offer(suggestions) {
      quick.replaceChildren(...suggestions.map((text) => {
        const chip = el("button", "chip", text);
        chip.type = "button";
        chip.addEventListener("click", () => ask(text));
        return chip;
      }));
    }

    let checking = null;  // the timer that checks for offers, once the customer has written

    function checkOffers() {
      if (checking) return;
      checking = setInterval(async () => {
        if (panel.hidden) return;
        try {
          const found = await brain.offer();
          if (found) {
            say("them", found.text);
            offer(found.suggestions);
          }
        } catch {
          // a missed check is fine: the next one comes in a few seconds
        }
      }, OFFER_CHECK_MS);
    }

    async function ask(text) {
      text = text.trim();
      if (!text) return;
      say("me", text);
      quick.replaceChildren();
      input.value = "";
      fit();
      input.disabled = send.disabled = true;
      const typing = el("p", "msg them typing", "…");
      log.append(typing);
      try {
        const reply = await brain.reply(text);
        say("them", reply.answer, reply.items);
        offer(reply.suggestions);
        checkOffers();
      } catch {
        say("them", "Sorry, I can't answer right now. Please call us, or try again in a moment.");
      } finally {
        typing.remove();
        input.disabled = send.disabled = false;
        input.focus();
      }
    }

    function open(show) {
      panel.hidden = !show;
      launcher.hidden = show;
      if (show) {
        if (!log.children.length) start();
        fit();  // one line tall until there is more to show
        input.focus();
      } else launcher.focus();
    }

    function start() {
      if (!business) {
        say("them", "This chat isn't set up for this website yet.");
        form.hidden = true;
        return;
      }
      say("them", business.greeting);
      offer(business.suggestions);
    }

    launcher.addEventListener("click", () => open(true));
    close.addEventListener("click", () => open(false));
    panel.addEventListener("keydown", (event) => { if (event.key === "Escape") open(false); });
    form.addEventListener("submit", (event) => { event.preventDefault(); ask(input.value); });
    input.addEventListener("input", fit);
    // Enter sends; Shift+Enter starts a new line.
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        ask(input.value);
      }
    });

    // Opened by the page: only once chat.css has loaded, so the box is measured at its real size.
    if (script.dataset.open === "true") style.addEventListener("load", () => open(true), { once: true });
  }

  load("brain.js")
    .then(() => window.SmartDeskBrain.business(key))
    .then((business) => build(window.SmartDeskBrain, business))
    .catch(() => console.warn("SmartDesk: the chat could not load."));
})();

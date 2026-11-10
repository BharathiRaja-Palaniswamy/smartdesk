/* The owner's preview (D33): their website stand-in, with the chat widget added
   the way their snippet adds it.

   1. GET /api/onboarding/preview: the widget key and the business's own facts
      (owner sign-in; without it, sign in first)
   2. the page fills itself from those facts: services, team, hours, contact
   3. the widget's one script tag, with the key, opened

   The widget makes up a new conversation each time the page loads, so
   "Open another customer" opens this page again in a new tab: a second
   customer, for trying the waitlist. Text is always set as text, never HTML. */

(() => {
  const SIGN_IN = "/login?next=/web/preview.html";
  const KINDS_SHOWN = 4;  // the hero names at most this many kinds of service
  const $ = (id) => document.getElementById(id);

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  async function json(url) {
    const response = await fetch(url);
    if (response.status === 401) {
      window.location.href = SIGN_IN;
      throw new Error("Please sign in as the owner first.");
    }
    if (!response.ok) throw new Error("The preview couldn't load. Please try again.");
    return response.json();
  }

  /** The services as a menu: grouped by category, in the document's order. Returns the categories. */
  function services(list) {
    const groups = new Map();
    list.forEach((service) => {
      const kind = service.category || "Services";
      if (!groups.has(kind)) groups.set(kind, []);
      groups.get(kind).push(service);
    });
    $("services-list").replaceChildren(...[...groups].map(([kind, items]) => {
      const group = el("div", "group");
      group.append(el("h3", "", kind));
      items.forEach((service) => {
        const row = el("div", "item");
        row.append(el("span", "name", service.name), el("span", "dots"),
          el("span", "length", service.detail), el("span", "price", service.price));
        group.append(row);
      });
      return group;
    }));
    return [...groups.keys()];
  }

  function team(names) {
    $("team").hidden = !names.length;
    $("team-list").replaceChildren(...names.map((name) => {
      const person = el("li");
      person.append(el("span", "face", name.charAt(0)), document.createTextNode(name));
      return person;
    }));
  }

  function visit(site) {
    $("hours-list").replaceChildren(...site.hours.map((day) => {
      const row = el("tr");
      row.append(el("td", "", day.day), el("td", "", day.time));
      return row;
    }));
    const contact = [el("strong", "", site.name)];
    [site.address, site.phone, site.email].filter(Boolean).forEach((line) => contact.push(el("span", "", line)));
    $("contact").replaceChildren(...contact);
  }

  /** The stand-in website, from the business's own facts. */
  function fill(site) {
    document.title = `${site.name} · Preview`;
    $("nav-name").textContent = $("site-name").textContent = site.name;
    const kinds = services(site.services);
    $("site-kinds").textContent = kinds.slice(0, KINDS_SHOWN).join(" · ");
    $("site-phone").textContent = site.phone ? `Call ${site.phone}` : "";
    team(site.team);
    visit(site);
    $("site-foot").textContent = [site.name, site.address].filter(Boolean).join(" · ");
  }

  /** The widget, added as the business's snippet adds it. */
  function addWidget(key) {
    const tag = document.createElement("script");
    tag.src = "/web/widget/chat.js";
    tag.dataset.business = key;
    tag.dataset.open = "true";
    document.body.append(tag);
  }

  async function start() {
    try {
      const { key, site } = await json("/api/onboarding/preview");
      fill(site);
      addWidget(key);
    } catch (failed) {
      $("preview-error").textContent = failed.message;
    }
  }

  $("another").addEventListener("click", () => window.open(window.location.href, "_blank", "noopener"));
  start();
})();

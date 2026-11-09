/* The owner's preview (D33): their website stand-in, with the chat widget added
   the way their snippet adds it.

   1. GET /api/onboarding/preview: the widget key (owner sign-in; without it, sign in first)
   2. GET /api/widget/business: the business's name and greeting, as the widget shows them
   3. the widget's one script tag, with the key, opened

   The widget makes up a new conversation each time the page loads, so
   "Open another customer" opens this page again in a new tab: a second
   customer, for trying the empty chair. Text is always set as text, never HTML. */

(() => {
  const SIGN_IN = "/login?next=/web/preview.html";
  const $ = (id) => document.getElementById(id);

  async function json(url) {
    const response = await fetch(url);
    if (response.status === 401) {
      window.location.href = SIGN_IN;
      throw new Error("Please sign in as the owner first.");
    }
    if (!response.ok) throw new Error("The preview couldn't load. Please try again.");
    return response.json();
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
      const { key } = await json("/api/onboarding/preview");
      const business = await json(`/api/widget/business?key=${encodeURIComponent(key)}`);
      $("site-name").textContent = business.name;
      $("site-greeting").textContent = business.greeting;
      document.title = `${business.name} · Preview`;
      addWidget(key);
    } catch (failed) {
      $("preview-error").textContent = failed.message;
    }
  }

  $("another").addEventListener("click", () => window.open(window.location.href, "_blank", "noopener"));
  start();
})();

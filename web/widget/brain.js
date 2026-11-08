/* The widget's brain: the business's real Front Desk agent, on the SmartDesk
   server this script came from.

     business(key)  -> Promise<{ name, greeting, suggestions } | null>
                       null when the key is not set up (the server says 404)
     reply(text)    -> Promise<{ answer, items, suggestions }>
                       one turn of the conversation (POST /api/assistant)
     offer()        -> Promise<{ text, suggestions } | null>
                       a slot offered to this chat's customer from the waitlist,
                       once (GET /api/widget/offer)

   The conversation is one "thread": an id made up when the page loads and
   sent with every message, which is how the agent remembers what was said. */

window.SmartDeskBrain = (() => {
  const server = new URL(document.currentScript.src).origin;
  const thread = "w-" + crypto.randomUUID();

  async function business(key) {
    const response = await fetch(`${server}/api/widget/business?key=${encodeURIComponent(key)}`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error(`business: ${response.status}`);
    return response.json();
  }

  async function reply(text) {
    const response = await fetch(`${server}/api/assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ thread, message: text }),
    });
    if (!response.ok) throw new Error(`assistant: ${response.status}`);
    return response.json();
  }

  async function offer() {
    const response = await fetch(`${server}/api/widget/offer?thread=${encodeURIComponent(thread)}`);
    return response.ok ? response.json() : null;
  }

  return { business, reply, offer };
})();

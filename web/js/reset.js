/* The business onboarded here, in a small card at the top right of the header, with
   a way to start over (development only). The card shows only when a business has
   gone live here (GET /api/onboarding/live, the owner's only): never for nothing.

   Reset: a small panel under the card asks for the business's name; the server
   takes the phone setup down, deletes the bookings on its calendars (keeping the
   calendars, still shared), and
   forgets the onboarded document, the waitlist and any upload not yet live
   (POST /api/onboarding/reset), and says what it removed; each is
   shown as done, the card goes away, and the owner goes back to the first step.
   Going live shows the card (SD.showLive, from complete.js). Rules in
   docs/workflows/go-live.md, part C. */

(() => {
  const card = document.getElementById("live-card");
  const start = document.getElementById("reset-start");
  const panel = document.getElementById("reset-confirm");
  const prompt = document.getElementById("reset-prompt");
  const nameInput = document.getElementById("reset-name");
  const go = document.getElementById("reset-go");
  const error = document.getElementById("reset-error");
  const progress = document.getElementById("reset-progress");
  let business = "";  // the name to type: the business live now

  function show(state) {   // "idle" · "confirm" · "done"
    panel.hidden = state === "idle";
    nameInput.closest("label").hidden = state === "done";
    go.closest(".reset-actions").hidden = state === "done";
    progress.hidden = state !== "done";
    start.disabled = state !== "idle";
  }

  /** Show the card when a business is live here; hide it otherwise (or before sign-in). */
  SD.showLive = async () => {
    try {
      const response = await fetch("/api/onboarding/live");
      const { live, name } = response.ok ? await response.json() : { live: false, name: "" };
      business = name;
      document.getElementById("live-name").textContent = name;
      card.hidden = !live;
    } catch {
      card.hidden = true;
    }
  };

  start.addEventListener("click", () => {
    error.textContent = "";
    progress.replaceChildren();  // nothing from an earlier reset
    prompt.textContent = `Type "${business}" to confirm.`;
    nameInput.value = "";
    go.disabled = true;
    show("confirm");
    nameInput.focus();
  });

  // The button works only once the name matches exactly; the server checks again.
  nameInput.addEventListener("input", () => { go.disabled = nameInput.value !== business; });
  document.getElementById("reset-cancel").addEventListener("click", () => show("idle"));

  go.addEventListener("click", async () => {
    go.disabled = true;
    let response;
    try {
      response = await fetch("/api/onboarding/reset", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: nameInput.value }),
      });
    } catch {
      error.textContent = "The server could not be reached. Please try again.";
      go.disabled = false;
      return;
    }
    if (!response.ok) {
      const { detail } = await response.json().catch(() => ({}));
      error.textContent = typeof detail === "string" ? detail : "The reset did not go through.";
      go.disabled = false;
      return;
    }
    const { removed } = await response.json();
    const lines = [...removed.map((what) => `Removed the ${what}`), "Ready to onboard again"];
    progress.replaceChildren(...lines.map((text) => {
      const line = SD.el("li");
      line.append(SD.el("span", text), SD.el("span", "Done", "stage"));
      line.classList.add("done");
      return line;
    }));
    show("done");
    setTimeout(() => {
      show("idle");
      card.hidden = true;
      SD.restart();  // every step empty: nothing of the business just reset stays on the page
    }, 1500);
  });

  show("idle");
  SD.showLive();
})();

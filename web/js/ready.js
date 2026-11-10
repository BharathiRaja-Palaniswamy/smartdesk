/* Step 3: SmartDesk reads the documents as they are and checks they are safe
   for customers (D31). It asks the owner nothing about the business.

   1. POST /api/onboarding/read: the documents' text, cleaned of anything a page could run
   2. POST /api/onboarding/check: harmful content, or text telling an assistant what to do
   3. safe: POST /api/onboarding/booking reads the services, team and hours, in any
      layout (D35); flagged: what was found, in the document's own words, "Upload
      again", and "Go live" disabled
   4. "Go live": POST /api/onboarding/go-live with the business's phone number, which
      its assistant then answers (D37); the website chat goes live either way

   While it works, one plain line says which step is running; a long step adds
   "Almost done" after a while. Text is always set as text, never HTML. */

(() => {
  const SIGN_IN = "/login?next=/web/onboard.html";
  const ALMOST_DONE_AFTER = 8;  // seconds into the last step before the line says "Almost done"
  const $ = (id) => document.getElementById(id);
  const error = $("ready-error");

  /** A failed request as words for the owner; a missing sign-in sends them to sign in. */
  async function failure(response) {
    if (response.status === 401) {
      window.location.href = SIGN_IN;
      return "Please sign in as the owner first.";
    }
    try {
      const { detail } = await response.json();
      return typeof detail === "string" ? detail : "Something in the request was not right.";
    } catch {
      return "Something went wrong. Please try again.";
    }
  }

  async function post(url, body) {
    const response = await fetch(url, { method: "POST", ...body });
    if (!response.ok) throw new Error(await failure(response));
    return response.json();
  }

  /** The status line: what is happening now, or how it ended ("done", "stopped"). */
  function status(text, state = "working") {
    $("status-text").textContent = text;
    $("status").className = `status ${state}`;
  }

  /** The line for a long step, then "Almost done" if it runs on; returns what stops the timer. */
  function longStep(text) {
    status(text);
    const timer = setTimeout(() => status("Almost done"), ALMOST_DONE_AFTER * 1000);
    return () => clearTimeout(timer);
  }

  function showFindings(findings) {
    $("findings").replaceChildren(...findings.map((f) => {
      const item = SD.el("li");
      item.append(SD.el("span", f.why, "why"), SD.el("q", f.quote));
      return item;
    }));
    $("flagged").hidden = false;
  }

  function finish(title, intro, canGoLive) {
    $("ready-title").textContent = title;
    $("ready-intro").textContent = intro;
    $("go-live").disabled = !canGoLive;
    $("ready-actions").hidden = false;
  }

  SD.enter.ready = async () => {
    error.textContent = "";
    $("problems").replaceChildren();
    $("flagged").hidden = true;
    $("ready-actions").hidden = true;
    $("go-live").disabled = true;
    $("ready-title").textContent = "Getting your assistant ready";
    $("ready-intro").textContent = "This takes a few seconds.";
    status("Reading your documents");
    let stop = () => {};
    try {
      const form = new FormData();
      SD.files.forEach(({ file }) => form.append("files", file));
      form.append("business", SD.business.name);
      const read = await post("/api/onboarding/read", { body: form });
      $("problems").replaceChildren(...read.problems.map((text) => SD.el("li", text)));
      status("Checking it's safe for your customers");
      const checked = await post("/api/onboarding/check", {});
      if (checked.safe) {
        stop = longStep("Understanding your services and team");
        const bookable = await post("/api/onboarding/booking", {});
        stop();
        $("problems").append(...bookable.problems.map((text) => SD.el("li", text)));
        status(bookable.headline, "done");
        finish("All set", "Your assistant will answer and book from your documents.", true);
      } else {
        status("We can't use this document yet", "stopped");
        showFindings(checked.findings);
        finish("Please check your document", "Fix the parts below and upload it again.", false);
      }
    } catch (failed) {
      stop();
      status("Stopped", "stopped");
      error.textContent = failed.message || "The server could not be reached. Please try again.";
      finish("Something went wrong", "Nothing was changed. Please try again.", false);
    }
  };

  $("go-live").addEventListener("click", async () => {
    error.textContent = "";
    $("go-live").disabled = true;
    status("Setting up your website chat, phone and calendars");
    try {
      const live = await post("/api/onboarding/go-live", {
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ number: SD.business.phone || "" }),
      });
      SD.snippet = live.snippet;
      SD.phone = live.phone;
      SD.phoneProblem = live.phone_problem;
      SD.calendars = live.calendars;
      SD.go("complete");
    } catch (failed) {
      status("Stopped", "stopped");
      error.textContent = failed.message || "The server could not be reached. Please try again.";
      $("go-live").disabled = false;  // the owner may try again
    }
  });
})();

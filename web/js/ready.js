/* Step 3: SmartDesk reads the documents as they are and checks they are safe
   for customers (D31). It asks the owner nothing about the business.

   1. POST /api/onboarding/read: the documents' text, cleaned of anything a page could run
   2. POST /api/onboarding/check: harmful content, or text telling an assistant what to do
   3. safe: "Proceed" to the phone step (phone.js), which goes live; flagged: what was
      found, in the document's own words, "Upload again", and "Proceed" disabled

   While it works, one plain line says what is happening. The check is one
   request, so its lines ("Understanding your business", "Checking it's safe",
   "Almost done") move on with time while it runs. Text is always set as text, never HTML. */

(() => {
  const SIGN_IN = "/login?next=/web/onboard.html";
  const DURING_CHECK = [  // [seconds into the check, what the line says]
    [0, "Understanding your business"],
    [4, "Checking it's safe for your customers"],
    [10, "Almost done"],
  ];
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

  /** The check's lines, moved on with time; returns what stops them. */
  function duringCheck() {
    const timers = DURING_CHECK.map(([seconds, text]) => setTimeout(() => status(text), seconds * 1000));
    return () => timers.forEach(clearTimeout);
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
    $("proceed").disabled = !canGoLive;
    $("ready-actions").hidden = false;
  }

  SD.enter.ready = async () => {
    error.textContent = "";
    $("problems").replaceChildren();
    $("flagged").hidden = true;
    $("ready-actions").hidden = true;
    $("proceed").disabled = true;
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
      stop = duringCheck();
      const checked = await post("/api/onboarding/check", {});
      stop();
      if (checked.safe) {
        status("Your documents are ready", "done");
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

  // The server checks again on going live; this only moves to the next step.
  $("proceed").addEventListener("click", () => SD.go("calls"));
})();

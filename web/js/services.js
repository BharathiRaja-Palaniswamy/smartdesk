/* Step 3: read the documents, then the services table the owner checks.

   The documents and the business's name go to the server
   (POST /api/onboarding/read), which reads them and has a model list what
   can be booked; the server keeps only what the documents' own words back
   up (smartdesk/onboarding/services.py). Each row shows where it came from.

   Booking uses this table, so every row is checked here: a name, and a length
   and price that are above 0 or left empty. A service left without a length
   or price stays listed but can't be booked; nothing is guessed.

   "Save and finish" makes the business live (POST /api/onboarding/go-live). */

(() => {
  const progress = document.getElementById("progress");
  const ready = document.getElementById("services-ready");
  const rows = document.getElementById("services-rows");
  const error = document.getElementById("services-error");
  const problems = document.getElementById("services-problems");
  const next = document.getElementById("services-next");
  const SIGN_IN = "/login?next=/web/onboard.html";

  function cell(input) {
    const td = SD.el("td");
    td.append(input);
    return td;
  }

  function field(type, value, label) {
    const input = SD.el("input");
    input.type = type;
    input.value = value ?? "";
    input.setAttribute("aria-label", label);
    if (type === "number") { input.min = "1"; input.step = "1"; }
    return input;
  }

  /** One editable row; `quote` is the document's words it came from ("" when added by the owner). */
  function addRow(service) {
    const tr = SD.el("tr");
    tr.dataset.quote = service.quote || "";
    tr.dataset.category = service.category || "";
    const name = field("text", service.name, "Service");
    const minutes = field("number", service.minutes, "Duration in minutes");
    const price = field("number", service.price, "Price in dollars");
    minutes.placeholder = price.placeholder = "missing";
    const from = SD.el("span", service.quote ? "Your document" : "Added by you", "from");
    if (service.quote) from.title = service.quote;  // hover to see the words it came from
    const remove = SD.el("button", "Remove", "link");
    remove.type = "button";
    remove.addEventListener("click", () => tr.remove());
    tr.append(cell(name), cell(minutes), cell(price), cell(from), cell(remove));
    rows.append(tr);
    return name;
  }

  /** The table as data, or the first problem found. */
  function table() {
    const services = [];
    for (const [i, tr] of [...rows.children].entries()) {
      const [name, minutes, price] = tr.querySelectorAll("input");
      const row = i + 1;
      if (!name.value.trim()) return { problem: `Row ${row}: add the service's name.` };
      const mins = minutes.value === "" ? null : Number(minutes.value);
      if (mins !== null && !(Number.isInteger(mins) && mins >= 5 && mins <= 600)) {
        return { problem: `Row ${row}: the length should be whole minutes, 5 to 600, or left empty.` };
      }
      const cost = price.value === "" ? null : Number(price.value);
      if (cost !== null && !(cost > 0)) return { problem: `Row ${row}: the price should be above 0, or left empty.` };
      services.push({ name: name.value.trim(), category: tr.dataset.category, minutes: mins, price: cost,
                      quote: tr.dataset.quote });
    }
    if (!services.length) return { problem: "Add at least one service." };
    return { services };
  }

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

  function status(text, done) {
    progress.replaceChildren(...SD.files.map(({ file }) => {
      const line = SD.el("li");
      line.append(SD.el("span", file.name), SD.el("span", text, "stage"));
      line.classList.toggle("done", done);
      return line;
    }));
  }

  SD.enter.services = async () => {
    error.textContent = "";
    problems.replaceChildren();
    rows.replaceChildren();
    ready.hidden = true;
    status("Reading…", false);
    const form = new FormData();
    SD.files.forEach(({ file }) => form.append("files", file));
    form.append("business", SD.business.name);
    let response;
    try {
      response = await fetch("/api/onboarding/read", { method: "POST", body: form });
    } catch {
      status("Not read", false);
      error.textContent = "The server could not be reached. Please try again.";
      return;
    }
    if (!response.ok) {
      status("Not read", false);
      error.textContent = await failure(response);
      return;
    }
    const answer = await response.json();
    status("Ready", true);
    answer.services.forEach(addRow);
    problems.replaceChildren(...answer.problems.map((text) => SD.el("li", text)));
    ready.hidden = false;
  };

  document.getElementById("add-service").addEventListener("click", () => {
    addRow({ name: "", minutes: null, price: null, quote: "" }).focus();
  });

  next.addEventListener("click", async () => {
    const { services, problem } = table();
    if (problem) { error.textContent = problem; return; }
    error.textContent = "";
    next.disabled = true;
    try {
      const response = await fetch("/api/onboarding/go-live", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ services }),
      });
      if (!response.ok) { error.textContent = await failure(response); return; }
      SD.services = services;
      SD.snippet = (await response.json()).snippet;
      SD.go("complete");
    } catch {
      error.textContent = "The server could not be reached. Please try again.";
    } finally {
      next.disabled = false;
    }
  });
})();

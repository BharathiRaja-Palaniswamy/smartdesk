/* Step 3: each document's progress, then the services table the owner checks.
   Booking uses this table, so every row is checked here: a name, a positive
   duration, and a price or none. A service with no price stays listed but
   can't be booked; nothing is guessed.

   Until document reading is connected (docs/workflows/onboarding.md, steps
   2–8), progress is simulated and the table starts with example rows,
   marked "Example" so they are never mistaken for what a file says. */

(() => {
  const progress = document.getElementById("progress");
  const ready = document.getElementById("services-ready");
  const rows = document.getElementById("services-rows");
  const error = document.getElementById("services-error");

  const STAGES = ["Reading", "Hiding personal details", "Finding services", "Ready"];
  const EXAMPLES = [
    { name: "Swedish massage", minutes: 60, price: 115 },
    { name: "Swedish massage", minutes: 90, price: 160 },
    { name: "Deep tissue massage", minutes: 60, price: 130 },
    { name: "Signature facial", minutes: 60, price: 120 },
    { name: "Gift wrap add-on", minutes: 15, price: null },   // shows abstention: no price stated
  ];

  /** Every document moves through the stages; a little apart, as real work would. */
  function play(done) {
    const lines = SD.files.map(({ file }) => {
      const line = SD.el("li");
      const name = SD.el("span", file.name);
      const stage = SD.el("span", "Waiting", "stage");
      line.append(name, stage);
      progress.append(line);
      return { line, stage };
    });
    let tick = 0;
    const timer = setInterval(() => {
      tick += 1;
      lines.forEach(({ line, stage }, i) => {
        const at = Math.min(Math.max(tick - i, 0), STAGES.length - 1);
        stage.textContent = tick - i < 0 ? "Waiting" : STAGES[at];
        line.classList.toggle("done", at === STAGES.length - 1);
      });
      if (lines.every(({ line }) => line.classList.contains("done"))) {
        clearInterval(timer);
        done();
      }
    }, 600);
  }

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

  /** One editable row. `source` says where it came from: "Example" or "Added by you". */
  function addRow(service, source) {
    const tr = SD.el("tr");
    const name = field("text", service.name, "Service");
    const minutes = field("number", service.minutes, "Duration in minutes");
    const price = field("number", service.price, "Price in dollars");
    price.placeholder = "missing";
    const remove = SD.el("button", "Remove", "link");
    remove.type = "button";
    remove.addEventListener("click", () => tr.remove());
    tr.append(cell(name), cell(minutes), cell(price), cell(SD.el("span", source, "from")), cell(remove));
    rows.append(tr);
    return name;
  }

  /** The table as data, or the first problem found. */
  function read() {
    const services = [];
    for (const [i, tr] of [...rows.children].entries()) {
      const [name, minutes, price] = tr.querySelectorAll("input");
      const row = i + 1;
      if (!name.value.trim()) return { problem: `Row ${row}: add the service's name.` };
      const mins = Number(minutes.value);
      if (!Number.isInteger(mins) || mins <= 0) return { problem: `Row ${row}: the duration should be whole minutes, above 0.` };
      const cost = price.value === "" ? null : Number(price.value);
      if (cost !== null && !(cost > 0)) return { problem: `Row ${row}: the price should be above 0, or left empty.` };
      services.push({ name: name.value.trim(), minutes: mins, price: cost });
    }
    if (!services.length) return { problem: "Add at least one service." };
    return { services };
  }

  SD.enter.services = () => {
    error.textContent = "";
    progress.replaceChildren();
    rows.replaceChildren();
    ready.hidden = true;
    play(() => {
      EXAMPLES.forEach((service) => addRow(service, "Example"));
      ready.hidden = false;
    });
  };

  document.getElementById("add-service").addEventListener("click", () => {
    addRow({ name: "", minutes: "", price: null }, "Added by you").focus();
  });

  document.getElementById("services-next").addEventListener("click", () => {
    const { services, problem } = read();
    if (problem) { error.textContent = problem; return; }
    error.textContent = "";
    SD.services = services;
    SD.go("complete");
  });
})();

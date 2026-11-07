/* Reset: empty this business's cell (reset onboarding) or remove it (delete
   business), showing each step like setup does. Steps and rules are in
   docs/workflows/go-live.md, parts C and D: confirmed by typing the business
   name, the assistant paused first, and a final check that nothing is left.

   In this preview nothing is stored, so the steps are simulated; with the
   backend each line follows the server's progress, and a failed step offers
   Retry from that step. */

(() => {
  const PLANS = {
    onboarding: {
      button: "Reset onboarding",
      steps: ["Pause the assistant", "Stop documents still processing", "Remove search entries",
              "Remove sections and services", "Remove uploaded files", "Check the cell is empty",
              "Ready to onboard again"],
      after() {          // basics stay; documents and services go
        SD.files = [];
        SD.services = [];
        SD.go("upload");
      },
    },
    business: {
      button: "Delete business",
      steps: ["Pause the assistant", "Disconnect the widget key", "Detach the phone number",
              "Remove calendar access", "Remove search", "Remove traces",
              "Remove database and files", "Remove from the registry", "Check nothing is left"],
      after() {          // back to an empty sign-up form
        SD.business = {};
        SD.files = [];
        SD.services = [];
        document.getElementById("business-form").reset();
        SD.go("business");
      },
    },
  };

  const confirmBox = document.getElementById("reset-confirm");
  const prompt = document.getElementById("reset-prompt");
  const nameInput = document.getElementById("reset-name");
  const go = document.getElementById("reset-go");
  const progress = document.getElementById("reset-progress");
  const starters = document.querySelectorAll("[data-reset]");
  let plan = null;

  function show(state) {   // "idle" · "confirm" · "running"
    confirmBox.hidden = state !== "confirm";
    progress.hidden = state !== "running";
    starters.forEach((button) => { button.disabled = state !== "idle"; });
  }

  starters.forEach((button) => button.addEventListener("click", () => {
    plan = PLANS[button.dataset.reset];
    prompt.textContent = `Type "${SD.business.name}" to confirm.`;
    nameInput.value = "";
    go.textContent = plan.button;
    go.disabled = true;
    show("confirm");
    nameInput.focus();
  }));

  // The button works only once the name matches exactly.
  nameInput.addEventListener("input", () => { go.disabled = nameInput.value !== SD.business.name; });
  document.getElementById("reset-cancel").addEventListener("click", () => show("idle"));

  go.addEventListener("click", () => {
    if (nameInput.value !== SD.business.name) return;
    show("running");
    const lines = plan.steps.map((step) => {
      const line = SD.el("li");
      const status = SD.el("span", "Waiting", "stage");
      line.append(SD.el("span", step), status);
      progress.append(line);
      return { line, status };
    });
    let at = 0;
    const timer = setInterval(() => {
      if (at > 0) {
        lines[at - 1].status.textContent = "Done";
        lines[at - 1].line.classList.add("done");
      }
      if (at === lines.length) {
        clearInterval(timer);
        setTimeout(() => {
          progress.replaceChildren();
          show("idle");
          plan.after();
        }, 900);
        return;
      }
      lines[at].status.textContent = "Working…";
      at += 1;
    }, 500);
  });

  show("idle");
})();

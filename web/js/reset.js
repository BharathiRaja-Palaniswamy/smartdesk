/* Reset onboarding (development only): start over, after typing the
   business's name. The server forgets the onboarded document and services
   table (POST /api/onboarding/reset) and says what it removed; each is shown
   as done, and the owner goes back to the documents step, basics kept.
   Rules in docs/workflows/go-live.md, part C. */

(() => {
  const start = document.getElementById("reset-start");
  const confirmBox = document.getElementById("reset-confirm");
  const prompt = document.getElementById("reset-prompt");
  const nameInput = document.getElementById("reset-name");
  const go = document.getElementById("reset-go");
  const error = document.getElementById("reset-error");
  const progress = document.getElementById("reset-progress");

  function show(state) {   // "idle" · "confirm" · "done"
    confirmBox.hidden = state !== "confirm";
    progress.hidden = state !== "done";
    start.disabled = state !== "idle";
  }

  start.addEventListener("click", () => {
    prompt.textContent = `Type "${SD.business.name}" to confirm.`;
    nameInput.value = "";
    go.disabled = true;
    error.textContent = "";
    show("confirm");
    nameInput.focus();
  });

  // The button works only once the name matches exactly; the server checks again.
  nameInput.addEventListener("input", () => { go.disabled = nameInput.value !== SD.business.name; });
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
      SD.files = [];
      SD.services = [];
      SD.go("upload");
    }, 1500);
  });

  show("idle");
})();

/* Step 4 ("calls"): phone support (D32). The owner chooses whether calls are answered too;
   a yes shows the line's cost, which they must agree to. "Go live" sends the
   choice (POST /api/onboarding/go-live): the server checks the documents again,
   gives the line, and makes the business live, all or nothing.

   GET /api/onboarding/phone says whether a line can be given now and what it
   costs; when none can be, only "No" is offered. Text is always set as text. */

(() => {
  const $ = (id) => document.getElementById(id);
  const error = $("phone-error");
  const yes = document.querySelector('input[name="phone"][value="yes"]');
  let offer = { available: false };

  /** The cost box and the Go live button follow the choice and the agreement. */
  function update() {
    $("phone-cost").hidden = !yes.checked;
    $("go-live").disabled = yes.checked && !$("agree-cost").checked;
  }

  SD.enter.calls = async () => {
    error.textContent = "";
    try {
      const response = await fetch("/api/onboarding/phone");
      if (response.ok) offer = await response.json();
    } catch {
      offer = { available: false };
    }
    yes.disabled = !offer.available;
    $("phone-unavailable").hidden = offer.available;
    if (!offer.available) document.querySelector('input[name="phone"][value="no"]').checked = true;
    else $("phone-price").textContent = `$${offer.monthly.toFixed(2)} a month for the number, with the first month free, `
      + `plus about ${(offer.per_minute * 100).toFixed(2)} cents a minute of calls answered.`;
    update();
  };

  document.querySelectorAll('input[name="phone"], #agree-cost').forEach((input) => input.addEventListener("change", update));

  $("go-live").addEventListener("click", async () => {
    error.textContent = "";
    $("go-live").disabled = true;
    try {
      const response = await fetch("/api/onboarding/go-live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: yes.checked, agree_cost: $("agree-cost").checked }),
      });
      const answer = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(typeof answer.detail === "string" ? answer.detail : "Something went wrong. Please try again.");
      SD.snippet = answer.snippet;
      SD.phone = answer.phone;
      SD.go("complete");
    } catch (failed) {
      error.textContent = failed.message || "The server could not be reached. Please try again.";
      update();
    }
  });
})();

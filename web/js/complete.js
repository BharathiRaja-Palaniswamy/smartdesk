/* Step 5: live. Shows the snippet that puts the chat on the owner's website,
   as the server gave it at Go live (POST /api/onboarding/go-live, ready.js), the
   business's number now answered by its assistant, or why it is not yet, its
   staff calendars made ready, and the way to the website preview (preview.html). */

(() => {
  const snippet = document.getElementById("snippet");
  const copy = document.getElementById("copy");

  SD.enter.complete = () => {
    document.getElementById("done-title").textContent = `${SD.business.name} is live`;
    snippet.textContent = SD.snippet;
    document.getElementById("phone-number").textContent = SD.phone || "Not answered yet";
    document.getElementById("phone-note").textContent = SD.phone
      ? "Your assistant answers this number, and calls waitlisted customers when a slot opens."
      : SD.phoneProblem || "";
    document.getElementById("calendars-note").textContent = SD.calendars || "";
    SD.showLive();  // the business is live now: its card shows in the header (reset.js)
    copy.textContent = "Copy snippet";
  };

  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(snippet.textContent);
      copy.textContent = "Copied";
    } catch {
      copy.textContent = "Select the text above to copy it";
    }
  });
})();

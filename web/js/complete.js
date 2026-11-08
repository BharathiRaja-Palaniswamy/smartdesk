/* Step 4: live. Shows the snippet that puts the chat on the owner's website,
   as the server gave it at Go live (POST /api/onboarding/go-live), and a
   link to try the assistant on a sample page. */

(() => {
  const snippet = document.getElementById("snippet");
  const copy = document.getElementById("copy");

  SD.enter.complete = () => {
    document.getElementById("done-title").textContent = `${SD.business.name} is live`;
    snippet.textContent = SD.snippet;
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

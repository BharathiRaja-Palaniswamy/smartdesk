/* Step 5: live. Shows the snippet that puts the chat on the owner's website,
   as the server gave it at Go live (POST /api/onboarding/go-live, phone.js),
   the phone line with how to forward calls to it when the owner chose phone
   support, and the way to the website preview (preview.html). */

(() => {
  const snippet = document.getElementById("snippet");
  const copy = document.getElementById("copy");

  SD.enter.complete = () => {
    document.getElementById("done-title").textContent = `${SD.business.name} is live`;
    snippet.textContent = SD.snippet;
    document.getElementById("phone-done").hidden = !SD.phone;
    document.getElementById("phone-number").textContent = SD.phone || "";
    document.getElementById("next-phone").hidden = Boolean(SD.phone);
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

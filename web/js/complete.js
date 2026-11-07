/* Step 4: done. Shows the snippet that puts the chat on the owner's site.
   The key is a placeholder until businesses are stored on the server; the
   real key will only work on the website given in step 1. */

(() => {
  const snippet = document.getElementById("snippet");
  const copy = document.getElementById("copy");

  function placeholderKey() {
    const bytes = crypto.getRandomValues(new Uint8Array(6));
    return "pub_" + [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  SD.enter.complete = () => {
    document.getElementById("done-title").textContent = `${SD.business.name} is set up`;
    snippet.textContent =
      `<script src="https://widget.smartdesk.example/chat.js"\n` +
      `        data-business="${placeholderKey()}" defer></script>`;
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

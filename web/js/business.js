/* Step 1: the business basics. Name, type and phone are required: the phone number
   is the one customers call, which the assistant answers (D37). Opening hours are
   not asked: they are read from the business's documents (onboarding/booking.py). */

(() => {
  const form = document.getElementById("business-form");
  const error = document.getElementById("business-error");
  const required = { name: "the business name", kind: "the type of business", phone: "your business phone number" };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const answers = Object.fromEntries(
      [...new FormData(form)].map(([key, value]) => [key, String(value).trim()]));

    const missing = Object.keys(required).filter((key) => !answers[key]);
    if (missing.length) {
      error.textContent = `Please add ${missing.map((key) => required[key]).join(", ")}.`;
      form.elements[missing[0]].focus();
      return;
    }
    if (answers.website && !/^https?:\/\/[^\s.]+\.[^\s]+$/i.test(answers.website)) {
      error.textContent = "The website should look like https://yourbusiness.com";
      form.elements.website.focus();
      return;
    }
    error.textContent = "";
    SD.business = answers;
    SD.go("upload");
  });
})();

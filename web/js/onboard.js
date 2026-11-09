/* Onboarding: what the owner has told us so far, and moving between steps.
   Each step has its own file (business.js, upload.js, ready.js, phone.js, complete.js);
   they share this one object, SD. The documents are read and checked on the server (ready.js). */

const SD = {
  steps: ["business", "upload", "ready", "calls", "complete"],
  business: {},   // step 1's answers
  files: [],      // step 2's accepted files: { file, kind }
  enter: {},      // step name -> function run when that step opens

  /** Show one step and mark the stepper. */
  go(name) {
    const at = SD.steps.indexOf(name);
    SD.steps.forEach((step, i) => {
      document.getElementById(step).classList.toggle("now", step === name);
      const mark = document.querySelector(`.stepper [data-for="${step}"]`);
      mark.classList.toggle("now", i === at);
      mark.classList.toggle("done", i < at);
    });
    window.scrollTo({ top: 0 });
    if (SD.enter[name]) SD.enter[name]();
  },

  /** A text element, safely: owner's words are always text, never HTML. */
  el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  },
};

// Every "Back" button goes to the step before its own.
document.querySelectorAll("[data-back]").forEach((button) => {
  button.addEventListener("click", () => {
    const here = button.closest(".step").id;
    SD.go(SD.steps[SD.steps.indexOf(here) - 1]);
  });
});

document.addEventListener("DOMContentLoaded", () => SD.go("business"));

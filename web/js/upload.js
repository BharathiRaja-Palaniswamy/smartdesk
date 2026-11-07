/* Step 2: choose documents. Each file is checked by type and size here, to
   the limits in docs/workflows/onboarding.md. The server checks again, and
   more (the real type from the contents, page count), since a browser check
   can be bypassed. */

(() => {
  const MB = 1024 * 1024;
  const KINDS = {
    document: { ext: ["pdf", "docx", "txt", "md", "csv"], max: 50 * MB, limit: "50 MB" },
    image: { ext: ["jpg", "jpeg", "png"], max: 10 * MB, limit: "10 MB" },
  };
  const MAX_FILES = 30;

  const input = document.getElementById("file-input");
  const drop = document.getElementById("drop");
  const list = document.getElementById("files");
  const authorized = document.getElementById("authorized");
  const error = document.getElementById("upload-error");
  let rejected = [];   // { name, why }, shown so the owner knows what was left out

  /** Which kind a file is, and why it can't be used ("" when it can). */
  function check(file) {
    const ext = file.name.split(".").pop().toLowerCase();
    const kind = Object.keys(KINDS).find((k) => KINDS[k].ext.includes(ext));
    if (!kind) return { kind: "", why: "this file type isn't supported" };
    if (file.size > KINDS[kind].max) return { kind, why: `larger than ${KINDS[kind].limit}` };
    if (file.size === 0) return { kind, why: "the file is empty" };
    return { kind, why: "" };
  }

  function add(files) {
    for (const file of files) {
      const { kind, why } = check(file);
      const duplicate = SD.files.some((f) => f.file.name === file.name && f.file.size === file.size);
      if (why) rejected.push({ name: file.name, why });
      else if (SD.files.length >= MAX_FILES) rejected.push({ name: file.name, why: `more than ${MAX_FILES} files` });
      else if (!duplicate) SD.files.push({ file, kind });
    }
    show();
  }

  function show() {
    list.replaceChildren();
    SD.files.forEach((entry, i) => {
      const row = SD.el("li");
      const name = SD.el("span");
      name.append(SD.el("span", entry.kind, "kind"), " ", entry.file.name);
      const remove = SD.el("button", "Remove");
      remove.type = "button";
      remove.addEventListener("click", () => { SD.files.splice(i, 1); show(); });
      row.append(name, remove);
      list.append(row);
    });
    rejected.forEach(({ name, why }) => list.append(SD.el("li", `${name}: not added, ${why}`, "rejected")));
    rejected = [];
  }

  input.addEventListener("change", () => { add(input.files); input.value = ""; });
  ["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (event) => {
    event.preventDefault();
    drop.classList.add("over");
  }));
  ["dragleave", "drop"].forEach((type) => drop.addEventListener(type, () => drop.classList.remove("over")));
  drop.addEventListener("drop", (event) => { event.preventDefault(); add(event.dataTransfer.files); });

  document.getElementById("upload-next").addEventListener("click", () => {
    if (!SD.files.length) { error.textContent = "Add at least one document."; return; }
    if (!authorized.checked) { error.textContent = "Please confirm you're authorized to share these files."; return; }
    error.textContent = "";
    SD.go("services");
  });
})();

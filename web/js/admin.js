/* Admin console preview: the businesses list, filters, and the summary above it.
   Text is always set as text, never HTML. Actions are a preview: they change
   the row on this page only (the real ones are logged on the server). */

(() => {
  const ORDER = { failed: 0, paused: 1, live: 2, draft: 3 };  // what needs help first
  const businesses = window.ADMIN_SAMPLE.map((b) => ({ ...b }));
  const rows = document.getElementById("rows");
  const statusFilter = document.getElementById("status-filter");
  const search = document.getElementById("search");

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function td(...children) {
    const cell = el("td");
    cell.append(...children);
    return cell;
  }

  function summary() {
    const count = (status) => businesses.filter((b) => b.status === status).length;
    const box = document.getElementById("summary");
    box.replaceChildren(...[
      ["Businesses", businesses.length], ["Live", count("live")], ["Need help", count("failed") + count("paused")],
      ["Chats, 7 days", businesses.reduce((n, b) => n + b.chats, 0)],
      ["Cost today", "$" + businesses.reduce((n, b) => n + b.cost, 0).toFixed(2)],
    ].map(([label, value]) => {
      const tile = el("div", undefined, "tile");
      tile.append(el("span", String(value), "value"), el("span", label, "label"));
      return tile;
    }));
  }

  function channels(b) {
    const list = el("div", undefined, "stack");
    list.append(el("span", b.channels.widget ? `Widget · ${b.channels.widget}` : "Widget · not set up"),
                el("span", b.channels.phone ? "Phone ✓" : "Phone · not set up"),
                el("span", b.channels.calendar ? `Calendar ✓ (${b.channels.calendar} staff)` : "Calendar · not connected"));
    return list;
  }

  function actions(b) {
    const box = el("div", undefined, "actions");
    const pause = el("button", b.status === "paused" ? "Resume" : "Pause", "link");
    pause.disabled = !["live", "paused"].includes(b.status);
    pause.addEventListener("click", () => { b.status = b.status === "paused" ? "live" : "paused"; render(); });
    const retry = el("button", "Retry", "link");
    retry.disabled = b.status !== "failed";
    retry.title = b.failure || "";
    const simulate = el("a", "Simulate", "link");
    simulate.href = "demo/sample-business.html";
    simulate.title = "A chat with this business's real agent, in a sandbox (support access: logged)";
    const traces = el("a", "Traces", "link");
    traces.href = "#";
    traces.title = "This business's LangSmith project";
    box.append(pause, retry, simulate, traces);
    return box;
  }

  function render() {
    const wanted = statusFilter.value, text = search.value.trim().toLowerCase();
    const shown = businesses
      .filter((b) => (!wanted || b.status === wanted) && b.name.toLowerCase().includes(text))
      .sort((a, b) => ORDER[a.status] - ORDER[b.status] || a.name.localeCompare(b.name));
    rows.replaceChildren(...shown.map((b) => {
      const tr = el("tr");
      const name = el("div", undefined, "stack");
      name.append(el("strong", b.name), el("span", b.since ? `${b.type} · live since ${b.since}` : b.type, "muted"));
      const status = el("span", b.status, `status ${b.status}`);
      if (b.failure) status.title = b.failure;
      const services = el("div", undefined, "stack");
      services.append(el("span", `${b.services} services`),
                      el("span", b.priceMissing ? `${b.priceMissing} price missing` : "all priced", "muted"));
      const week = el("div", undefined, "stack");
      week.append(el("span", `${b.chats} chats · ${b.bookings} bookings`),
                  el("span", `${b.handoffs} open hand-offs · last chat ${b.lastChat}`, "muted"));
      const day = el("div", undefined, "stack");
      day.append(el("span", `${b.errors} errors`, b.errors ? "warn" : ""),
                 el("span", b.p95 ? `reply p95 ${b.p95} s` : "no chats yet", b.p95 > 10 ? "warn" : "muted"));
      const cost = el("span", `$${b.cost.toFixed(2)} of $${b.budget.toFixed(2)}`);
      tr.append(td(name), td(status), td(channels(b)), td(services), td(week), td(day), td(cost), td(actions(b)));
      return tr;
    }));
    summary();
  }

  statusFilter.addEventListener("change", render);
  search.addEventListener("input", render);
  render();
})();

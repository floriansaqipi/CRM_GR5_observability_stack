const $ = (id) => document.getElementById(id);
const labels = {
  cpu_fixed: "CPU comparison",
  cpu: "CPU calculation",
  memory: "Memory hold",
  network: "Network transfer",
  database: "Database read / write",
  combined: "Combined Data",
};
const fieldLabels = {
  duration_seconds: "Duration / safety deadline",
  batch_count: "Number of fixed calculation batches",
  cpu_percent: "CPU busy time (%)",
  memory_mib: "Allocated memory (MiB)",
  payload_kib: "Network payload (KiB)",
  rate_per_second: "Requests / cycles per second",
  document_kib: "Database payload (KiB)",
};
const help = {
  cpu_fixed: "Run the same fixed calculation work under each allocation. Low / Medium / High select 16 / 32 / 64 batches, each containing 2,500 calculation units.",
  cpu: "Compute repeats calculations with controlled busy and idle intervals.",
  memory:
    "Data touches and holds a memory buffer until completion or cancellation.",
  network:
    "Data downloads real payloads from Compute. Watch Data receive traffic in Grafana.",
  database:
    "Data performs one MongoDB write and read per cycle. Temporary documents are cleaned afterward.",
  combined:
    "Data holds memory while performing network transfers and database cycles.",
};
let catalog,
  current,
  detailRun,
  page = 1,
  pollCount = 0,
  pending = false;
let historyRequest = 0;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function settingValue(name, value) {
  const unit = {duration_seconds: "seconds", cpu_percent: "% busy time", memory_mib: "MiB", payload_kib: "KiB", document_kib: "KiB", rate_per_second: "/ second", batch_count: "batches"}[name] || "";
  return Number(value).toLocaleString("en-US") + (unit ? " " + unit : "");
}
function settingItem(label, value) {
  const item = element("div", undefined, "setting");
  item.append(element("span", label), element("strong", value));
  return item;
}
function renderSettings(container, settings) {
  container.replaceChildren(...Object.entries(settings).map(([name, value]) =>
    settingItem(fieldLabels[name] || name, settingValue(name, value))));
}
function section(title) {
  const node = element("section", undefined, "detail-section");
  node.append(element("h3", title));
  $("detail-body").append(node);
  return node;
}
function table(headers, rows) {
  const wrapper = element("div", undefined, "table-wrap");
  const grid = element("table"), head = element("thead"), row = element("tr");
  for (const title of headers) row.append(element("th", title));
  head.append(row);
  const body = element("tbody");
  for (const values of rows) {
    const entry = element("tr");
    for (const value of values) entry.append(element("td", value));
    body.append(entry);
  }
  grid.append(head, body);
  wrapper.append(grid);
  return wrapper;
}
async function api(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "The request failed.");
  return data;
}
function notice(message = "") {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}
function settingFields() {
  if (!catalog) return;
  const kind = $("workload").value,
    profile = $("profile").value;
  $("workload-help").textContent = help[kind];
  const fixed = kind === "cpu_fixed";
  $("duration-control").hidden = fixed;
  $("duration").disabled = fixed;
  $("fixed-work-hint").hidden = !fixed;
  $("profile-label").textContent = fixed ? "Work amount" : "Intensity";
  $("advanced-fields").replaceChildren();
  for (const name of catalog.fields[kind]) {
    const row = document.createElement("div");
    row.className = "advanced-row";
    const label = document.createElement("label");
    label.htmlFor = "setting-" + name;
    label.textContent = fieldLabels[name];
    const input = document.createElement("input");
    input.type = "number";
    input.id = "setting-" + name;
    input.min = catalog.limits[name][0];
    input.max = catalog.limits[name][1];
    input.value = catalog.presets[profile][name];
    input.required = true;
    row.append(label, input);
    $("advanced-fields").append(row);
  }
}
function metric(value, label) {
  const div = document.createElement("div");
  div.className = "metric";
  const strong = document.createElement("strong");
  strong.textContent = value;
  const span = document.createElement("span");
  span.textContent = label;
  div.append(strong, span);
  return div;
}
function displayRun(run) {
  current = run;
  $("empty").hidden = !!run;
  $("current-run").hidden = !run;
  if (!run) return;
  const active = ["starting", "running", "stopping"].includes(run.state);
  $("current-name").textContent = run.name || labels[run.workload];
  $("current-state").textContent = run.state;
  $("current-state").className = "badge " + run.state;
  $("current-description").textContent =
    labels[run.workload] +
    " · " +
    run.profile +
    (run.workload === "cpu_fixed" ? " work amount · " : " intensity · ") +
    (run.target_services || [run.target_service]).join(" + ");
  $("elapsed").textContent = Number(run.elapsed_seconds || 0).toFixed(1);
  $("planned-duration").textContent =
    run.workload === "cpu_fixed" ? "180s safety deadline" : run.settings.duration_seconds + "s planned";
  $("progress").value = Math.min(
    100,
    run.workload === "cpu_fixed" ? 100 * (run.counters?.fixed_batches || 0) / run.settings.batch_count :
    (100 * (run.elapsed_seconds || 0)) / run.settings.duration_seconds,
  );
  $("progress").setAttribute("aria-label", run.workload === "cpu_fixed" ? "Completed calculation batches" : "Elapsed duration");
  $("stop").disabled = !active || run.state === "stopping";
  $("stop").textContent =
    run.state === "stopping" ? "Stopping…" : "Stop experiment";
  $("run-grafana").href = run.grafana_url;
  $("run-application").href = run.application_grafana_url;
  traceLink("run-trace", run);
  $("trace-hint").textContent = run.trace_id
    ? "Trace ingestion can take a few seconds. Traces are retained for about 24 hours; history lasts longer."
    : "This run has no recorded trace. Start the lab with tracing enabled to trace new experiments.";
  renderSettings($("current-settings"), run.settings);
  $("current-error").textContent = run.error || "";
  $("current-error").hidden = !run.error;
  $("current-storage").textContent =
    run.persistence === "saved"
      ? "✓ Run saved to history."
      : "History pending — retained in memory until MongoDB is available.";
  const c = run.counters || {},
    rates = run.rates || {};
  const cards = [];
  if (run.workload === "cpu_fixed") {
    cards.push(metric((c.fixed_batches || 0) + " / " + run.settings.batch_count, "Completed fixed batches"));
    cards.push(metric((c.cpu_batches || 0).toLocaleString(), "Calculation units"));
    cards.push(metric((c.checksum || 0).toLocaleString(), "Actual checksum"));
    cards[cards.length - 1].classList.add("checksum");
    for (const [instance, part] of Object.entries(run.instance_results || {})) {
      cards.push(metric(part.counters?.fixed_batches || 0, instance + " completed batches"));
    }
  }
  if (run.workload === "cpu")
    cards.push(
      metric((c.cpu_batches || 0).toLocaleString(), "Calculation batches"),
    );
  if (["memory", "combined"].includes(run.workload))
    cards.push(metric(c.allocated_mib || 0, "MiB allocated by workload"));
  if (["network", "combined"].includes(run.workload)) {
    cards.push(
      metric(
        (c.network_requests || 0).toLocaleString(),
        "Successful responses",
      ),
    );
    cards.push(
      metric(((c.network_bytes || 0) / 1048576).toFixed(2), "MiB transferred"),
    );
    cards.push(
      metric(
        rates.network_requests_per_second || 0,
        "Achieved requests / second",
      ),
    );
  }
  if (["database", "combined"].includes(run.workload)) {
    cards.push(
      metric(
        (c.database_cycles || 0).toLocaleString(),
        "Completed database cycles",
      ),
    );
    cards.push(
      metric(
        rates.database_cycles_per_second || 0,
        "Achieved database cycles / second",
      ),
    );
  }
  cards.push(metric(c.errors || 0, "Operation errors"));
  $("metrics").replaceChildren(...cards);
}
function query() {
  const q = new URLSearchParams();
  for (const [key, id] of [
    ["workload", "filter-workload"],
    ["state", "filter-state"],
    ["q", "search"],
  ])
    if ($(id).value) q.set(key, $(id).value);
  return q;
}
async function loadHistory() {
  const requestId = ++historyRequest;
  const q = query();
  $("export").href = "/api/runs/export.csv?" + q.toString();
  q.set("page", page);
  q.set("page_size", 10);
  const data = await api("/api/runs?" + q);
  if (requestId !== historyRequest) return data;
  $("history-body").replaceChildren();
  for (const run of data.items) {
    const row = document.createElement("tr");
    const values = [
      run.name || run.id.slice(0, 8),
      labels[run.workload],
      run.state,
      new Date(run.started_at || run.created_at).toLocaleString("en-GB", {month:"short", day:"numeric", hour:"2-digit", minute:"2-digit"}),
      Number(run.elapsed_seconds || 0).toFixed(1) + "s",
      run.persistence,
    ];
    for (const [index, text] of values.entries()) {
      const cell = document.createElement("td");
      if (index === 2) cell.append(element("span", text, "badge " + run.state));
      else cell.textContent = text;
      if (index === 5) cell.className = run.persistence;
      row.append(cell);
    }
    const cell = document.createElement("td"),
      button = document.createElement("button");
    button.className = "outline";
    button.textContent = "Details";
    button.onclick = () => details(run.id);
    cell.append(button);
    row.append(cell);
    $("history-body").append(row);
  }
  $("history-empty").hidden = data.items.length > 0;
  $("history-empty").textContent = "No experiments match these filters.";
  $("previous").disabled = page === 1;
  $("next").disabled = page * 10 >= data.total;
  $("page-label").textContent = "Page " + page + " · " + data.total + " runs";
  if (!catalog?.active && data.items.length && !current)
    displayRun(data.items[0]);
  return data;
}
async function details(id) {
  try {
    const run = await api("/api/runs/" + id);
    detailRun = run;
    $("detail-name").textContent = run.name || labels[run.workload];
    $("detail-body").replaceChildren();
    const summary = section("Run summary"), facts = element("div", undefined, "detail-grid");
    facts.append(settingItem("Workload", labels[run.workload]), settingItem("Outcome / history", run.state + " / " + run.persistence),
      settingItem("Target services", (run.target_services || [run.target_service]).join(" + ")),
      settingItem("Elapsed time", Number(run.elapsed_seconds || 0).toFixed(3) + " seconds"),
      settingItem("Started", new Date(run.started_at || run.created_at).toLocaleString("en-GB")),
      settingItem("Finished", run.finished_at ? new Date(run.finished_at).toLocaleString("en-GB") : "In progress"),
      settingItem("Run ID", run.id), settingItem("Trace ID", run.trace_id || "Not recorded"));
    summary.append(facts, element("p", run.notes || "No notes recorded."));
    if (run.error) summary.append(element("p", run.error, "error"));
    const settings = element("div", undefined, "settings-grid");
    renderSettings(settings, run.settings);
    section("Resolved workload settings").append(settings);
    const deployment = section("Saved deployment");
    if (run.deployment) {
      const d = run.deployment;
      deployment.append(element("p", "Preset: " + d.preset + " · tracing " + (d.tracing ? "enabled" : "disabled") + " · " + (d.verified ? "verified at Start" : "verification unknown")));
      const resource = (limits) => limits ? (limits.cpus ?? "unavailable") + " CPU / " + (limits.memory_bytes ? limits.memory_bytes/1048576 : "unavailable") + " MiB" : "Unknown";
      deployment.append(table(["Instance", "Expected ceiling", "Verified effective ceiling"], Object.entries(d.expected || {}).map(([name, limits]) => [name, resource(limits), resource(d.effective?.[name]?.limits)])));
    } else deployment.append(element("p", "Unknown — this record predates saved deployment snapshots."));
    const counterLabels = {cpu_batches:"Calculation units / batches", checksum:"Actual checksum", fixed_batches:"Completed logical batches", allocated_mib:"Allocated memory (MiB)", network_requests:"Successful network responses", network_bytes:"Received payload bytes", database_cycles:"Completed database cycles", database_reads:"Successful database reads", database_writes:"Successful database writes", errors:"Operation errors"};
    counterLabels.cpu_batches = run.workload === "cpu_fixed" ? "Calculation units" : "Calculation batches";
    const results = element("div", undefined, "detail-grid");
    for (const [key, value] of Object.entries(run.counters || {})) results.append(settingItem(counterLabels[key] || key.replaceAll("_", " "), typeof value === "number" ? value.toLocaleString("en-US") : value));
    for (const [key, value] of Object.entries(run.rates || {})) results.append(settingItem("Achieved " + key.replaceAll("_", " "), Number(value).toLocaleString("en-US")));
    section("Actual results").append(results);
    if (run.instance_results && Object.keys(run.instance_results).length) section("Per-instance results").append(table(["Instance", "Outcome", "Completed batches", "Actual units"], Object.entries(run.instance_results).map(([name, part]) => [name, part.state, part.counters?.fixed_batches || 0, (part.counters?.cpu_batches || 0).toLocaleString("en-US")])));
    if (run.batch_results?.length) {
      const batches = section("Batch results · " + (run.algorithm_version || "unknown algorithm"));
      batches.append(table(["Batch", "Instance", "Slot", "Outcome", "Units", "Checksum"], run.batch_results.map(b => [b.batch_id, b.instance, b.slot, b.state, b.calculation_units.toLocaleString("en-US"), b.checksum.toLocaleString("en-US")])));
    }
    const raw = element("details"), rawTitle = element("summary", "Advanced · raw saved record");
    raw.append(rawTitle, element("pre", JSON.stringify(run, null, 2)));
    $("detail-body").append(raw);
    $("detail-grafana").href = run.grafana_url;
    $("detail-application").href = run.application_grafana_url;
    traceLink("detail-trace", run);
    if (!$("run-dialog").open) $("run-dialog").showModal();
    $("run-dialog").scrollTop = 0;
  } catch (error) {
    notice(error.message);
  }
}
function traceLink(id, run) {
  $(id).hidden = !run.trace_url || !catalog?.observability?.tracing_enabled;
  if (run.trace_url) $(id).href = run.trace_url;
}
let connectionFailed = false;
async function poll() {
  try {
    const wasActive = !!catalog?.active;
    catalog = await api("/api/workloads");
    $("connection-status").textContent = "Connected · status every second";
    $("connection-status").dataset.tone = "good";
    const deployment = catalog.deployment;
    if (deployment) {
      $("deployment-status").textContent = deployment.pending ? "Maintenance in progress" : deployment.verified ? "Limits verified" : "Verification pending";
      $("deployment-status").dataset.tone = deployment.pending || !deployment.verified ? "warning" : "good";
      $("deployment-summary").textContent = "Preset: " + deployment.preset + " · " + deployment.compute_instances.length + " Compute instance(s) · tracing " + (deployment.tracing ? "enabled" : "disabled");
      $("deployment-limits").textContent = Object.entries(deployment.expected).map(([instance, limits]) => {
        const actual = deployment.effective[instance]?.limits;
        return instance + ": " + (actual?.cpus ?? "unavailable") + " CPU / " + (actual?.memory_bytes ? actual.memory_bytes / 1048576 : "unavailable") + " MiB";
      }).join(" · ");
      if (deployment.error) $("deployment-limits").textContent += " · " + deployment.error;
    }
    if (current) traceLink("run-trace", current);
    if (detailRun) traceLink("detail-trace", detailRun);
    $("tracing-status").textContent = catalog.observability?.tracing_enabled
      ? "● Tracing enabled · export is asynchronous"
      : "○ Tracing disabled · application metrics available";
    if (!$("advanced-fields").children.length) settingFields();
    $("workers-status").textContent =
      catalog.ready && Object.values(catalog.workers).every(Boolean)
        ? "● Workload services ready"
        : "● Waiting for workload services";
    $("storage-status").textContent = catalog.storage_available
      ? "● MongoDB history available"
      : "● MongoDB offline — history pending";
    $("storage-status").dataset.tone = catalog.storage_available ? "good" : "warning";
    $("workers-status").dataset.tone = catalog.ready ? "good" : "warning";
    for (const name of catalog.fields[$("workload").value]) {
      const input = $("setting-" + name);
      if (input) { input.min = catalog.limits[name][0]; input.max = catalog.limits[name][1]; }
    }
    $("unsaved-status").textContent = catalog.unsaved_count
      ? catalog.unsaved_count +
        " unsaved run(s). Pending results may be lost if the controller restarts."
      : "";
    const entry = catalog.workloads.find((w) => w.id === $("workload").value);
    $("start").disabled = pending || !!catalog.active || !entry?.available;
    for (const option of $("workload").options) {
      option.disabled = !catalog.workloads.find((w) => w.id === option.value)
        ?.available;
    }
    if (catalog.active) displayRun(catalog.active);
    else if (
      current &&
      (wasActive ||
        current.persistence === "pending" ||
        ["starting", "running", "stopping"].includes(current.state))
    ) {
      displayRun(await api("/api/runs/" + current.id));
      await loadHistory();
    }
    if (pollCount++ % 5 === 0) await loadHistory();
    if (connectionFailed) {
      notice();
      connectionFailed = false;
    }
  } catch (error) {
    connectionFailed = true;
    $("start").disabled = true;
    $("workers-status").textContent = "● Connection unavailable";
    $("workers-status").dataset.tone = "error";
    $("connection-status").textContent = "Connection lost · last known result";
    $("connection-status").dataset.tone = "error";
    notice(error.message);
  }
}
$("workload").onchange = () => {
  settingFields();
  poll();
};
$("profile").onchange = settingFields;
$("run-form").onsubmit = async (event) => {
  event.preventDefault();
  pending = true;
  $("start").disabled = true;
  notice();
  try {
    const overrides = {};
    for (const name of catalog.fields[$("workload").value])
      overrides[name] = Number($("setting-" + name).value);
    const run = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workload: $("workload").value,
        profile: $("profile").value,
        ...($("workload").value === "cpu_fixed" ? {} : {duration_seconds: Number($("duration").value)}),
        overrides,
        name: $("run-name").value,
        notes: $("notes").value,
      }),
    });
    displayRun(run);
    page = 1;
    await poll();
    await loadHistory();
  } catch (error) {
    notice(error.message);
  } finally {
    pending = false;
  }
};
$("stop").onclick = async () => {
  if (!current) return;
  $("stop").disabled = true;
  try {
    displayRun(
      await api("/api/runs/" + current.id + "/stop", { method: "POST" }),
    );
  } catch (error) {
    notice(error.message);
  }
};
for (const id of ["filter-workload", "filter-state"])
  $(id).onchange = () => {
    page = 1;
    loadHistory().catch((e) => notice(e.message));
  };
let searchTimer;
$("search").oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    page = 1;
    loadHistory().catch((e) => notice(e.message));
  }, 300);
};
$("previous").onclick = () => {
  page--;
  loadHistory().catch((e) => notice(e.message));
};
$("next").onclick = () => {
  page++;
  loadHistory().catch((e) => notice(e.message));
};
$("close-dialog").onclick = () => $("run-dialog").close();
$("clear-filters").onclick = () => {
  clearTimeout(searchTimer);
  for (const id of ["search", "filter-workload", "filter-state"]) $(id).value = "";
  page = 1;
  loadHistory().catch((error) => notice(error.message));
};
async function cycle() {
  await poll();
  setTimeout(cycle, 1000);
}
cycle();

const HEALTH_ENDPOINT = "/health/ready";
const INGESTION_STATUS_ENDPOINT = "/ingestion/status";
const BRONZE_RUNS_ENDPOINT = "/bronze/runs";
const INGESTION_POLL_INTERVAL_MS = 3000;

const viewNames = {
  chat: "Chat",
  dashboard: "Ingestion",
  data: "Bronze explorer",
  retrieval: "Retrieval",
  evaluation: "Evaluation"
};

const state = {
  bronzeRuns: [],
  activeBronzeRun: null,
  activeBronzeResource: null,
  ingestionRefreshPending: false,
  toastTimer: 0
};

const elements = {
  body: document.body,
  sidebar: document.querySelector(".sidebar"),
  sidebarOpenButton: document.querySelector("[data-sidebar-open]"),
  currentView: document.querySelector("[data-current-view]"),
  healthButton: document.querySelector("[data-health-refresh]"),
  healthLabel: document.querySelector("[data-health-label]"),
  ingestionWorks: document.querySelector("[data-ingestion-works]"),
  ingestionNavCount: document.querySelector("[data-ingestion-nav-count]"),
  ingestionDiscovered: document.querySelector("[data-ingestion-discovered]"),
  ingestionPages: document.querySelector("[data-ingestion-pages]"),
  ingestionMissing: document.querySelector("[data-ingestion-missing]"),
  ingestionFailures: document.querySelector("[data-ingestion-failures]"),
  ingestionRetries: document.querySelector("[data-ingestion-retries]"),
  ingestionStatus: document.querySelector("[data-ingestion-status]"),
  ingestionUpdated: document.querySelector("[data-ingestion-updated]"),
  ingestionBadge: document.querySelector("[data-ingestion-badge]"),
  ingestionRunId: document.querySelector("[data-ingestion-run-id]"),
  ingestionPercent: document.querySelector("[data-ingestion-percent]"),
  ingestionProgress: document.querySelector("[data-ingestion-progress]"),
  ingestionProgressBar: document.querySelector("[data-ingestion-progress-bar]"),
  ingestionCurrentWork: document.querySelector("[data-ingestion-current-work]"),
  ingestionDiscoveryStage: document.querySelector("[data-ingestion-discovery-stage]"),
  ingestionCompletedStage: document.querySelector("[data-ingestion-completed-stage]"),
  ingestionOcrStage: document.querySelector("[data-ingestion-ocr-stage]"),
  ingestionResultStage: document.querySelector("[data-ingestion-result-stage]"),
  ingestionEvents: document.querySelector("[data-ingestion-events]"),
  ingestionAttentionTitle: document.querySelector("[data-ingestion-attention-title]"),
  ingestionAttentionDetail: document.querySelector("[data-ingestion-attention-detail]"),
  bronzeRunSelect: document.querySelector("[data-bronze-run-select]"),
  bronzeRunSummary: document.querySelector("[data-bronze-run-summary]"),
  bronzeFailures: document.querySelector("[data-bronze-failures]"),
  recordList: document.querySelector("[data-record-list]"),
  recordCount: document.querySelector("[data-record-count]"),
  recordEmpty: document.querySelector("[data-record-empty]"),
  recordSearch: document.querySelector("[data-record-search]"),
  recordFilter: document.querySelector("[data-record-filter]"),
  detailLoading: document.querySelector("[data-detail-loading]"),
  detailContent: document.querySelector("[data-detail-content]"),
  toast: document.querySelector("[data-toast]")
};

const mobileNavigation = window.matchMedia("(max-width: 820px)");

function setActiveView(viewId) {
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.hidden = panel.dataset.viewPanel !== viewId;
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    const isActive = button.dataset.view === viewId;
    button.classList.toggle("is-active", isActive);
    if (isActive) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  elements.currentView.textContent = viewNames[viewId];
  document.title = `${viewNames[viewId]} — HeritageRAG`;
  closeSidebar();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openSidebar() {
  elements.body.classList.add("sidebar-open");
  syncSidebarAccessibility();
  document.querySelector(".sidebar-close")?.focus();
}

function closeSidebar() {
  elements.body.classList.remove("sidebar-open");
  syncSidebarAccessibility();
}

function syncSidebarAccessibility() {
  const hidden = mobileNavigation.matches && !elements.body.classList.contains("sidebar-open");
  elements.sidebar.inert = hidden;
  if (hidden) elements.sidebar.setAttribute("aria-hidden", "true");
  else elements.sidebar.removeAttribute("aria-hidden");
  elements.sidebarOpenButton.setAttribute(
    "aria-expanded",
    String(!hidden && mobileNavigation.matches)
  );
}

async function refreshHealth() {
  elements.healthButton.className = "system-status is-checking";
  elements.healthLabel.textContent = "Checking system";
  elements.healthButton.disabled = true;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(HEALTH_ENDPOINT, {
      headers: { Accept: "application/json" },
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`Health request returned ${response.status}`);
    const health = await response.json();
    if (health.status !== "ok") throw new Error("Unexpected health response");
    elements.healthButton.className = "system-status is-online";
    elements.healthLabel.textContent = "System operational";
    elements.healthButton.title = `${health.service} ${health.version} · click to refresh`;
  } catch {
    elements.healthButton.className = "system-status is-offline";
    elements.healthLabel.textContent = "Backend offline";
    elements.healthButton.title = "Start the API and click to try again";
  } finally {
    window.clearTimeout(timeoutId);
    elements.healthButton.disabled = false;
  }
}

const ingestionStatusLabels = {
  idle: "Idle",
  running: "In progress",
  completed: "Completed",
  completed_with_failures: "Completed with failures",
  failed: "Failed"
};

const ingestionBadgeStyles = {
  idle: "planned",
  running: "active",
  completed: "ready",
  completed_with_failures: "review",
  failed: "review"
};

function formatTime(value) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Unknown time";
  return timestamp.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function renderIngestionEvents(events) {
  elements.ingestionEvents.replaceChildren();
  if (events.length === 0) {
    const item = document.createElement("li");
    item.innerHTML = "<span class=\"activity-mark\"></span><div><strong>No ingestion events yet</strong><p>Run the Wellcome CLI command to begin.</p><time>Idle</time></div>";
    elements.ingestionEvents.append(item);
    return;
  }
  [...events].reverse().forEach((event) => {
    const item = document.createElement("li");
    const mark = document.createElement("span");
    const detail = document.createElement("div");
    const title = document.createElement("strong");
    const description = document.createElement("p");
    const time = document.createElement("time");
    mark.className = `activity-mark activity-mark--${event.level === "info" ? "success" : "warning"}`;
    mark.textContent = event.level === "info" ? "✓" : "!";
    title.textContent = event.message;
    description.textContent = event.work_id ? `Work ${event.work_id}` : "Ingestion run";
    time.textContent = formatTime(event.timestamp);
    time.dateTime = event.timestamp;
    detail.append(title, description, time);
    item.append(mark, detail);
    elements.ingestionEvents.append(item);
  });
}

function renderIngestionStatus(status) {
  const label = ingestionStatusLabels[status.status] || status.status;
  const denominator = status.works_discovered || status.requested_limit;
  const completion = denominator > 0
    ? Math.round((status.works_completed / denominator) * 100)
    : 0;
  const percent = status.dry_run && status.status === "completed"
    ? 100
    : Math.min(100, completion);
  elements.ingestionWorks.textContent = `${status.works_completed} / ${status.works_discovered}`;
  elements.ingestionDiscovered.textContent = status.works_discovered
    ? `${status.works_discovered} eligible works discovered`
    : "No run has started";
  elements.ingestionPages.textContent = status.pages_downloaded.toLocaleString();
  elements.ingestionMissing.textContent = `${status.missing_ocr_pages} without OCR`;
  elements.ingestionFailures.textContent = status.failure_count;
  elements.ingestionNavCount.textContent = status.failure_count;
  elements.ingestionRetries.textContent = `${status.retry_count} retries`;
  elements.ingestionStatus.textContent = label;
  elements.ingestionUpdated.textContent = status.updated_at
    ? `Updated ${formatTime(status.updated_at)}`
    : "Waiting for a CLI run";
  elements.ingestionBadge.textContent = label;
  elements.ingestionBadge.className = `state-badge state-badge--${ingestionBadgeStyles[status.status] || "planned"}`;
  elements.ingestionRunId.textContent = status.run_id || "No ingestion run yet";
  elements.ingestionPercent.textContent = `${percent}%`;
  elements.ingestionProgress.setAttribute("aria-valuenow", String(percent));
  elements.ingestionProgressBar.style.width = `${percent}%`;
  elements.ingestionCurrentWork.textContent = status.current_work_title
    ? `Current work: ${status.current_work_title}`
    : `Run status: ${label}`;
  elements.ingestionDiscoveryStage.textContent = `${status.works_discovered} selected`;
  elements.ingestionCompletedStage.textContent = `${status.works_completed} completed`;
  elements.ingestionOcrStage.textContent = `${status.pages_downloaded} pages`;
  elements.ingestionResultStage.textContent = label;
  elements.ingestionAttentionTitle.textContent = status.failure_count === 0
    ? "No terminal failures"
    : `${status.failure_count} work failure${status.failure_count === 1 ? "" : "s"}`;
  elements.ingestionAttentionDetail.textContent = (
    `${status.missing_ocr_pages} pages have no OCR; ` +
    `${status.retry_count} retry waits were recorded.`
  );
  renderIngestionEvents(status.recent_events);
}

async function refreshIngestionStatus() {
  if (state.ingestionRefreshPending) return;
  state.ingestionRefreshPending = true;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(INGESTION_STATUS_ENDPOINT, {
      headers: { Accept: "application/json" },
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`Ingestion status returned ${response.status}`);
    renderIngestionStatus(await response.json());
  } catch {
    elements.ingestionStatus.textContent = "Unavailable";
    elements.ingestionUpdated.textContent = "Could not reach ingestion status API";
    elements.ingestionBadge.textContent = "Unavailable";
    elements.ingestionBadge.className = "state-badge state-badge--review";
  } finally {
    window.clearTimeout(timeoutId);
    state.ingestionRefreshPending = false;
  }
}

function showToast(message) {
  window.clearTimeout(state.toastTimer);
  elements.toast.textContent = message;
  elements.toast.hidden = false;
  state.toastTimer = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 3200);
}

function getFilteredResources() {
  if (!state.activeBronzeRun) return [];
  const query = elements.recordSearch.value.trim().toLowerCase();
  const filter = elements.recordFilter.value;
  return state.activeBronzeRun.resources.filter((resource) => {
    const searchable = [
      resource.work_id,
      resource.relative_path,
      resource.resource_id
    ].join(" ").toLowerCase();
    return searchable.includes(query) &&
      (filter === "all" || resource.resource_type === filter);
  });
}

function resourceLabel(resource) {
  return resource.resource_type
    .replace("catalogue_work", "Catalogue work")
    .replace("iiif_manifest", "IIIF manifest")
    .replace("ocr_annotation_list", "OCR annotation");
}

function renderResourceList() {
  const resources = getFilteredResources();
  elements.recordList.replaceChildren();
  elements.recordCount.textContent = `${resources.length} ${resources.length === 1 ? "resource" : "resources"}`;
  elements.recordEmpty.hidden = resources.length !== 0;
  resources.forEach((resource) => {
    const button = document.createElement("button");
    const wrapper = document.createElement("span");
    const title = document.createElement("strong");
    const subtitle = document.createElement("small");
    const metadata = document.createElement("span");
    const arrow = document.createElement("span");
    button.type = "button";
    button.className = `record-item${resource.resource_id === state.activeBronzeResource?.resource_id ? " is-active" : ""}`;
    button.dataset.resourceId = resource.resource_id;
    title.textContent = resourceLabel(resource);
    subtitle.textContent = `Work ${resource.work_id}`;
    metadata.className = "record-meta";
    metadata.textContent = `${resource.byte_length.toLocaleString()} bytes · ${resource.relative_path}`;
    arrow.className = "record-arrow";
    arrow.textContent = "›";
    wrapper.append(title, subtitle, metadata);
    button.append(wrapper, arrow);
    elements.recordList.append(button);
  });
}

function renderRunSummary() {
  const run = state.activeBronzeRun;
  elements.bronzeRunSummary.replaceChildren();
  if (!run) {
    ["Status", "Works", "Resources", "Failures"].forEach((label) => {
      const wrapper = document.createElement("div");
      const term = document.createElement("dt");
      const detail = document.createElement("dd");
      term.textContent = label;
      detail.textContent = "—";
      wrapper.append(term, detail);
      elements.bronzeRunSummary.append(wrapper);
    });
    return;
  }
  const unresolved = run.failures.filter((failure) => failure.resolved_at === null);
  const summary = [
    ["Status", run.status.replaceAll("_", " ")],
    ["Works", `${run.completed_work_count} / ${run.discovered_work_count}`],
    ["Resources", run.resources.length.toLocaleString()],
    ["Failures", `${unresolved.length} unresolved / ${run.failures.length} recorded`]
  ];
  summary.forEach(([label, value]) => {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    wrapper.append(term, detail);
    elements.bronzeRunSummary.append(wrapper);
  });

  elements.bronzeFailures.replaceChildren();
  elements.bronzeFailures.hidden = unresolved.length === 0;
  unresolved.forEach((failure) => {
    const item = document.createElement("p");
    item.textContent = `${failure.message} — ${failure.source_url}`;
    elements.bronzeFailures.append(item);
  });
}

async function renderResourceDetail(resource) {
  const run = state.activeBronzeRun;
  if (!run || !resource) return;
  state.activeBronzeResource = resource;
  renderResourceList();
  elements.detailLoading.hidden = false;
  elements.detailContent.setAttribute("aria-busy", "true");
  document.querySelector("[data-detail-title]").textContent = resourceLabel(resource);
  document.querySelector("[data-detail-subtitle]").textContent = resource.relative_path;
  document.querySelector("[data-detail-id]").textContent = resource.resource_id;
  document.querySelector("[data-detail-work-id]").textContent = resource.work_id;
  document.querySelector("[data-detail-bytes]").textContent = resource.byte_length.toLocaleString();
  document.querySelector("[data-detail-acquired]").textContent = formatTime(resource.acquired_at);
  document.querySelector("[data-detail-hash]").textContent = resource.content_sha256;
  document.querySelector("[data-detail-path]").textContent = resource.relative_path;
  const source = document.querySelector("[data-detail-source]");
  source.href = resource.source_url;
  source.textContent = "Open original source";
  const preview = document.querySelector("[data-detail-json]");
  preview.textContent = "Loading stored JSON…";
  try {
    const url = `${BRONZE_RUNS_ENDPOINT}/${encodeURIComponent(run.identity.run_id)}/resources/${encodeURIComponent(resource.resource_id)}`;
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Resource preview returned ${response.status}`);
    preview.textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) {
    preview.textContent = `Could not load this resource: ${error.message}`;
  } finally {
    elements.detailLoading.hidden = true;
    elements.detailContent.removeAttribute("aria-busy");
  }
}

function selectBronzeRun(runId) {
  state.activeBronzeRun = state.bronzeRuns.find(
    (run) => run.identity.run_id === runId
  ) || null;
  state.activeBronzeResource = null;
  elements.recordSearch.value = "";
  elements.recordFilter.value = "all";
  renderRunSummary();
  renderResourceList();
  const firstResource = state.activeBronzeRun?.resources[0];
  if (firstResource) renderResourceDetail(firstResource);
  else document.querySelector("[data-detail-json]").textContent = "This run has no stored resources.";
}

async function refreshBronzeRuns() {
  elements.bronzeRunSelect.disabled = true;
  try {
    const response = await fetch(BRONZE_RUNS_ENDPOINT, {
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error(`Bronze runs returned ${response.status}`);
    state.bronzeRuns = await response.json();
    elements.bronzeRunSelect.replaceChildren();
    if (state.bronzeRuns.length === 0) {
      const option = document.createElement("option");
      option.textContent = "No Bronze runs available";
      elements.bronzeRunSelect.append(option);
      renderRunSummary();
      renderResourceList();
      document.querySelector("[data-detail-json]").textContent = (
        "Run a non-dry Wellcome ingestion to create Bronze data."
      );
      return;
    }
    state.bronzeRuns.forEach((run) => {
      const option = document.createElement("option");
      option.value = run.identity.run_id;
      option.textContent = `${formatTime(run.started_at)} · ${run.status} · ${run.identity.run_id}`;
      elements.bronzeRunSelect.append(option);
    });
    selectBronzeRun(state.bronzeRuns[0].identity.run_id);
  } catch (error) {
    elements.bronzeRunSelect.replaceChildren();
    const option = document.createElement("option");
    option.textContent = "Bronze API unavailable";
    elements.bronzeRunSelect.append(option);
    document.querySelector("[data-detail-json]").textContent = error.message;
  } finally {
    elements.bronzeRunSelect.disabled = false;
  }
}

function resetResourceSearch() {
  elements.recordSearch.value = "";
  elements.recordFilter.value = "all";
  renderResourceList();
  elements.recordSearch.focus();
}

function handleChatSubmit(event) {
  event.preventDefault();
  const input = document.querySelector("[data-chat-input]");
  const feedback = document.querySelector("[data-chat-feedback]");
  if (!input.value.trim()) {
    input.focus();
    return;
  }
  feedback.textContent = "Your question is ready. Answer generation will be connected after retrieval and evidence validation are complete.";
  feedback.hidden = false;
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => setActiveView(button.dataset.view));
});
elements.sidebarOpenButton.addEventListener("click", openSidebar);
document.querySelectorAll("[data-sidebar-close]").forEach((button) => {
  button.addEventListener("click", closeSidebar);
});
elements.healthButton.addEventListener("click", refreshHealth);
document.querySelector("[data-dismiss-notice]").addEventListener("click", (event) => {
  event.currentTarget.closest(".notice-banner").remove();
});
document.querySelectorAll("[data-notice]").forEach((button) => {
  button.addEventListener("click", () => showToast(button.dataset.notice));
});
document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.querySelector("[data-chat-input]");
    input.value = button.dataset.prompt;
    input.focus();
  });
});
document.querySelector("[data-chat-form]").addEventListener("submit", handleChatSubmit);
elements.bronzeRunSelect.addEventListener("change", () => {
  selectBronzeRun(elements.bronzeRunSelect.value);
});
elements.recordSearch.addEventListener("input", renderResourceList);
elements.recordFilter.addEventListener("change", renderResourceList);
document.querySelector("[data-reset-search]").addEventListener("click", resetResourceSearch);
elements.recordList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-resource-id]");
  const resource = state.activeBronzeRun?.resources.find(
    (candidate) => candidate.resource_id === button?.dataset.resourceId
  );
  if (resource) renderResourceDetail(resource);
});
document.querySelector("[data-copy-id]").addEventListener("click", async () => {
  const id = state.activeBronzeResource?.resource_id;
  if (!id) return;
  try {
    await navigator.clipboard.writeText(id);
    showToast("Resource ID copied to clipboard.");
  } catch {
    showToast(`Resource ID: ${id}`);
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSidebar();
});
mobileNavigation.addEventListener("change", syncSidebarAccessibility);

syncSidebarAccessibility();
refreshHealth();
refreshIngestionStatus();
refreshBronzeRuns();
window.setInterval(refreshIngestionStatus, INGESTION_POLL_INTERVAL_MS);

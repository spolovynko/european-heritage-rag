const HEALTH_ENDPOINT = "/health/ready";
const INGESTION_STATUS_ENDPOINT = "/ingestion/status";
const BRONZE_RUNS_ENDPOINT = "/bronze/runs";
const SILVER_DATASETS_ENDPOINT = "/silver/datasets";
const GOLD_DATASETS_ENDPOINT = "/gold/datasets";
const INGESTION_POLL_INTERVAL_MS = 3000;

const viewNames = {
  chat: "Chat",
  dashboard: "Ingestion",
  data: "Data explorer",
  retrieval: "Retrieval",
  evaluation: "Evaluation"
};

const state = {
  bronzeRuns: [],
  activeBronzeRun: null,
  activeBronzeResource: null,
  silverDatasets: [],
  activeSilverDataset: null,
  silverWorks: [],
  silverPages: [],
  silverPageTotal: 0,
  activeSilverPage: null,
  goldDatasets: [],
  activeGoldDataset: null,
  goldWorks: [],
  goldChunks: [],
  goldChunkTotal: 0,
  activeGoldChunk: null,
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
  bronzeExplorer: document.querySelector("[data-bronze-explorer]"),
  silverExplorer: document.querySelector("[data-silver-explorer]"),
  goldExplorer: document.querySelector("[data-gold-explorer]"),
  silverDatasetSelect: document.querySelector("[data-silver-dataset-select]"),
  silverSummary: document.querySelector("[data-silver-summary]"),
  silverWorkSelect: document.querySelector("[data-silver-work-select]"),
  silverFlagSelect: document.querySelector("[data-silver-flag-select]"),
  silverPageList: document.querySelector("[data-silver-page-list]"),
  silverPageCount: document.querySelector("[data-silver-page-count]"),
  silverPageEmpty: document.querySelector("[data-silver-page-empty]"),
  goldDatasetSelect: document.querySelector("[data-gold-dataset-select]"),
  goldSummary: document.querySelector("[data-gold-summary]"),
  goldWorkSelect: document.querySelector("[data-gold-work-select]"),
  goldChunkList: document.querySelector("[data-gold-chunk-list]"),
  goldChunkCount: document.querySelector("[data-gold-chunk-count]"),
  goldChunkEmpty: document.querySelector("[data-gold-chunk-empty]"),
  goldPrevious: document.querySelector("[data-gold-previous]"),
  goldNext: document.querySelector("[data-gold-next]"),
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

function setDataLayer(layer) {
  const showSilver = layer === "silver";
  const showGold = layer === "gold";
  elements.bronzeExplorer.hidden = showSilver || showGold;
  elements.silverExplorer.hidden = !showSilver;
  elements.goldExplorer.hidden = !showGold;
  document.querySelectorAll("[data-data-layer]").forEach((button) => {
    const active = button.dataset.dataLayer === layer;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function renderSilverSummary(quality) {
  const values = [
    ["Works", quality.work_count.toLocaleString()],
    ["Pages", quality.page_count.toLocaleString()],
    ["Usable", quality.usable_page_count.toLocaleString()],
    [
      "Review / empty",
      `${quality.review_page_count.toLocaleString()} / ${quality.empty_page_count.toLocaleString()}`
    ]
  ];
  elements.silverSummary.replaceChildren();
  values.forEach(([label, value]) => {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    wrapper.append(term, detail);
    elements.silverSummary.append(wrapper);
  });
  setSilverDetailText(
    "[data-silver-average-words]",
    quality.average_clean_word_count.toFixed(1)
  );
  setSilverDetailText(
    "[data-silver-languages]",
    Object.entries(quality.language_counts)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([language, count]) => `${language}: ${count}`)
      .join(" · ") || "Not recorded"
  );
  setSilverDetailText(
    "[data-silver-processing-failures]",
    quality.processing_failures.length.toLocaleString()
  );
}

function renderSilverWorkOptions() {
  const previousValue = elements.silverWorkSelect.value;
  elements.silverWorkSelect.replaceChildren();
  const allWorks = document.createElement("option");
  allWorks.value = "";
  allWorks.textContent = "All works";
  elements.silverWorkSelect.append(allWorks);
  state.silverWorks.forEach((work) => {
    const option = document.createElement("option");
    option.value = work.work_id;
    option.textContent = `${work.title} · ${work.work_id}`;
    elements.silverWorkSelect.append(option);
  });
  if (state.silverWorks.some((work) => work.work_id === previousValue)) {
    elements.silverWorkSelect.value = previousValue;
  }
}

function renderSilverPageList() {
  elements.silverPageList.replaceChildren();
  elements.silverPageCount.textContent = (
    state.silverPages.length === state.silverPageTotal
      ? `${state.silverPages.length} ${state.silverPages.length === 1 ? "page" : "pages"}`
      : `Showing ${state.silverPages.length} of ${state.silverPageTotal} pages`
  );
  elements.silverPageEmpty.hidden = state.silverPages.length !== 0;
  state.silverPages.forEach((page) => {
    const button = document.createElement("button");
    const wrapper = document.createElement("span");
    const title = document.createElement("strong");
    const subtitle = document.createElement("small");
    const metadata = document.createElement("span");
    const arrow = document.createElement("span");
    button.type = "button";
    button.className = (
      `record-item${page.page_id === state.activeSilverPage?.page_id ? " is-active" : ""}`
    );
    button.dataset.silverPageSelect = page.page_id;
    title.textContent = `Page ${page.sequence_number} · ${page.page_label}`;
    subtitle.textContent = `Work ${page.work_id}`;
    metadata.className = "record-meta";
    metadata.textContent = (
      `${page.ocr_quality.replaceAll("_", " ")} · ` +
      `${page.clean_word_count.toLocaleString()} clean words`
    );
    arrow.className = "record-arrow";
    arrow.textContent = "›";
    wrapper.append(title, subtitle, metadata);
    button.append(wrapper, arrow);
    elements.silverPageList.append(button);
  });
}

function setSilverDetailText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function renderSilverWorkMetadata(workId) {
  const work = state.silverWorks.find((candidate) => candidate.work_id === workId);
  if (!work) return;
  const contributors = work.contributors.map((contributor) => {
    const roles = contributor.roles.length ? ` (${contributor.roles.join(", ")})` : "";
    return `${contributor.label}${roles}`;
  });
  const production = [...work.production_dates, ...work.production_labels];
  setSilverDetailText("[data-silver-work-title]", work.title);
  setSilverDetailText("[data-silver-contributors]", contributors.join(" · ") || "Not recorded");
  setSilverDetailText("[data-silver-production]", production.join(" · ") || "Not recorded");
  setSilverDetailText(
    "[data-silver-work-languages]",
    work.language_labels.join(" · ") || work.language_ids.join(" · ") || "Not recorded"
  );
  setSilverDetailText("[data-silver-subjects]", work.subjects.join(" · ") || "Not recorded");
  setSilverDetailText("[data-silver-genres]", work.genres.join(" · ") || "Not recorded");
  const source = document.querySelector("[data-silver-work-source]");
  source.href = work.source_url;
  source.textContent = `${work.licence_id || "Unknown licence"} · open source`;
}

async function renderSilverPageDetail(pageSummary) {
  const dataset = state.activeSilverDataset;
  if (!dataset || !pageSummary) return;
  try {
    const url = (
      `${SILVER_DATASETS_ENDPOINT}/${encodeURIComponent(dataset.dataset_id)}` +
      `/pages/${encodeURIComponent(pageSummary.page_id)}`
    );
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Silver page returned ${response.status}`);
    const page = await response.json();
    state.activeSilverPage = page;
    renderSilverPageList();
    setSilverDetailText("[data-silver-detail-title]", `Page ${page.sequence_number} · ${page.page_label}`);
    setSilverDetailText("[data-silver-detail-subtitle]", `Canonical page from work ${page.work_id}`);
    setSilverDetailText("[data-silver-quality]", page.ocr_quality.replaceAll("_", " "));
    setSilverDetailText("[data-silver-page-id]", page.page_id);
    setSilverDetailText("[data-silver-work-id]", page.work_id);
    setSilverDetailText("[data-silver-sequence]", page.sequence_number.toLocaleString());
    setSilverDetailText("[data-silver-printed-page]", page.printed_page_number ?? "Not parsed");
    setSilverDetailText("[data-silver-raw-words]", page.raw_word_count.toLocaleString());
    setSilverDetailText("[data-silver-clean-words]", page.clean_word_count.toLocaleString());
    setSilverDetailText("[data-silver-raw]", page.raw_text || "No raw OCR was available.");
    setSilverDetailText("[data-silver-clean]", page.clean_text || "No cleaned OCR was available.");
    setSilverDetailText("[data-silver-headers]", page.detected_headers.join(" · ") || "None detected");
    setSilverDetailText("[data-silver-footers]", page.detected_footers.join(" · ") || "None detected");
    setSilverDetailText("[data-silver-lineage]", JSON.stringify(page.lineage, null, 2));
    renderSilverWorkMetadata(page.work_id);

    const quality = document.querySelector("[data-silver-quality]");
    const qualityStyle = page.ocr_quality === "usable"
      ? "ready"
      : page.ocr_quality === "missing" ? "review" : "sample";
    quality.className = `state-badge state-badge--${qualityStyle}`;

    const flags = document.querySelector("[data-silver-flags]");
    flags.replaceChildren();
    const labels = page.quality_flags.length === 0 ? ["no quality flags"] : page.quality_flags;
    labels.forEach((flag) => {
      const chip = document.createElement("span");
      chip.textContent = flag.replaceAll("_", " ");
      flags.append(chip);
    });

    const imageFrame = document.querySelector("[data-silver-image-frame]");
    const image = document.querySelector("[data-silver-image]");
    imageFrame.hidden = !page.image_url;
    if (page.image_url) {
      image.src = page.image_url;
      image.alt = `Digitized image for ${page.page_label}`;
    } else {
      image.removeAttribute("src");
      image.alt = "";
    }
  } catch (error) {
    setSilverDetailText("[data-silver-clean]", `Could not load this Silver page: ${error.message}`);
  }
}

async function refreshSilverPages() {
  const dataset = state.activeSilverDataset;
  if (!dataset) return;
  const query = new URLSearchParams({ limit: "500" });
  if (elements.silverWorkSelect.value) {
    query.set("work_id", elements.silverWorkSelect.value);
  }
  if (elements.silverFlagSelect.value) {
    query.set("quality_flag", elements.silverFlagSelect.value);
  }
  try {
    const url = (
      `${SILVER_DATASETS_ENDPOINT}/${encodeURIComponent(dataset.dataset_id)}` +
      `/pages?${query}`
    );
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Silver pages returned ${response.status}`);
    const result = await response.json();
    state.silverPages = result.items;
    state.silverPageTotal = result.total;
    state.activeSilverPage = null;
    renderSilverPageList();
    if (state.silverPages[0]) {
      await renderSilverPageDetail(state.silverPages[0]);
    } else {
      setSilverDetailText("[data-silver-detail-title]", "No page matches these filters");
      setSilverDetailText("[data-silver-detail-subtitle]", "Choose another work or quality flag.");
    }
  } catch (error) {
    state.silverPages = [];
    state.silverPageTotal = 0;
    renderSilverPageList();
    setSilverDetailText("[data-silver-clean]", `Could not load Silver pages: ${error.message}`);
  }
}

async function selectSilverDataset(datasetId) {
  state.activeSilverDataset = state.silverDatasets.find(
    (dataset) => dataset.dataset_id === datasetId
  ) || null;
  state.silverWorks = [];
  state.silverPages = [];
  state.silverPageTotal = 0;
  state.activeSilverPage = null;
  if (!state.activeSilverDataset) return;
  const baseUrl = (
    `${SILVER_DATASETS_ENDPOINT}/${encodeURIComponent(state.activeSilverDataset.dataset_id)}`
  );
  try {
    const [worksResponse, qualityResponse] = await Promise.all([
      fetch(`${baseUrl}/works`, { headers: { Accept: "application/json" } }),
      fetch(`${baseUrl}/quality`, { headers: { Accept: "application/json" } })
    ]);
    if (!worksResponse.ok || !qualityResponse.ok) {
      throw new Error("Silver dataset details are unavailable");
    }
    state.silverWorks = await worksResponse.json();
    renderSilverWorkOptions();
    renderSilverSummary(await qualityResponse.json());
    await refreshSilverPages();
  } catch (error) {
    setSilverDetailText("[data-silver-clean]", error.message);
  }
}

async function refreshSilverDatasets() {
  elements.silverDatasetSelect.disabled = true;
  try {
    const response = await fetch(SILVER_DATASETS_ENDPOINT, {
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error(`Silver datasets returned ${response.status}`);
    state.silverDatasets = await response.json();
    elements.silverDatasetSelect.replaceChildren();
    if (state.silverDatasets.length === 0) {
      const option = document.createElement("option");
      option.textContent = "No Silver datasets available";
      elements.silverDatasetSelect.append(option);
      setSilverDetailText(
        "[data-silver-clean]",
        "Run the Silver build command against a complete Bronze run."
      );
      return;
    }
    state.silverDatasets.forEach((dataset) => {
      const option = document.createElement("option");
      option.value = dataset.dataset_id;
      option.textContent = (
        `${formatTime(dataset.generated_at)} · ${dataset.work_count} works · ` +
        dataset.dataset_id.slice(0, 12)
      );
      elements.silverDatasetSelect.append(option);
    });
    await selectSilverDataset(state.silverDatasets[0].dataset_id);
  } catch (error) {
    elements.silverDatasetSelect.replaceChildren();
    const option = document.createElement("option");
    option.textContent = "Silver API unavailable";
    elements.silverDatasetSelect.append(option);
    setSilverDetailText("[data-silver-clean]", error.message);
  } finally {
    elements.silverDatasetSelect.disabled = false;
  }
}

function setGoldDetailText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function renderGoldSummary(statistics) {
  const values = [
    ["Works", statistics.work_count.toLocaleString()],
    ["Pages", statistics.contributing_page_count.toLocaleString()],
    ["Chunks", statistics.chunk_count.toLocaleString()],
    [
      "Short / empty",
      `${statistics.short_chunk_count.toLocaleString()} / ` +
      statistics.empty_chunk_count.toLocaleString()
    ]
  ];
  elements.goldSummary.replaceChildren();
  values.forEach(([label, value]) => {
    const wrapper = document.createElement("div");
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value;
    wrapper.append(term, detail);
    elements.goldSummary.append(wrapper);
  });
  setGoldDetailText(
    "[data-gold-token-distribution]",
    `${statistics.minimum_tokens} / ${statistics.median_tokens.toFixed(0)} / ` +
    `${statistics.p95_tokens.toFixed(0)} / ${statistics.maximum_tokens} ` +
    "(min / median / p95 / max)"
  );
  setGoldDetailText(
    "[data-gold-overlap-ratio]",
    `${(statistics.overlap_ratio * 100).toFixed(1)}% · ` +
    `${statistics.actual_overlap_tokens.toLocaleString()} repeated tokens`
  );
  const workExclusions = statistics.exclusions.filter((item) => item.kind === "work").length;
  const pageExclusions = statistics.exclusions.filter((item) => item.kind === "page").length;
  setGoldDetailText(
    "[data-gold-exclusions]",
    `${workExclusions.toLocaleString()} / ${pageExclusions.toLocaleString()}`
  );
}

function describeGoldPageRange(chunk) {
  const sourceLabels = [chunk.page_label_start, chunk.page_label_end];
  const hasUsefulSourceLabels = sourceLabels.every(
    (label) => label && label !== "-" && label !== "—"
  );
  if (hasUsefulSourceLabels) {
    return `pages ${sourceLabels[0]}–${sourceLabels[1]}`;
  }
  return `canvases ${chunk.page_sequence_start}–${chunk.page_sequence_end}`;
}

function renderGoldWorkOptions() {
  const previousValue = elements.goldWorkSelect.value;
  elements.goldWorkSelect.replaceChildren();
  const allWorks = document.createElement("option");
  allWorks.value = "";
  allWorks.textContent = "All works";
  elements.goldWorkSelect.append(allWorks);
  state.goldWorks.forEach((work) => {
    const option = document.createElement("option");
    option.value = work.work_id;
    option.textContent = `${work.title} · ${work.chunk_count} chunks`;
    elements.goldWorkSelect.append(option);
  });
  if (state.goldWorks.some((work) => work.work_id === previousValue)) {
    elements.goldWorkSelect.value = previousValue;
  }
}

function renderGoldChunkList() {
  elements.goldChunkList.replaceChildren();
  elements.goldChunkCount.textContent = (
    state.goldChunks.length === state.goldChunkTotal
      ? `${state.goldChunks.length} ${state.goldChunks.length === 1 ? "chunk" : "chunks"}`
      : `Showing ${state.goldChunks.length} of ${state.goldChunkTotal} chunks`
  );
  elements.goldChunkEmpty.hidden = state.goldChunks.length !== 0;
  state.goldChunks.forEach((chunk) => {
    const button = document.createElement("button");
    const wrapper = document.createElement("span");
    const title = document.createElement("strong");
    const subtitle = document.createElement("small");
    const metadata = document.createElement("span");
    const arrow = document.createElement("span");
    button.type = "button";
    button.className = (
      `record-item${chunk.chunk_id === state.activeGoldChunk?.chunk_id ? " is-active" : ""}`
    );
    button.dataset.goldChunkSelect = chunk.chunk_id;
    title.textContent = `Chunk ${chunk.chunk_index + 1} · ${chunk.token_count} tokens`;
    subtitle.textContent = describeGoldPageRange(chunk);
    metadata.className = "record-meta";
    metadata.textContent = (
      `${chunk.title} · ${chunk.overlap_previous_token_count} overlap tokens`
    );
    arrow.className = "record-arrow";
    arrow.textContent = "›";
    wrapper.append(title, subtitle, metadata);
    button.append(wrapper, arrow);
    elements.goldChunkList.append(button);
  });
}

function appendGoldTextRange(container, chunk, start, end) {
  if (end <= start) return;
  const overlapEnd = chunk.overlap_prefix_char_end;
  if (start < overlapEnd) {
    const markEnd = Math.min(end, overlapEnd);
    const mark = document.createElement("mark");
    mark.className = "gold-overlap";
    mark.textContent = chunk.text.slice(start, markEnd);
    container.append(mark);
    start = markEnd;
  }
  if (end > start) {
    container.append(document.createTextNode(chunk.text.slice(start, end)));
  }
}

function renderGoldChunkText(chunk) {
  const container = document.querySelector("[data-gold-text]");
  container.replaceChildren();
  let cursor = 0;
  chunk.page_spans.forEach((span) => {
    appendGoldTextRange(container, chunk, cursor, span.chunk_char_start);
    const boundary = document.createElement("span");
    boundary.className = "gold-page-boundary";
    boundary.textContent = (
      `\n[Canvas ${span.sequence_number} · source label ${span.page_label}]\n`
    );
    container.append(boundary);
    appendGoldTextRange(
      container,
      chunk,
      span.chunk_char_start,
      span.chunk_char_end
    );
    cursor = span.chunk_char_end;
  });
  appendGoldTextRange(container, chunk, cursor, chunk.text.length);
}

function renderGoldPages(chunk) {
  const container = document.querySelector("[data-gold-pages]");
  container.replaceChildren();
  chunk.page_spans.forEach((span) => {
    const card = document.createElement("article");
    const heading = document.createElement("strong");
    const details = document.createElement("p");
    heading.textContent = `Canvas ${span.sequence_number} · ${span.page_label}`;
    details.textContent = (
      `Chunk characters ${span.chunk_char_start}–${span.chunk_char_end} · ` +
      `Silver source characters ${span.source_char_start}–${span.source_char_end}`
    );
    card.append(heading, details);
    if (span.image_url) {
      const image = document.createElement("img");
      image.src = span.image_url;
      image.alt = `Digitized source image for canvas ${span.sequence_number}`;
      image.loading = "lazy";
      card.prepend(image);
    }
    container.append(card);
  });
}

async function renderGoldChunkDetail(chunkOrId) {
  const dataset = state.activeGoldDataset;
  if (!dataset || !chunkOrId) return;
  const chunkId = typeof chunkOrId === "string" ? chunkOrId : chunkOrId.chunk_id;
  try {
    const url = (
      `${GOLD_DATASETS_ENDPOINT}/${encodeURIComponent(dataset.gold_dataset_id)}` +
      `/chunks/${encodeURIComponent(chunkId)}`
    );
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Gold chunk returned ${response.status}`);
    const chunk = await response.json();
    state.activeGoldChunk = chunk;
    renderGoldChunkList();
    setGoldDetailText(
      "[data-gold-detail-title]",
      `Chunk ${chunk.chunk_index + 1} · ${describeGoldPageRange(chunk)}`
    );
    setGoldDetailText(
      "[data-gold-detail-subtitle]",
      `One retrieval unit from ${chunk.title}`
    );
    setGoldDetailText("[data-gold-profile]", chunk.profile_id);
    setGoldDetailText("[data-gold-chunk-id]", chunk.chunk_id);
    setGoldDetailText("[data-gold-work-id]", chunk.work_id);
    setGoldDetailText("[data-gold-chunk-index]", chunk.chunk_index.toLocaleString());
    setGoldDetailText(
      "[data-gold-token-count]",
      `${chunk.token_count.toLocaleString()} / ${chunk.maximum_token_count.toLocaleString()}`
    );
    setGoldDetailText(
      "[data-gold-page-range]",
      `${chunk.page_sequence_start}–${chunk.page_sequence_end}`
    );
    setGoldDetailText(
      "[data-gold-overlap-count]",
      `${chunk.overlap_previous_token_count.toLocaleString()} tokens`
    );
    setGoldDetailText("[data-gold-work-title]", chunk.title);
    setGoldDetailText(
      "[data-gold-contributors]",
      chunk.contributors.join(" · ") || "Not recorded"
    );
    setGoldDetailText(
      "[data-gold-production]",
      [...chunk.production_dates, ...chunk.production_labels].join(" · ") || "Not recorded"
    );
    setGoldDetailText("[data-gold-language]", chunk.language_id);
    setGoldDetailText("[data-gold-subjects]", chunk.subjects.join(" · ") || "Not recorded");
    setGoldDetailText("[data-gold-genres]", chunk.genres.join(" · ") || "Not recorded");
    const source = document.querySelector("[data-gold-source]");
    source.href = chunk.source_url;
    source.textContent = `${chunk.licence_id} · open digitized work`;
    setGoldDetailText("[data-gold-payload]", JSON.stringify(chunk, null, 2));
    renderGoldChunkText(chunk);
    renderGoldPages(chunk);
    elements.goldPrevious.disabled = !chunk.previous_chunk_id;
    elements.goldPrevious.dataset.chunkId = chunk.previous_chunk_id || "";
    elements.goldNext.disabled = !chunk.next_chunk_id;
    elements.goldNext.dataset.chunkId = chunk.next_chunk_id || "";
  } catch (error) {
    setGoldDetailText(
      "[data-gold-text]",
      `Could not load this Gold chunk: ${error.message}`
    );
  }
}

async function refreshGoldChunks() {
  const dataset = state.activeGoldDataset;
  if (!dataset) return;
  const query = new URLSearchParams({ limit: "500" });
  if (elements.goldWorkSelect.value) {
    query.set("work_id", elements.goldWorkSelect.value);
  }
  try {
    const url = (
      `${GOLD_DATASETS_ENDPOINT}/${encodeURIComponent(dataset.gold_dataset_id)}` +
      `/chunks?${query}`
    );
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(`Gold chunks returned ${response.status}`);
    const result = await response.json();
    state.goldChunks = result.items;
    state.goldChunkTotal = result.total;
    state.activeGoldChunk = null;
    renderGoldChunkList();
    if (state.goldChunks[0]) {
      await renderGoldChunkDetail(state.goldChunks[0]);
    } else {
      setGoldDetailText("[data-gold-detail-title]", "No chunk matches this work");
      setGoldDetailText("[data-gold-detail-subtitle]", "Choose another Gold work.");
    }
  } catch (error) {
    state.goldChunks = [];
    state.goldChunkTotal = 0;
    renderGoldChunkList();
    setGoldDetailText("[data-gold-text]", error.message);
  }
}

async function selectGoldDataset(datasetId) {
  state.activeGoldDataset = state.goldDatasets.find(
    (dataset) => dataset.gold_dataset_id === datasetId
  ) || null;
  state.goldWorks = [];
  state.goldChunks = [];
  state.goldChunkTotal = 0;
  state.activeGoldChunk = null;
  if (!state.activeGoldDataset) return;
  const baseUrl = (
    `${GOLD_DATASETS_ENDPOINT}/${encodeURIComponent(state.activeGoldDataset.gold_dataset_id)}`
  );
  try {
    const [worksResponse, statisticsResponse] = await Promise.all([
      fetch(`${baseUrl}/works`, { headers: { Accept: "application/json" } }),
      fetch(`${baseUrl}/statistics`, { headers: { Accept: "application/json" } })
    ]);
    if (!worksResponse.ok || !statisticsResponse.ok) {
      throw new Error("Gold dataset details are unavailable");
    }
    state.goldWorks = await worksResponse.json();
    renderGoldWorkOptions();
    renderGoldSummary(await statisticsResponse.json());
    await refreshGoldChunks();
  } catch (error) {
    setGoldDetailText("[data-gold-text]", error.message);
  }
}

async function refreshGoldDatasets() {
  elements.goldDatasetSelect.disabled = true;
  try {
    const response = await fetch(GOLD_DATASETS_ENDPOINT, {
      headers: { Accept: "application/json" }
    });
    if (!response.ok) throw new Error(`Gold datasets returned ${response.status}`);
    state.goldDatasets = await response.json();
    elements.goldDatasetSelect.replaceChildren();
    if (state.goldDatasets.length === 0) {
      const option = document.createElement("option");
      option.textContent = "No Gold datasets available";
      elements.goldDatasetSelect.append(option);
      setGoldDetailText(
        "[data-gold-text]",
        "Run the Gold build command against a validated Silver dataset."
      );
      return;
    }
    state.goldDatasets.forEach((dataset) => {
      const option = document.createElement("option");
      option.value = dataset.gold_dataset_id;
      option.textContent = (
        `${dataset.chunking_config.profile_id} · ${dataset.chunk_count} chunks · ` +
        dataset.gold_dataset_id.slice(0, 12)
      );
      elements.goldDatasetSelect.append(option);
    });
    await selectGoldDataset(state.goldDatasets[0].gold_dataset_id);
  } catch (error) {
    elements.goldDatasetSelect.replaceChildren();
    const option = document.createElement("option");
    option.textContent = "Gold API unavailable";
    elements.goldDatasetSelect.append(option);
    setGoldDetailText("[data-gold-text]", error.message);
  } finally {
    elements.goldDatasetSelect.disabled = false;
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
document.querySelectorAll("[data-data-layer]").forEach((button) => {
  button.addEventListener("click", () => setDataLayer(button.dataset.dataLayer));
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
elements.silverDatasetSelect.addEventListener("change", () => {
  selectSilverDataset(elements.silverDatasetSelect.value);
});
elements.silverWorkSelect.addEventListener("change", refreshSilverPages);
elements.silverFlagSelect.addEventListener("change", refreshSilverPages);
elements.silverPageList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-silver-page-select]");
  const page = state.silverPages.find(
    (candidate) => candidate.page_id === button?.dataset.silverPageSelect
  );
  if (page) renderSilverPageDetail(page);
});
elements.goldDatasetSelect.addEventListener("change", () => {
  selectGoldDataset(elements.goldDatasetSelect.value);
});
elements.goldWorkSelect.addEventListener("change", refreshGoldChunks);
elements.goldChunkList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-gold-chunk-select]");
  const chunk = state.goldChunks.find(
    (candidate) => candidate.chunk_id === button?.dataset.goldChunkSelect
  );
  if (chunk) renderGoldChunkDetail(chunk);
});
elements.goldPrevious.addEventListener("click", () => {
  if (elements.goldPrevious.dataset.chunkId) {
    renderGoldChunkDetail(elements.goldPrevious.dataset.chunkId);
  }
});
elements.goldNext.addEventListener("click", () => {
  if (elements.goldNext.dataset.chunkId) {
    renderGoldChunkDetail(elements.goldNext.dataset.chunkId);
  }
});
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
refreshSilverDatasets();
refreshGoldDatasets();
window.setInterval(refreshIngestionStatus, INGESTION_POLL_INTERVAL_MS);

const HEALTH_ENDPOINT = "/health/ready";

/**
 * @typedef {Object} HealthResponse
 * @property {"ok"} status
 * @property {string} service
 * @property {string} version
 * @property {Record<string, "ok">} checks
 */

/**
 * @typedef {Object} SampleRecord
 * @property {string} id
 * @property {string} title
 * @property {string} contributor
 * @property {number} year
 * @property {string} language
 * @property {string} rights
 * @property {number} pages
 * @property {"ready" | "review"} status
 * @property {string} source
 * @property {number} startPage
 * @property {string[]} ocr
 */

/** @type {SampleRecord[]} */
const sampleRecords = [
  {
    id: "WEL-DEMO-001",
    title: "Reports on cholera in London",
    contributor: "Public Health Committee",
    year: 1854,
    language: "English",
    rights: "Public Domain Mark",
    pages: 186,
    status: "ready",
    source: "Wellcome Collection · demo",
    startPage: 17,
    ocr: [
      "The inquiry was directed first to the condition of the water supplied to the several districts, and next to the habits of the population during the weeks in which the sickness prevailed.\n\nEvery reported case was entered by street and date, so that no conclusion should rest on recollection alone.",
      "The returns show a marked difference between neighbouring districts. This difference cannot be understood without attention to drainage, crowding, and the source from which drinking water was obtained.\n\nThe observations are presented as evidence, not as a complete account of every cause.",
      "It is recommended that each local authority preserve a regular register of illness and mortality, accompanied wherever possible by particulars of dwelling, occupation, and water supply.\n\nSuch records would permit earlier warning and more exact comparison."
    ]
  },
  {
    id: "WEL-DEMO-002",
    title: "On the preservation of public health",
    contributor: "Eleanor Whitcombe",
    year: 1848,
    language: "English",
    rights: "Public Domain Mark",
    pages: 224,
    status: "ready",
    source: "Wellcome Collection · demo",
    startPage: 42,
    ocr: [
      "Public health depends not upon a single measure, but upon the ordinary conditions in which families live and labour. Clean water, sufficient air, and the removal of refuse are therefore public concerns.\n\nThe prevention of disease must begin before sickness is visible.",
      "Where streets are narrow and dwellings overcrowded, inspection alone is insufficient. Local reports must lead to works of drainage and to a reliable provision of wholesome water.\n\nDelay transfers the greatest burden to those least able to bear it.",
      "A sanitary report should distinguish observation from inference. The place, date, and number of persons affected ought always to accompany any general conclusion offered to the public."
    ]
  },
  {
    id: "WEL-DEMO-003",
    title: "Notes on sanitary reform",
    contributor: "Thomas H. Bell",
    year: 1872,
    language: "English",
    rights: "Public Domain Mark",
    pages: 98,
    status: "ready",
    source: "Wellcome Collection · demo",
    startPage: 11,
    ocr: [
      "Sanitary reform is often described as an expense, though its first economy is the prevention of avoidable loss. A town pays for neglected drainage more than once: in illness, interrupted work, and emergency relief.\n\nThe accounts should therefore include consequences as well as construction.",
      "The improvement of courts and alleys requires consultation with inhabitants. Plans drawn without knowledge of daily use may move a nuisance rather than remove it.\n\nInspection should be repeated after works are completed.",
      "No table is useful if its headings conceal the unit counted. Houses, persons, and reported cases must not be interchanged, and missing returns should be marked rather than silently estimated."
    ]
  },
  {
    id: "WEL-DEMO-004",
    title: "Medical observations, volume II",
    contributor: "Contributor unconfirmed",
    year: 1861,
    language: "English",
    rights: "Rights review required",
    pages: 0,
    status: "review",
    source: "Wellcome Collection · demo",
    startPage: 0,
    ocr: [
      "OCR is not available for this sample record. The pipeline retains the metadata record and marks the missing page resource for review."
    ]
  }
];

const viewNames = {
  chat: "Chat",
  dashboard: "Ingestion",
  data: "Data explorer",
  retrieval: "Retrieval",
  evaluation: "Evaluation"
};

const state = {
  activeRecordId: sampleRecords[0].id,
  activePageIndex: 0,
  toastTimer: 0
};

const elements = {
  body: document.body,
  sidebar: document.querySelector(".sidebar"),
  sidebarOpenButton: document.querySelector("[data-sidebar-open]"),
  currentView: document.querySelector("[data-current-view]"),
  healthButton: document.querySelector("[data-health-refresh]"),
  healthLabel: document.querySelector("[data-health-label]"),
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
    if (isActive) {
      button.setAttribute("aria-current", "page");
    } else {
      button.removeAttribute("aria-current");
    }
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
  const isHidden = mobileNavigation.matches && !elements.body.classList.contains("sidebar-open");
  elements.sidebar.inert = isHidden;
  if (isHidden) {
    elements.sidebar.setAttribute("aria-hidden", "true");
  } else {
    elements.sidebar.removeAttribute("aria-hidden");
  }
  elements.sidebarOpenButton.setAttribute("aria-expanded", String(!isHidden && mobileNavigation.matches));
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

    /** @type {HealthResponse} */
    const health = await response.json();
    if (health.status !== "ok") throw new Error("Unexpected health response");

    elements.healthButton.className = "system-status is-online";
    elements.healthLabel.textContent = "System operational";
    elements.healthButton.title = `${health.service} ${health.version} · click to refresh`;
  } catch (error) {
    elements.healthButton.className = "system-status is-offline";
    elements.healthLabel.textContent = "Backend offline";
    elements.healthButton.title = "Start the API and click to try again";
  } finally {
    window.clearTimeout(timeoutId);
    elements.healthButton.disabled = false;
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

function getFilteredRecords() {
  const query = elements.recordSearch.value.trim().toLowerCase();
  const filter = elements.recordFilter.value;

  return sampleRecords.filter((record) => {
    const matchesText = [record.title, record.contributor, record.id]
      .some((value) => value.toLowerCase().includes(query));
    const matchesStatus = filter === "all" || record.status === filter;
    return matchesText && matchesStatus;
  });
}

function renderRecordList() {
  const records = getFilteredRecords();
  elements.recordList.replaceChildren();
  elements.recordCount.textContent = `${records.length} ${records.length === 1 ? "work" : "works"}`;
  elements.recordEmpty.hidden = records.length !== 0;

  records.forEach((record) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `record-item${record.id === state.activeRecordId ? " is-active" : ""}`;
    button.dataset.recordId = record.id;
    button.innerHTML = `
      <span>
        <strong>${record.title}</strong>
        <small>${record.contributor}</small>
        <span class="record-meta">${record.year} · ${record.pages || "No"} pages · ${record.status === "ready" ? "Ready" : "Review"}</span>
      </span>
      <span class="record-arrow" aria-hidden="true">›</span>
    `;
    button.setAttribute("aria-label", `Open ${record.title}`);
    elements.recordList.append(button);
  });
}

function getActiveRecord() {
  return sampleRecords.find((record) => record.id === state.activeRecordId) || sampleRecords[0];
}

function updateOcrPage(record) {
  const pageNumber = record.startPage + state.activePageIndex;
  document.querySelector("[data-detail-page]").textContent = pageNumber || "unavailable";
  document.querySelector("[data-page-current]").textContent = state.activePageIndex + 1;
  document.querySelector("[data-page-total]").textContent = record.ocr.length;
  document.querySelector("[data-detail-ocr]").textContent = record.ocr[state.activePageIndex];

  document.querySelector("[data-page-prev]").disabled = state.activePageIndex === 0;
  document.querySelector("[data-page-next]").disabled = state.activePageIndex === record.ocr.length - 1;
}

function renderActiveRecord({ showLoading = false } = {}) {
  const record = getActiveRecord();

  if (showLoading) {
    elements.detailLoading.hidden = false;
    elements.detailContent.setAttribute("aria-busy", "true");
  }

  window.setTimeout(() => {
    document.querySelector("[data-detail-title]").textContent = record.title;
    document.querySelector("[data-detail-contributor]").textContent = record.contributor;
    document.querySelector("[data-detail-id]").textContent = record.id;
    document.querySelector("[data-detail-year]").textContent = record.year;
    document.querySelector("[data-detail-language]").textContent = record.language;
    document.querySelector("[data-detail-rights]").textContent = record.rights;
    document.querySelector("[data-detail-pages]").textContent = record.pages || "Unavailable";
    document.querySelector("[data-detail-source]").textContent = record.source;

    const status = document.querySelector("[data-detail-status]");
    status.textContent = record.status === "ready" ? "Ready" : "Needs review";
    status.className = `state-badge state-badge--${record.status}`;

    updateOcrPage(record);
    elements.detailLoading.hidden = true;
    elements.detailContent.removeAttribute("aria-busy");
  }, showLoading ? 280 : 0);
}

function selectRecord(recordId) {
  if (!sampleRecords.some((record) => record.id === recordId)) return;
  state.activeRecordId = recordId;
  state.activePageIndex = 0;
  renderRecordList();
  renderActiveRecord({ showLoading: true });
}

function moveOcrPage(direction) {
  const record = getActiveRecord();
  state.activePageIndex = Math.max(0, Math.min(record.ocr.length - 1, state.activePageIndex + direction));
  updateOcrPage(record);
}

function resetRecordSearch() {
  elements.recordSearch.value = "";
  elements.recordFilter.value = "all";
  renderRecordList();
  elements.recordSearch.focus();
}

function handleChatSubmit(event) {
  event.preventDefault();
  const input = document.querySelector("[data-chat-input]");
  const feedback = document.querySelector("[data-chat-feedback]");
  const question = input.value.trim();

  if (!question) {
    input.focus();
    return;
  }

  feedback.textContent = "Your question is ready. Answer generation will be connected after retrieval and evidence validation are complete.";
  feedback.hidden = false;
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", () => setActiveView(button.dataset.view));
});

document.querySelector("[data-sidebar-open]").addEventListener("click", openSidebar);
document.querySelectorAll("[data-sidebar-close]").forEach((button) => button.addEventListener("click", closeSidebar));
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
elements.recordSearch.addEventListener("input", renderRecordList);
elements.recordFilter.addEventListener("change", renderRecordList);
document.querySelector("[data-reset-search]").addEventListener("click", resetRecordSearch);

elements.recordList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-record-id]");
  if (button) selectRecord(button.dataset.recordId);
});

document.querySelector("[data-page-prev]").addEventListener("click", () => moveOcrPage(-1));
document.querySelector("[data-page-next]").addEventListener("click", () => moveOcrPage(1));
document.querySelector("[data-copy-id]").addEventListener("click", async () => {
  const record = getActiveRecord();
  try {
    await navigator.clipboard.writeText(record.id);
    showToast(`${record.id} copied to clipboard.`);
  } catch {
    showToast(`Work ID: ${record.id}`);
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeSidebar();
});

mobileNavigation.addEventListener("change", syncSidebarAccessibility);

syncSidebarAccessibility();
renderRecordList();
renderActiveRecord({ showLoading: true });
refreshHealth();

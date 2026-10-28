(function () {
  "use strict";
  const storageKeys = { saved: "lenslist-saved-v2", tracker: "lenslist-tracker-v2" };
  const stages = ["Interested", "Preparing", "Applied", "Shortlisted", "Awarded", "Declined"];
  const state = { opportunities: [], review: [], meta: {}, saved: new Set(readLocal(storageKeys.saved, [])), tracker: readLocal(storageKeys.tracker, {}) };
  const $ = (selector) => document.querySelector(selector);
  const elements = { grid: $("#opportunity-grid"), reviewGrid: $("#review-grid"), empty: $("#empty-state"), reviewEmpty: $("#review-empty"), summary: $("#results-summary"), search: $("#search"), category: $("#category-filter"), geography: $("#geography-filter"), deadline: $("#deadline-filter"), savedOnly: $("#saved-only"), clear: $("#clear-filters"), trackerBoard: $("#tracker-board"), trackerEmpty: $("#tracker-empty"), dialog: $("#detail-dialog"), dialogContent: $("#dialog-content") };

  function readLocal(key, fallback) { try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch (_error) { return fallback; } }
  function writeLocal(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (_error) {} }
  function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
  function formatDate(value) { if (!value) return "Rolling / check source"; return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(value + "T12:00:00Z")); }
  function formatTimestamp(value) { if (!value) return "Not available"; return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }

  async function loadData() {
    const [opportunities, review, meta] = await Promise.all([
      fetch("data/opportunities.json", { cache: "no-store" }).then((response) => response.json()),
      fetch("data/review_queue.json", { cache: "no-store" }).then((response) => response.json()),
      fetch("data/meta.json", { cache: "no-store" }).then((response) => response.json())
    ]);
    state.opportunities = opportunities; state.review = review; state.meta = meta;
  }
  function populateFilters() {
    const addOptions = (select, values) => values.sort().forEach((value) => select.add(new Option(value, value)));
    addOptions(elements.category, [...new Set(state.opportunities.map((item) => item.category))]);
    addOptions(elements.geography, [...new Set(state.opportunities.map((item) => item.geography))]);
  }
  function matchesDeadline(item, filter) {
    if (filter === "all") return true;
    if (filter === "rolling") return !item.deadline || item.rolling;
    if (!item.deadline) return false;
    const days = (new Date(item.deadline + "T23:59:59Z") - new Date()) / 86400000;
    return days >= 0 && days <= Number(filter);
  }
  function filteredItems() {
    const query = elements.search.value.trim().toLowerCase();
    return state.opportunities.filter((item) => {
      const haystack = [item.title, item.organization, item.summary, item.location, item.eligibility, ...(item.tags || [])].join(" ").toLowerCase();
      return (!query || haystack.includes(query)) && (elements.category.value === "all" || item.category === elements.category.value) && (elements.geography.value === "all" || item.geography === elements.geography.value) && matchesDeadline(item, elements.deadline.value) && (!elements.savedOnly.checked || state.saved.has(item.id));
    });
  }
  function saveButton(item) {
    const isSaved = state.saved.has(item.id);
    return '<button class="save-button" type="button" data-save="' + escapeHtml(item.id) + '" aria-pressed="' + isSaved + '" aria-label="' + (isSaved ? "Remove from saved" : "Save opportunity") + '"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.75A1.75 1.75 0 0 1 7.75 2h8.5A1.75 1.75 0 0 1 18 3.75V22l-6-3.5L6 22V3.75Zm1.5 0v15.64L12 16.76l4.5 2.63V3.75a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Z"/></svg></button>';
  }
  function trackerControl(item) {
    const current = state.tracker[item.id]?.stage || "";
    const options = ['<option value="">Track application…</option>'].concat(stages.map((stage) => '<option value="' + stage + '"' + (stage === current ? " selected" : "") + '>' + stage + '</option>'));
    return '<label class="tracker-control"><span>Application stage</span><select data-track="' + escapeHtml(item.id) + '">' + options.join("") + '</select></label>';
  }
  function card(item, reviewMode) {
    const verified = !reviewMode && item.fee_status === "confirmed-free";
    const reason = reviewMode ? (item.review_reasons || ["Verification incomplete"]).join("; ") : "Official fee evidence recorded";
    return '<article class="card ' + (reviewMode ? "card-review" : "") + '"><div class="card-top"><span class="type">' + escapeHtml(item.category) + '</span>' + (reviewMode ? '<span class="review-mark">Review</span>' : saveButton(item)) + '</div><h3>' + escapeHtml(item.title) + '</h3><p class="organisation">' + escapeHtml(item.organization) + ' · ' + escapeHtml(item.location) + '</p><p class="summary">' + escapeHtml(item.summary || "See the official source for full details.") + '</p><dl class="meta"><div><dt>Deadline</dt><dd>' + escapeHtml(formatDate(item.deadline)) + '</dd></div><div><dt>Compensation</dt><dd>' + escapeHtml(item.compensation || "Not stated") + '</dd></div></dl><div class="card-footer"><div><span class="badge ' + (verified ? "badge-free" : "badge-verify") + '">' + (verified ? "✓ Confirmed free" : "! Verification pending") + '</span><p class="fee-note">' + escapeHtml(reason) + '</p></div><button class="details-button" type="button" data-details="' + escapeHtml(item.id) + '" data-review="' + reviewMode + '">Details</button></div>' + (reviewMode ? "" : trackerControl(item)) + '</article>';
  }
  function bindCards(container) {
    container.querySelectorAll("[data-save]").forEach((button) => button.addEventListener("click", () => toggleSaved(button.dataset.save)));
    container.querySelectorAll("[data-track]").forEach((select) => select.addEventListener("change", () => updateTracker(select.dataset.track, select.value)));
    container.querySelectorAll("[data-details]").forEach((button) => button.addEventListener("click", () => showDetails(button.dataset.details, button.dataset.review === "true")));
  }
  function renderBrowse() {
    const items = filteredItems(); elements.grid.innerHTML = items.map((item) => card(item, false)).join(""); elements.empty.hidden = items.length > 0; elements.summary.textContent = items.length + (items.length === 1 ? " verified opportunity" : " verified opportunities") + " shown"; bindCards(elements.grid);
  }
  function renderReview() { elements.reviewGrid.innerHTML = state.review.map((item) => card(item, true)).join(""); elements.reviewEmpty.hidden = state.review.length > 0; bindCards(elements.reviewGrid); }
  function renderTracker() {
    const tracked = Object.entries(state.tracker).filter(([, value]) => value.stage).map(([id, value]) => ({ item: state.opportunities.find((entry) => entry.id === id), value })).filter((entry) => entry.item);
    elements.trackerBoard.innerHTML = stages.map((stage) => { const stageItems = tracked.filter((entry) => entry.value.stage === stage); return '<section class="tracker-column"><h3>' + stage + '<span>' + stageItems.length + '</span></h3>' + stageItems.map((entry) => '<div class="tracker-card"><strong>' + escapeHtml(entry.item.title) + '</strong><span>' + escapeHtml(entry.item.organization) + '</span><select data-track="' + escapeHtml(entry.item.id) + '">' + stages.map((option) => '<option' + (option === stage ? " selected" : "") + '>' + option + '</option>').join("") + '</select></div>').join("") + '</section>'; }).join("");
    elements.trackerEmpty.hidden = tracked.length > 0; elements.trackerBoard.querySelectorAll("[data-track]").forEach((select) => select.addEventListener("change", () => updateTracker(select.dataset.track, select.value))); $("#tracker-count").textContent = tracked.length;
  }
  function toggleSaved(id) { state.saved.has(id) ? state.saved.delete(id) : state.saved.add(id); writeLocal(storageKeys.saved, [...state.saved]); refreshCounts(); renderBrowse(); }
  function updateTracker(id, stage) { if (!stage) delete state.tracker[id]; else state.tracker[id] = { stage, updatedAt: new Date().toISOString() }; writeLocal(storageKeys.tracker, state.tracker); renderBrowse(); renderTracker(); refreshCounts(); }
  function detailRow(label, value) { return '<div class="detail-row"><strong>' + escapeHtml(label) + '</strong><p>' + escapeHtml(value || "Not stated") + '</p></div>'; }
  function showDetails(id, reviewMode) {
    const item = (reviewMode ? state.review : state.opportunities).find((entry) => entry.id === id); if (!item) return;
    elements.dialogContent.innerHTML = '<div class="eyebrow">' + escapeHtml(item.category) + '</div><h2 id="dialog-title">' + escapeHtml(item.title) + '</h2><p class="dialog-org">' + escapeHtml(item.organization) + ' · ' + escapeHtml(item.location) + '</p>' + detailRow("Deadline", formatDate(item.deadline)) + detailRow("Eligibility", item.eligibility) + detailRow("Compensation", item.compensation) + detailRow("Copyright terms", item.copyright_terms) + detailRow("Publication costs", item.publication_costs) + detailRow("Fee evidence", item.fee_evidence || "Not conclusively verified") + detailRow("Last verified", formatTimestamp(item.last_verified)) + '<a class="official-button" href="' + escapeHtml(item.source_url) + '" target="_blank" rel="noreferrer">Open official source ↗</a>';
    elements.dialog.showModal();
  }
  function switchView(name) {
    document.querySelectorAll("[data-view-panel]").forEach((panel) => { const active = panel.dataset.viewPanel === name; panel.hidden = !active; panel.classList.toggle("active", active); });
    document.querySelectorAll("[data-view]").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
    document.querySelector('[data-view-panel="' + name + '"]').scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  }
  function refreshCounts() {
    $("#opportunity-count").textContent = state.opportunities.length; $("#review-stat").textContent = state.review.length; $("#review-count").textContent = state.review.length; $("#saved-stat").textContent = state.saved.size; $("#last-updated").textContent = formatTimestamp(state.meta.last_updated); $("#last-updated").dateTime = state.meta.last_updated || ""; $("#pipeline-status").textContent = state.meta.pipeline || "Operational";
  }
  function exportTracker() {
    const rows = [["Title", "Organisation", "Stage", "Deadline", "Official source"]]; Object.entries(state.tracker).forEach(([id, entry]) => { const item = state.opportunities.find((value) => value.id === id); if (item && entry.stage) rows.push([item.title, item.organization, entry.stage, item.deadline || "Rolling", item.source_url]); });
    const csv = rows.map((row) => row.map((cell) => '"' + String(cell).replaceAll('"', '""') + '"').join(",")).join("\n"); const link = document.createElement("a"); link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); link.download = "lenslist-application-tracker.csv"; link.click(); URL.revokeObjectURL(link.href);
  }
  function bindGlobalEvents() {
    [elements.search, elements.category, elements.geography, elements.deadline, elements.savedOnly].forEach((control) => control.addEventListener(control === elements.search ? "input" : "change", renderBrowse));
    elements.clear.addEventListener("click", () => { elements.search.value = ""; elements.category.value = "all"; elements.geography.value = "all"; elements.deadline.value = "all"; elements.savedOnly.checked = false; renderBrowse(); elements.search.focus(); });
    document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view))); $(".dialog-close").addEventListener("click", () => elements.dialog.close()); elements.dialog.addEventListener("click", (event) => { if (event.target === elements.dialog) elements.dialog.close(); }); $("#export-tracker").addEventListener("click", exportTracker);
  }
  async function init() { bindGlobalEvents(); try { await loadData(); populateFilters(); refreshCounts(); renderBrowse(); renderReview(); renderTracker(); } catch (error) { elements.summary.textContent = "The verified feed could not be loaded. Please retry shortly."; $("#pipeline-status").textContent = "Data unavailable"; console.error(error); } }
  init();
}());

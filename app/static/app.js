const singleForm = document.getElementById("singleForm");
const singleInput = document.getElementById("singlePhone");
const singleClear = document.getElementById("singleClear");
const singleResult = document.getElementById("singleResult");
const singleResultLayer = document.getElementById("singleResultLayer");
const globalStatus = document.getElementById("globalStatus");
const runtimeHint = document.getElementById("runtimeHint");
const kpiMatches = document.getElementById("kpiMatches");
const kpiHigh = document.getElementById("kpiHigh");
const resultStamp = document.getElementById("resultStamp");

const bulkForm = document.getElementById("bulkForm");
const bulkInput = document.getElementById("bulkPhones");
const bulkAsync = document.getElementById("bulkAsync");
const bulkResult = document.getElementById("bulkResult");
const bulkProgressBar = document.getElementById("bulkProgressBar");
const bulkProgressText = document.getElementById("bulkProgressText");
const jobStatus = document.getElementById("jobStatus");

const apiEnabled = window.location.protocol !== "file:";

function setStatus(text, tone) {
  globalStatus.textContent = text;
  globalStatus.dataset.tone = tone;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function confidenceLabel(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}% vertrouwen`;
}

function confidenceClass(value, matchType) {
  const score = Number(value || 0);
  if (matchType === "exact" || score >= 0.75) return "";
  if (score >= 0.45) return "warn";
  return "error";
}

function updateCounts(results) {
  const matchCount = results.length;
  const highConfidenceCount = results.filter((item) => Number(item.confidence || 0) >= 0.75).length;
  kpiMatches.textContent = `${matchCount} treffers`;
  kpiHigh.textContent = `${highConfidenceCount} hoge score`;
}

function renderSummary(text, target) {
  target.className = "summary-box";
  target.textContent = text;
}

function renderEmptyResults(message) {
  singleResultLayer.className = "result-layer muted-empty";
  singleResultLayer.innerHTML = `<span class="empty-label">${escapeHtml(message)}</span>`;
}

function renderMatches(results, stamp) {
  if (!results.length) {
    updateCounts([]);
    resultStamp.textContent = stamp;
    renderEmptyResults("Geen publieke matches gevonden.");
    return;
  }

  const cards = results
    .map((item) => {
      const platform = escapeHtml(item.platform || item.source || "Onbekend platform");
      const source = escapeHtml(item.source || "Onbekende bron");
      const matchType = escapeHtml(item.match_type || "context");
      const name = escapeHtml(item.name || "Onbekend");
      const handle = escapeHtml(item.account_handle || "-");
      const organization = escapeHtml(item.organization || "-");
      const location = escapeHtml(item.location || "-");
      const evidence = escapeHtml((item.evidence || []).slice(0, 6).join(" | ") || "-");
      const url = item.account_url
        ? `<a href="${escapeAttr(item.account_url)}" target="_blank" rel="noopener">${escapeHtml(item.account_url)}</a>`
        : "-";

      return `
        <article class="match-card">
          <div class="match-top">
            <div class="match-tags">
              <span class="tag platform">${platform}</span>
              <span class="tag">${source}</span>
              <span class="tag">${matchType}</span>
            </div>
            <span class="tag score-tag ${confidenceClass(item.confidence, item.match_type)}">${confidenceLabel(item.confidence)}</span>
          </div>
          <div class="match-body">
            <strong>Naam</strong><span>${name}</span>
            <strong>Gebruikersnaam</strong><span>${handle}</span>
            <strong>Organisatie</strong><span>${organization}</span>
            <strong>Locatie</strong><span>${location}</span>
            <strong>Bronlink</strong><span>${url}</span>
            <strong>Bewijs</strong><span>${evidence}</span>
          </div>
        </article>
      `;
    })
    .join("");

  updateCounts(results);
  resultStamp.textContent = stamp;
  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = cards;
}

function resetSingleView() {
  renderSummary("Status standby\nNog geen actieve lookup.", singleResult);
  renderEmptyResults("Geen resultaten geladen.");
  kpiMatches.textContent = "0 treffers";
  kpiHigh.textContent = "0 hoge score";
  resultStamp.textContent = "wachten...";
}

async function runSingleLookup(phoneNumber) {
  setStatus("Zoeken", "busy");
  renderSummary("Lookup gestart...\nBezig met zoeken naar publieke signalen.", singleResult);
  renderEmptyResults("Matches laden...");

  const response = await fetch("/api/v1/lookup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
  const payload = await response.json();

  if (!response.ok) {
    setStatus("Zoeken mislukt", "err");
    renderSummary(`Fout: ${payload.detail || "onbekend"}`, singleResult);
    renderEmptyResults("Lookup mislukt.");
    return;
  }

  renderSummary(
    [
      `Status: ${payload.status}`,
      `Request ID: ${payload.request_id}`,
      `E164: ${payload.phone_e164}`,
      `Resultaten: ${payload.results.length}`,
    ].join("\n"),
    singleResult,
  );
  renderMatches(payload.results || [], `lookup ${payload.phone_e164}`);
  setStatus("Zoeken klaar", "ok");
}

async function pollJob(jobId) {
  const response = await fetch(`/api/v1/jobs/${jobId}`);
  if (!response.ok) {
    setStatus("Batch mislukt", "err");
    renderSummary("Job niet gevonden.", jobStatus);
    return;
  }

  const payload = await response.json();
  const percent = Math.max(0, Math.min(100, Number(payload.percent || 0)));

  bulkProgressBar.style.width = `${percent}%`;
  bulkProgressText.textContent = `${payload.processed_items} / ${payload.total_items}`;
  renderSummary(
    [
      `Status: ${payload.status}`,
      `Voortgang: ${payload.processed_items}/${payload.total_items} (${payload.percent}%)`,
      `Error: ${payload.error || "-"}`,
      "",
      ...payload.items.map((item) => `${item.row_index}. ${item.phone_raw} -> ${item.status}`),
    ].join("\n"),
    jobStatus,
  );

  if (payload.status === "done") {
    setStatus("Batch klaar", "ok");
    return;
  }

  if (payload.status === "error") {
    setStatus("Batch mislukt", "err");
    return;
  }

  setStatus("Batch draait", "busy");
  window.setTimeout(() => pollJob(jobId), 1200);
}

singleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const phoneNumber = singleInput.value.trim();

  if (!phoneNumber) {
    setStatus("Invoer ontbreekt", "err");
    renderSummary("Voer eerst een telefoonnummer in.", singleResult);
    return;
  }

  if (!apiEnabled) {
    setStatus("Previewmodus", "busy");
    renderSummary("Design preview actief.\nOpen http://127.0.0.1:8000 voor live lookup.", singleResult);
    renderEmptyResults("Live API is niet beschikbaar in file preview.");
    return;
  }

  await runSingleLookup(phoneNumber);
});

singleClear.addEventListener("click", () => {
  singleInput.value = "";
  resetSingleView();
});

bulkForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const numbers = bulkInput.value.split("\n").map((value) => value.trim()).filter(Boolean);

  if (!numbers.length) {
    setStatus("Batchinvoer ontbreekt", "err");
    renderSummary("Voer minimaal één nummer in.", bulkResult);
    return;
  }

  if (!apiEnabled) {
    setStatus("Previewmodus", "busy");
    renderSummary("Bulk preview actief.\nOpen http://127.0.0.1:8000 voor echte jobs.", bulkResult);
    return;
  }

  setStatus("Batch gestart", "busy");
  bulkProgressBar.style.width = "0%";
  bulkProgressText.textContent = "0 / 0";
  renderSummary("Batch wordt gestart...", bulkResult);
  renderSummary("Geen actieve queue.", jobStatus);

  const response = await fetch("/api/v1/lookup/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ numbers, async_mode: bulkAsync.checked }),
  });
  const payload = await response.json();

  if (!response.ok) {
    setStatus("Batch mislukt", "err");
    renderSummary(`Fout: ${payload.detail || "onbekend"}`, bulkResult);
    return;
  }

  if (payload.job_id) {
    renderSummary(`Async job gestart: ${payload.job_id}`, bulkResult);
    pollJob(payload.job_id);
    return;
  }

  bulkProgressBar.style.width = "100%";
  bulkProgressText.textContent = `${payload.request_count} / ${payload.request_count}`;
  setStatus("Batch klaar", "ok");
  renderSummary(`Sync batch voltooid: ${payload.request_count} items`, bulkResult);
});

if (!apiEnabled) {
  runtimeHint.textContent = "Preview mode via file://. Voor live zoekopdrachten open de lokale server op http://127.0.0.1:8000.";
  setStatus("Previewmodus", "busy");
} else {
  runtimeHint.textContent = "Live mode actief. Resultaten worden direct uit de API en publieke bronnen geladen.";
}

resetSingleView();
if (!apiEnabled) {
  setStatus("Previewmodus", "busy");
} else {
  setStatus("Systeem standby", "idle");
}
